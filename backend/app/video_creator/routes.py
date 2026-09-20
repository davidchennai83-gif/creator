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
    kind: Literal['history', 'indian-law'] = 'history'
    day: date = Field(default_factory=lambda: datetime.now(timezone(timedelta(hours=5, minutes=30))).date())
    voice: Literal['ta-IN-PallaviNeural', 'ta-IN-ValluvarNeural'] = 'ta-IN-PallaviNeural'


@router.get('/capabilities')
def capabilities(user=Depends(get_current_user)):
    try:
        r = httpx.get(settings.OLLAMA_BASE_URL.rstrip('/') + '/api/tags', timeout=5)
        r.raise_for_status()
        models = [m['name'] for m in r.json()['models']]
    except (httpx.HTTPError, ValueError, KeyError):
        models = []
    return success({'model': settings.HISTORY_MODEL, 'installed': settings.HISTORY_MODEL in models,
                    'stock_photos_configured': bool(settings.PEXELS_API_KEY.get_secret_value()),
                    'models': models, 'mode': 'Narrated Tamil history scenes (not text-to-motion AI)',
                    'internet_required': 'History sources and neural Tamil speech'})


@router.get('/jobs')
def listing(user=Depends(get_current_user)):
    return success(jobs.listing(user.id))


@router.post('/jobs', status_code=202)
def create(data: Request, user=Depends(editor)):
    try:
        return success(jobs.new(user.id, data.day, data.voice, data.kind))
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


@router.get('/jobs/{job_id}/download')
def download(job_id: UUID, user=Depends(get_current_user)):
    job = owned(job_id, user)
    path = jobs.root() / str(job_id) / 'history.mp4'
    if job['status'] != 'complete' or not path.is_file():
        raise HTTPException(409, 'MP4 is not ready')
    prefix = 'indian-law' if job.get('kind') == 'indian-law' else 'day-of-history'
    return FileResponse(path, media_type='video/mp4', filename=f"{prefix}-{job['date']}.mp4")


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
