"""Pexels photo backgrounds with bounded downloads and local cache."""
import base64
import hashlib
import io
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps

from app.config.settings import settings
from .backgrounds import illustration

QUERIES = {
    'education': 'library books', 'environment': 'forest river nature',
    'technology': 'computer keyboard', 'health': 'hospital building',
    'family': 'courthouse building', 'consumer': 'shopping supermarket shelves',
    'housing': 'apartment buildings', 'space': 'moon astronomy',
    'aviation': 'airplane airport', 'maritime': 'sailing ship ocean',
    'conflict': 'war memorial monument', 'justice': 'law books justice',
    'history': 'historic architecture monument',
}


def query_for(point, kind, topic):
    title = point.get('title', '').lower()
    if kind == 'indian-law':
        # Use places/objects for sensitive legal topics, rather than depicting a person as a victim/offender.
        if any(word in title for word in ('domestic', 'sexual', 'protection of children')):
            return 'courthouse building'
        if 'senior' in title:
            return 'park bench garden'
        if 'disabilit' in title:
            return 'wheelchair accessibility ramp'
        if 'copyright' in title:
            return 'books library'
        if 'information' in title and 'technology' not in title:
            return 'documents archive'
    return QUERIES[topic]


def _search(client, query, cache, key):
    path = cache / (hashlib.sha256(query.encode()).hexdigest() + '.json')
    try:
        if time.time() - path.stat().st_mtime < 86400:
            return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    response = client.get('https://api.pexels.com/v1/search',
                          headers={'Authorization': key},
                          params={'query': query, 'orientation': 'landscape', 'per_page': 12})
    response.raise_for_status()
    photos = response.json()['photos']
    path.write_text(json.dumps(photos), encoding='utf-8')
    return photos


def _image(client, photo, cache):
    photo_id = int(photo['id'])
    path = cache / f'pexels-{photo_id}.jpg'
    if path.is_file():
        return path.read_bytes()
    url = photo['src']['large2x']
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'images.pexels.com':
        raise ValueError('Unexpected photo host')
    data = bytearray()
    # Authorization is sent only to the API, never to an image CDN.
    with client.stream('GET', url) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > 12 * 1024 * 1024:
                raise ValueError('Photo exceeds download limit')
    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > 24_000_000:
            raise ValueError('Photo exceeds pixel limit')
        image = ImageOps.exif_transpose(image).convert('RGB')
        image = ImageOps.fit(image, (1280, 720), method=Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=88)
    path.write_bytes(output.getvalue())
    return output.getvalue()


def prepare_backgrounds(points, kind, folder, progress):
    folder = Path(folder)
    key = settings.PEXELS_API_KEY.get_secret_value()
    cache = Path(settings.STORAGE_PATH) / 'video_creator' / 'pexels-cache'
    backgrounds, credits, used = [], [], set()
    if key:
        cache.mkdir(parents=True, exist_ok=True)
    disabled_reason = 'Pexels key not configured' if not key else ''
    with httpx.Client(timeout=httpx.Timeout(12, connect=5), follow_redirects=False) as client:
        for index, point in enumerate(points):
            fallback = illustration(point, kind, index)
            query = query_for(point, kind, fallback['topic'])
            background = dict(fallback, provider='illustration')
            credit = {'scene': index + 1, 'provider': 'illustration', 'query': query}
            progress(f'Background photo {index + 1}/{len(points)}: {query}')
            try:
                if disabled_reason:
                    raise ValueError(disabled_reason)
                photos = _search(client, query, cache, key)
                photo = next((p for p in photos if p['id'] not in used), None)
                if not photo:
                    raise ValueError('No unused matching photo')
                image = _image(client, photo, cache)
                used.add(photo['id'])
                background.update(provider='pexels', image='data:image/jpeg;base64,' + base64.b64encode(image).decode(),
                                  photographer=photo['photographer'])
                credit.update(provider='pexels', photo_id=photo['id'], photographer=photo['photographer'],
                              source_url=photo['url'], photographer_url=photo.get('photographer_url', ''),
                              license_url='https://www.pexels.com/license/')
            except (httpx.HTTPError, ValueError, KeyError, OSError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (401, 403, 429):
                    disabled_reason = f'Pexels unavailable (HTTP {exc.response.status_code})'
                elif isinstance(exc, httpx.RequestError):
                    disabled_reason = 'Pexels network unavailable'
                credit['fallback_reason'] = disabled_reason or 'No usable stock photo for this scene'
                progress(f"Scene {index + 1}: {credit['fallback_reason']}; using illustration")
            backgrounds.append(background)
            credits.append(credit)
    (folder / 'media-sources.json').write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding='utf-8')
    return backgrounds
