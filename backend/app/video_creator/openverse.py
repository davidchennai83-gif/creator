"""Openverse: one search over many free-licence libraries, no key required.

Openverse aggregates Flickr, Wikimedia Commons, museums and other CC archives
into a single image search, which is exactly the "connect the free websites"
idea. It works without any account, so it needs no signup; an optional
OPENVERSE_TOKEN only raises the request limit.

Two things shape how it is used:

* Anonymous access is 20 requests/minute and 200/day, which is plenty for a
  daily batch but not for a retry storm, so one 429 stops Openverse for the rest
  of the render. An optional OPENVERSE_TOKEN raises those limits.
* Results come from many hosts, so the download cannot use a fixed host
  allow-list; each URL goes through the project's SSRF guard instead.

Only CC0, public domain and plain CC BY are accepted. BY-SA is refused because
ShareAlike would force the whole monetised video under the same licence, and
NC/ND are refused by the `license_type=commercial,modification` filter.
"""
import hashlib
import json
import re
import time
from pathlib import Path

from app.config.settings import settings
from . import search_text

API = 'https://api.openverse.org/v1/images/'
LICENSE_URL = 'https://creativecommons.org/licenses/'
SOURCE_NAME = 'Openverse'
ALLOWED = {'cc0', 'pdm', 'by'}


def configured():
    """Openverse always answers anonymously; a token is optional."""
    return True


def _cache_dir():
    path = Path(settings.STORAGE_PATH) / 'video_creator' / 'openverse-cache'
    path.mkdir(parents=True, exist_ok=True)
    return path


def search(client, query, cache=None, page_size=20):
    """Cached, licence-filtered images for a query (empty list on no key needed)."""
    cache = cache or _cache_dir()
    stamp = hashlib.sha256(query.encode()).hexdigest()[:24]
    path = cache / f'search-{stamp}.json'
    try:
        if time.time() - path.stat().st_mtime < 86400:
            return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    params = {
        'q': query, 'page_size': page_size, 'size': 'large',
        'license_type': 'commercial,modification', 'mature': 'false',
        'filter_dead': 'true',
    }
    headers = {'User-Agent': 'CreatorPlatform/1.0 (Tamil daily video renderer)'}
    token = settings.OPENVERSE_TOKEN.get_secret_value()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    response = client.get(API, params=params, headers=headers)
    response.raise_for_status()
    images = []
    for item in response.json().get('results') or []:
        licence = str(item.get('license') or '').lower()
        if licence not in ALLOWED:
            continue
        link = str(item.get('url') or '')
        if not link.startswith('https://'):
            continue
        images.append(item)
    try:
        path.write_text(json.dumps(images), encoding='utf-8')
    except OSError:
        pass
    return images


def label(item):
    """Everything the record itself says about the picture."""
    tags = ' '.join(str(tag.get('name') or '') for tag in item.get('tags') or []
                    if isinstance(tag, dict))
    return ' '.join(_text(item.get(key)) for key in ('title', 'foreign_landing_url')) + ' ' + tags


def _text(value):
    """Openverse titles and creators arrive as HTML fragments."""
    return re.sub(r'<[^>]+>', '', str(value or '')).replace('&amp;', '&').strip()


def pick_photo(images, blocked, query):
    usable = [item for item in images
              if f"openverse-{item.get('id')}" not in blocked]
    if not usable:
        return None
    return (next((item for item in usable if search_text.matches(query, label(item))), None)
            or usable[0])


def photo_credit(item):
    licence = str(item.get('license') or '').lower()
    version = str(item.get('license_version') or '').strip()
    label = {'cc0': 'CC0', 'pdm': 'Public domain', 'by': 'CC BY'}.get(licence, licence.upper())
    creator = _text(item.get('creator'))
    if creator.lower().startswith(('http://', 'https://')):
        creator = ''
    return {
        'id': f"openverse-{item.get('id')}",
        'photographer': creator or SOURCE_NAME,
        'source_url': item.get('foreign_landing_url') or item.get('detail_url') or '',
        'license': label + (' ' + version if version else ''),
        'license_url': item.get('license_url') or LICENSE_URL,
    }


def photo_link(item):
    return str(item.get('url') or '')
