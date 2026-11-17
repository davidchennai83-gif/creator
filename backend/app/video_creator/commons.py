"""Free-licence still images from Wikimedia Commons.

Pexels is good for pretty stock, but its free-text search is loose: a Thirukkural
query could return a festival dance. Commons is a library rather than a stock
site, so a search for "palm leaf manuscript" or "Kanchipuram temple" returns the
actual thing, with its licence and author attached. No API key is needed; only
CC0 / public domain / CC BY material is accepted. NC, ND and BY-SA licences are
refused: the videos are monetised, the frames are cropped, and ShareAlike would
require licensing the whole video under the same terms.
"""
import hashlib
import io
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps

from app.config.settings import settings

API = 'https://commons.wikimedia.org/w/api.php'
USER_AGENT = 'CreatorPlatform/1.0 (https://github.com/davidchennai83-gif/creator) python-httpx'
MAX_MB = 12
BLOCKED = ('nc', 'nd', 'by-sa', 'fair use', 'non-free')


def _cache_dir():
    path = Path(settings.STORAGE_PATH) / 'video_creator' / 'commons-cache'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _text(value):
    """extmetadata values arrive as HTML fragments."""
    return re.sub(r'<[^>]+>', '', str(value or '')).replace('&amp;', '&').strip()


def _licence(metadata):
    short = _text(metadata.get('LicenseShortName', {}).get('value'))
    url = _text(metadata.get('LicenseUrl', {}).get('value'))
    lower = short.lower()
    if not short or any(word in lower for word in BLOCKED):
        return '', ''
    allowed = ('cc0', 'public domain', 'pd-', 'cc by')
    if not any(word in lower for word in allowed) and 'creativecommons.org/licenses/by' not in url:
        return '', ''
    return short, url


def search_images(client, query, cache=None, limit=12):
    """Commons file matches for a query, filtered to reusable licences."""
    cache = cache or _cache_dir()
    path = cache / f'search-{_sha(query)[:24]}.json'
    try:
        if time.time() - path.stat().st_mtime < 86400:
            return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    response = client.get(API, headers={'User-Agent': USER_AGENT}, params={
        'action': 'query', 'format': 'json', 'generator': 'search',
        'gsrsearch': f'filetype:bitmap {query}', 'gsrnamespace': 6, 'gsrlimit': limit,
        'prop': 'imageinfo', 'iiprop': 'url|extmetadata|mime', 'iiurlwidth': 1280,
    })
    response.raise_for_status()
    pages = (response.json().get('query') or {}).get('pages') or {}
    images = []
    for page in pages.values():
        info = (page.get('imageinfo') or [{}])[0]
        if not str(info.get('mime', '')).startswith('image/'):
            continue
        if str(info.get('mime')) in ('image/svg+xml', 'image/gif'):
            continue
        short, url = _licence(info.get('extmetadata') or {})
        if not short:
            continue
        source = info.get('thumburl') or info.get('url') or ''
        if not source.startswith('https://'):
            continue
        images.append({
            'id': f"commons-{page.get('pageid')}",
            'title': _text(page.get('title')),
            'image': source,
            'page': info.get('descriptionurl') or '',
            'license': short,
            'license_url': url,
            'artist': _text(((info.get('extmetadata') or {}).get('Artist') or {}).get('value'))[:80],
        })
    try:
        path.write_text(json.dumps(images), encoding='utf-8')
    except OSError:
        pass
    return images


def download(client, image, cache=None):
    """Fetch the file bytes, host-checked and size-capped."""
    cache = cache or _cache_dir()
    path = cache / f"{image['id']}.jpg"
    if path.is_file() and path.stat().st_size > 20_000:
        return path.read_bytes()
    host = (urlparse(image['image']).hostname or '').lower()
    if host != 'upload.wikimedia.org':
        raise ValueError('unexpected image host')
    data = bytearray()
    with client.stream('GET', image['image'], headers={'User-Agent': USER_AGENT}) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > MAX_MB * 1024 * 1024:
                raise ValueError('image exceeds download limit')
    if len(data) < 5_000:
        raise ValueError('image download too small')
    path.write_bytes(bytes(data))
    return bytes(data)


def portrait(data):
    """Cover-crop to the 1080x1920 output frame so a wide photo fills the scene."""
    with Image.open(io.BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        if image.width * image.height > 40_000_000:
            raise ValueError('image exceeds pixel limit')
        frame = ImageOps.fit(image, (1080, 1920), method=Image.Resampling.LANCZOS)
        output = io.BytesIO()
        frame.save(output, format='JPEG', quality=88)
        return output.getvalue()
