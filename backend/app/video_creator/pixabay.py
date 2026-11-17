"""Pixabay as a second stock library (needs PIXABAY_API_KEY).

Pexels alone means one catalogue: the same clips come back for a topic until the
reuse window runs out. Pixabay's free API returns a different catalogue of photos
and portrait video clips under its own licence, so a key here roughly doubles
what a scene can be matched against. No key configured means every search returns
nothing and the caller simply keeps Pexels / Unsplash / Commons.

Pixabay answers with its own shapes (`hits`, `tags`, `videos.large.url`), while
the rest of the pipeline speaks Pexels shapes, so `pick_video` normalises a hit
into the same fields the Pexels path already reads. Ids are prefixed
(`pixabay-123`) because Pixabay and Pexels both number from 1: without the prefix
the reuse registry would treat a Pixabay photo and a Pexels photo as the same
asset and block the wrong one.
"""
import hashlib
import json
import time
from pathlib import Path

from app.config.settings import settings
from . import search_text

VIDEO_API = 'https://pixabay.com/api/videos/'
PHOTO_API = 'https://pixabay.com/api/'
CDN_HOSTS = ('cdn.pixabay.com',)
LICENSE = 'Pixabay Content License — free for commercial use'
LICENSE_URL = 'https://pixabay.com/service/license-summary/'
SOURCE_NAME = 'Pixabay'


def configured():
    return bool(settings.PIXABAY_API_KEY.get_secret_value())


def _cache_dir():
    path = Path(settings.STORAGE_PATH) / 'video_creator' / 'pixabay-cache'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _search(client, api, params, cache):
    """Cached hits for one query; empty list when no key is configured."""
    key = settings.PIXABAY_API_KEY.get_secret_value()
    if not key:
        return []
    params = dict(params, key=key, safesearch='true')
    stamp = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:24]
    label = 'videos' if api == VIDEO_API else 'photos'
    path = cache / f'{label}-{stamp}.json'
    try:
        if time.time() - path.stat().st_mtime < 86400:
            return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    response = client.get(api, params=params)
    response.raise_for_status()
    hits = response.json().get('hits') or []
    try:
        path.write_text(json.dumps(hits), encoding='utf-8')
    except OSError:
        pass
    return hits


def videos(client, query, cache=None):
    return _search(client, VIDEO_API, {'q': query, 'orientation': 'vertical',
                                      'video_type': 'film', 'per_page': 20},
                   cache or _cache_dir())


def photos(client, query, cache=None):
    return _search(client, PHOTO_API, {'q': query, 'image_type': 'photo',
                                      'orientation': 'vertical', 'per_page': 20},
                   cache or _cache_dir())


def _file(hit):
    """Largest portrait rendition Pixabay offers for a clip."""
    for name in ('large', 'medium', 'small'):
        video = (hit.get('videos') or {}).get(name) or {}
        width, height = video.get('width') or 0, video.get('height') or 0
        if video.get('url') and height and height >= width:
            return {'link': video['url'], 'width': width, 'height': height}
    return None


def _normalise(hit, file):
    """A hit in the Pexels video shape the renderer already understands."""
    return {
        'id': f"pixabay-{hit.get('id')}",
        'duration': float(hit.get('duration') or 0),
        'url': hit.get('pageURL') or '',
        'user': {'name': hit.get('user') or SOURCE_NAME},
        'provider': 'pixabay',
        'source_name': SOURCE_NAME,
        'license': LICENSE,
        'license_url': LICENSE_URL,
        'video_files': [{'file_type': 'video/mp4', 'width': file['width'],
                         'height': file['height'], 'link': file['link']}],
    }


def pick_video(hits, need, blocked, query):
    """(video, file) of the best unused clip whose tags describe the query."""
    best, best_score = None, None
    for rank, hit in enumerate(hits):
        file = _file(hit)
        if not file:
            continue
        video = _normalise(hit, file)
        if video['id'] in blocked or video['duration'] < 4:
            continue
        # Pixabay's `tags` are its own hand-written labels, so they are a fair
        # relevance check: a query for "shared meal" must not return any random
        # clip that merely ranked high.
        if not search_text.matches(query, hit.get('tags')):
            continue
        detail = search_text.overlap(query, str(hit.get('tags') or ''))
        score = (0 if video['duration'] >= need else 1, -min(detail, 3), rank,
                 abs(video['duration'] - need))
        if best_score is None or score < best_score:
            best, best_score = (video, file), score
    return best


def pick_photo(hits, blocked, query):
    """First unused photo whose tags or page slug describe the query.

    Pixabay always writes its own `tags`, so an unmatched hit is skipped rather
    than used: a random courthouse for a "cat" search is worse than the topic
    illustration the caller falls back to.
    """
    usable = [hit for hit in hits if f"pixabay-{hit.get('id')}" not in blocked]
    return (next((hit for hit in usable if search_text.matches(query, hit.get('tags'))), None)
            or next((hit for hit in usable
                     if search_text.matches(query, hit.get('pageURL'))), None))


def photo_credit(hit):
    return {
        'id': f"pixabay-{hit.get('id')}",
        'photographer': hit.get('user') or SOURCE_NAME,
        'source_url': hit.get('pageURL') or '',
        'license': LICENSE,
        'license_url': LICENSE_URL,
    }


def photo_link(hit):
    """Best still for a portrait frame: Pixabay's large URL, else the preview."""
    return str(hit.get('largeImageURL') or hit.get('webformatURL') or '')
