"""Unsplash photos as an optional third source (needs UNSPLASH_ACCESS_KEY).

Unsplash is photos only, but its catalogue is large and its photos are framed
for editorial use, which suits the still scenes (health, motivation, law). The
free developer key allows 50 requests/hour, so a search is cached for a day and
one query is asked per scene, exactly like the Pexels path.

No key configured means no requests and the caller keeps Pexels / Pixabay /
Commons. Ids are prefixed (`unsplash-<id>`) to keep them distinct in the reuse
registry.
"""
import hashlib
import json
import time
from pathlib import Path

from app.config.settings import settings
from . import search_text

API = 'https://api.unsplash.com/search/photos'
CDN_HOSTS = ('images.unsplash.com',)
LICENSE = 'Unsplash License — free to use, credited here'
LICENSE_URL = 'https://unsplash.com/license'
SOURCE_NAME = 'Unsplash'


def configured():
    return bool(settings.UNSPLASH_ACCESS_KEY.get_secret_value())


def _cache_dir():
    path = Path(settings.STORAGE_PATH) / 'video_creator' / 'unsplash-cache'
    path.mkdir(parents=True, exist_ok=True)
    return path


def search(client, query, cache=None, page=1, limit=20):
    """Cached photo results for a query; empty list when no key is configured."""
    key = settings.UNSPLASH_ACCESS_KEY.get_secret_value()
    if not key:
        return []
    cache = cache or _cache_dir()
    stamp = hashlib.sha256(f'{query}|{page}'.encode()).hexdigest()[:24]
    path = cache / f'search-{stamp}.json'
    try:
        if time.time() - path.stat().st_mtime < 86400:
            return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    response = client.get(API, headers={'Authorization': f'Client-ID {key}'},
                          params={'query': query, 'orientation': 'portrait',
                                  'content_filter': 'high', 'per_page': limit,
                                  'page': page})
    response.raise_for_status()
    results = response.json().get('results') or []
    try:
        path.write_text(json.dumps(results), encoding='utf-8')
    except OSError:
        pass
    return results


def pick_photo(results, blocked, query):
    """First unused photo that describes the query, else one with no description.

    ``alt_description`` is Unsplash's own description of the shot, so it is the
    cheapest relevance label available without a vision model. A photo the
    service labelled with something else is rejected (the caller then keeps its
    topic illustration); only an unlabelled photo is accepted as unknown.
    """
    usable = [photo for photo in results if f"unsplash-{photo.get('id')}" not in blocked]
    return (next((photo for photo in usable
                  if search_text.matches(query, photo.get('alt_description')
                                         or photo.get('description'))), None)
            or next((photo for photo in usable
                     if not (photo.get('alt_description') or photo.get('description'))), None))


def photo_credit(photo):
    user = photo.get('user') or {}
    return {
        'id': f"unsplash-{photo.get('id')}",
        'photographer': user.get('name') or SOURCE_NAME,
        'source_url': (photo.get('links') or {}).get('html') or '',
        'license': LICENSE,
        'license_url': LICENSE_URL,
    }


def photo_link(photo):
    """A ~1080 px wide rendition: enough for a 1080x1920 crop, small download."""
    urls = photo.get('urls') or {}
    return str(urls.get('regular') or urls.get('full') or '')
