import base64
import hashlib
import hmac
import json
import time
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app.api.deps import editor, get_current_user
from app.config.settings import settings
from app.schemas.common import success
from . import jobs

router = APIRouter()


class Request(BaseModel):
    kind: Literal['history', 'indian-law', 'make-money', 'news', 'thirukkural', 'english', 'gk', 'health', 'motivation', 'kids', 'meesho'] = 'history'
    day: date = Field(default_factory=lambda: datetime.now(timezone(timedelta(hours=5, minutes=30))).date())
    voice: Literal['ta-IN-PallaviNeural', 'ta-IN-ValluvarNeural', 'ta-LK-KumarNeural', 'ta-LK-SaranyaNeural', 'ta-MY-KaniNeural', 'ta-MY-SuryaNeural', 'ta-SG-AnbuNeural', 'ta-SG-VenbaNeural'] = 'ta-IN-PallaviNeural'
    # Voice-over delivery, passed straight to edge-tts. Example: rate "+15%", pitch "-5Hz", volume "+10%".
    rate: str = Field(default='+15%', pattern=r'^[+-]\d{1,3}%$')
    pitch: str = Field(default='+0Hz', pattern=r'^[+-]\d{1,3}Hz$')
    volume: str = Field(default='+0%', pattern=r'^[+-]\d{1,3}%$')
    display: Literal['tamil', 'tanglish'] = 'tamil'


@router.get('/capabilities')
def capabilities(user=Depends(get_current_user)):
    from .video_gen import provider_state
    try:
        r = httpx.get(settings.OLLAMA_BASE_URL.rstrip('/') + '/api/tags', timeout=5)
        r.raise_for_status()
        models = [m['name'] for m in r.json()['models']]
    except (httpx.HTTPError, ValueError, KeyError):
        models = []
    motion = provider_state()
    return success({'model': settings.HISTORY_MODEL, 'installed': settings.HISTORY_MODEL in models,
                    'stock_photos_configured': bool(settings.PEXELS_API_KEY.get_secret_value()),
                    'models': models, 'mode': 'Moving narrated Tamil scenes (provider AI clips or local animation)',
                    'internet_required': 'History sources and neural Tamil speech',
                    'motion': motion,
                    'output': f"{settings.VIDEO_OUTPUT_WIDTH}x{settings.VIDEO_OUTPUT_HEIGHT} {settings.VIDEO_FPS}fps"})


@router.get('/jobs')
def listing(user=Depends(get_current_user)):
    return success(jobs.listing(user.id))


@router.post('/jobs', status_code=202)
def create(data: Request, user=Depends(editor)):
    try:
        return success(jobs.new(user.id, data.day, data.voice, data.kind,
                                rate=data.rate, pitch=data.pitch, volume=data.volume, display=data.display))
    except ValueError as exc:
        raise HTTPException(409, str(exc))


def owned(job_id, user):
    job = jobs.get(job_id, user.id)
    if not job:
        raise HTTPException(404, 'Video job not found')
    return job


@router.get('/jobs/{job_id}')
def status(job_id: UUID, user=Depends(get_current_user)):
    return success(owned(job_id, user))


@router.post('/jobs/{job_id}/render', status_code=202)
def start_render(job_id: UUID, user=Depends(editor)):
    job = owned(job_id, user)
    if job['status'] != 'review':
        raise HTTPException(409, 'Generate and review a script first')
    try:
        return success(jobs.launch(job, 'render'))
    except ValueError as exc:
        raise HTTPException(409, str(exc))


_DOWNLOAD_TTL = 6 * 60 * 60  # 6 hours: enough for a slow mobile download or a long preview.


def _download_key() -> bytes:
    """Separate signing key for download links, derived from the JWT secret."""
    return hmac.new(settings.JWT_SECRET.encode(), b'video-download', hashlib.sha256).digest()


def _sign_download(job_id: UUID, user_id: UUID, format: str) -> str:
    payload = json.dumps({'j': str(job_id), 'u': str(user_id), 'f': format,
                          'e': int(time.time()) + _DOWNLOAD_TTL}, separators=(',', ':')).encode()
    body = base64.urlsafe_b64encode(payload).rstrip(b'=')
    sig = hmac.new(_download_key(), body, hashlib.sha256).digest()
    return body.decode() + '.' + base64.urlsafe_b64encode(sig).rstrip(b'=').decode()


def _read_download(token: str) -> dict:
    try:
        body, sig = token.split('.', 1)
        expected = hmac.new(_download_key(), body.encode(), hashlib.sha256).digest()
        given = base64.urlsafe_b64decode(sig + '=' * (-len(sig) % 4))
        if not hmac.compare_digest(given, expected):
            raise ValueError('bad signature')
        data = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        if int(data['e']) < int(time.time()) or data.get('f') not in ('landscape', 'portrait'):
            raise ValueError('expired')
        return data
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, 'Download link expired — reopen the app and try again')


def _mp4(job, job_id: UUID, format: str):
    filename = 'history.mp4' if format != 'portrait' else 'history-portrait.mp4'
    path = jobs.root() / str(job_id) / filename
    if job['status'] != 'complete' or not path.is_file():
        raise HTTPException(409, 'MP4 is not ready')
    prefix = {'indian-law': 'indian-law', 'make-money': 'make-money', 'news': 'tamil-news',
              'thirukkural': 'thirukkural', 'english': 'spoken-english', 'gk': 'amazing-facts',
              'health': 'health-tips', 'motivation': 'life-lessons', 'kids': 'kids-learning',
              'meesho': 'tamil-budget-finds'}.get(job.get('kind'), 'day-of-history')
    suffix = '' if format != 'portrait' else '-portrait'
    return path, f"{prefix}-{job['date']}{suffix}.mp4"


class DownloadLink(BaseModel):
    format: Literal['landscape', 'portrait'] = 'landscape'


@router.get('/jobs/{job_id}/download')
def download(job_id: UUID, user=Depends(get_current_user), format: str = 'landscape'):
    """Legacy authenticated response; the app uses the signed link below for native
    downloads so a 50 MB MP4 is streamed to disk instead of buffered by axios."""
    job = owned(job_id, user)
    path, name = _mp4(job, job_id, format)
    return FileResponse(path, media_type='video/mp4', filename=name)


@router.post('/jobs/{job_id}/download-link')
def download_link(job_id: UUID, body: DownloadLink, user=Depends(get_current_user)):
    job = owned(job_id, user)
    _mp4(job, job_id, body.format)  # validate readiness before handing out a link
    return success({'token': _sign_download(job_id, user.id, body.format), 'expires_in': _DOWNLOAD_TTL})


@router.get('/download/{token}')
def download_signed(token: str):
    """No Authorization header: the signed token proves job + owner + expiry. This is
    what lets iOS/Android use their native download manager (stream, resume, no timeout)."""
    data = _read_download(token)
    job = jobs.get(UUID(data['j']), UUID(data['u']))
    if not job:
        raise HTTPException(404, 'Video job not found')
    path, name = _mp4(job, UUID(data['j']), data['f'])
    return FileResponse(path, media_type='video/mp4', filename=name)


@router.post('/jobs/{job_id}/delete')
def delete(job_id: UUID, user=Depends(editor)):
    owned(job_id, user)
    try:
        if not jobs.delete(job_id, user.id):
            raise HTTPException(404, 'Video job not found')
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except OSError:
        raise HTTPException(409, 'Could not remove video files. Close any external video player and retry.')
    return success({'id': str(job_id), 'deleted': True})
