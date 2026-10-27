"""Pexels photo backgrounds with bounded downloads and local cache."""
import base64
import binascii
import hashlib
import io
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

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
    # Daily news fallbacks (used only when the story's own feed image cannot be
    # downloaded): the picture illustrates the topic, never a named person.
    'news': 'newspaper headlines', 'globe': 'world map globe',
    # How to Make Money topics
    'pen': 'writing notebook desk', 'laptop': 'laptop work desk', 'play': 'video editing computer',
    'mic': 'podcast microphone studio', 'camera': 'photographer camera', 'coin': 'coins savings',
    'chart': 'growth chart laptop', 'food': 'south indian food meals', 'craft': 'handmade crafts',
    'delivery': 'delivery scooter city', 'wrench': 'mobile phone repair', 'phone': 'smartphone social media',
    'warning': 'warning sign', 'wallet': 'wallet savings',
    # Catalogue kinds (Thirukkural / Spoken English / Amazing Facts)
    'book': 'ancient tamil palm leaf manuscript', 'chat': 'two people talking conversation',
    'globe': 'earth from space planet',
}


def query_for(point, kind, topic):
    title = point.get('title', '').lower()
    if kind == 'make-money':
        # Objects and places only; scam topics never show a person as a victim.
        return point.get('photo_query') or QUERIES[topic]
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
    # Catalogue kinds carry their own per-item photo query; History has none.
    return point.get('photo_query') or QUERIES[topic]


def _search(client, query, cache, key):
    path = cache / (hashlib.sha256(query.encode()).hexdigest() + '.json')
    try:
        if time.time() - path.stat().st_mtime < 86400:
            return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    response = client.get('https://api.pexels.com/v1/search',
                          headers={'Authorization': key},
                          params={'query': query, 'orientation': 'portrait', 'per_page': 12})
    response.raise_for_status()
    photos = response.json()['photos']
    path.write_text(json.dumps(photos), encoding='utf-8')
    return photos


def _product_image(client, value, cache):
    """Return a clean square JPEG for a Meesho product image.

    Accepts a data URI (used by the offline demo catalogue) or a public HTTPS
    image URL. Network images go through the same SSRF guard as the store and
    are size/pixel limited. Any failure is non-fatal: the scene falls back to a
    stock photo or a local illustration.
    """
    value = str(value or "").strip()
    if not value:
        return None
    if value.startswith("data:image/"):
        try:
            header, payload = value.split(",", 1)
            if ";base64" in header:
                data = base64.b64decode(payload)
            else:
                from urllib.parse import unquote_to_bytes
                data = unquote_to_bytes(payload)
        except (ValueError, TypeError, binascii.Error):
            return None
    elif value.startswith("https://"):
        try:
            from app.store import _is_public_http_url
            if not _is_public_http_url(value):
                return None
        except Exception:
            return None
        path = cache / (hashlib.sha256(value.encode()).hexdigest() + ".product")
        if path.is_file():
            data = path.read_bytes()
        else:
            data = bytearray()
            try:
                with client.stream("GET", value, follow_redirects=True) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if content_type and not content_type.startswith("image/"):
                        raise ValueError("Product URL is not an image")
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > 12 * 1024 * 1024:
                            raise ValueError("Product image exceeds download limit")
            except (httpx.HTTPError, ValueError, OSError):
                return None
            data = bytes(data)
            path.write_bytes(data)
    else:
        return None
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 24_000_000:
                raise ValueError("Product image exceeds pixel limit")
            image = ImageOps.exif_transpose(image).convert("RGB")
            image = ImageOps.contain(image, (1080, 1080), method=Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (1080, 1080), (248, 250, 252))
            canvas.paste(image, ((1080 - image.width) // 2, (1080 - image.height) // 2))
            output = io.BytesIO()
            canvas.save(output, format="JPEG", quality=90)
            return output.getvalue()
    except (OSError, ValueError):
        return None


def _feed_image(client, value, cache):
    """Portrait 1080x1920 frame from a publisher's RSS lead image.

    The photo is shown whole over a blurred, darkened fill of itself, so a wide
    16:9 news photo is not cropped to a thin centre strip and no solid card is
    added. Same SSRF/size/pixel guards as the product image; any failure falls
    back to a stock photo or a local illustration.
    """
    value = str(value or "").strip()
    if not value.startswith("https://"):
        return None
    try:
        from app.store import _is_public_http_url
        if not _is_public_http_url(value):
            return None
    except Exception:
        return None
    path = cache / (hashlib.sha256(value.encode()).hexdigest() + ".news")
    if path.is_file():
        data = path.read_bytes()
    else:
        data = bytearray()
        try:
            with client.stream("GET", value, follow_redirects=True) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type and not content_type.startswith("image/"):
                    raise ValueError("Feed URL is not an image")
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 12 * 1024 * 1024:
                        raise ValueError("Feed image exceeds download limit")
        except (httpx.HTTPError, ValueError, OSError):
            return None
        data = bytes(data)
        path.write_bytes(data)
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 24_000_000:
                raise ValueError("Feed image exceeds pixel limit")
            image = ImageOps.exif_transpose(image).convert("RGB")
            fill = ImageOps.fit(image, (1080, 1920), method=Image.Resampling.LANCZOS)
            fill = fill.filter(ImageFilter.GaussianBlur(28))
            fill = ImageEnhance.Brightness(fill).enhance(0.62)
            photo = ImageOps.contain(image, (1040, 1000), method=Image.Resampling.LANCZOS)
            fill.paste(photo, ((1080 - photo.width) // 2, int(1920 * 0.46) - photo.height // 2))
            output = io.BytesIO()
            fill.save(output, format="JPEG", quality=88)
            return output.getvalue()
    except (OSError, ValueError):
        return None


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
        image = ImageOps.fit(image, (1080, 1920), method=Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=88)
    path.write_bytes(output.getvalue())
    return output.getvalue()


def prepare_backgrounds(points, kind, folder, progress):
    folder = Path(folder)
    key = settings.PEXELS_API_KEY.get_secret_value()
    cache = Path(settings.STORAGE_PATH) / 'video_creator' / 'pexels-cache'
    backgrounds, credits, used = [], [], set()
    cache.mkdir(parents=True, exist_ok=True)
    disabled_reason = 'Pexels key not configured' if not key else ''
    with httpx.Client(timeout=httpx.Timeout(12, connect=5), follow_redirects=False) as client:
        for index, point in enumerate(points):
            fallback = illustration(point, kind, index)
            query = query_for(point, kind, fallback['topic'])
            if kind == 'news' and point.get('image_url'):
                progress(f'News photo {index + 1}/{len(points)}')
                feed_image = _feed_image(client, point.get('image_url'), cache)
                if feed_image:
                    backgrounds.append({
                        'topic': fallback['topic'], 'provider': 'feed',
                        'image': 'data:image/jpeg;base64,' + base64.b64encode(feed_image).decode(),
                    })
                    credits.append({'scene': index + 1, 'provider': 'feed',
                                    'publisher': point.get('source_name', ''),
                                    'source_url': point.get('source_url', ''),
                                    'query': 'RSS lead image',
                                    'license': 'Publisher RSS image — credited on screen and in the description'})
                    continue
                progress(f'Scene {index + 1}: feed image unavailable; using a stock/illustrated background')
            if kind == 'meesho' and point.get('image_url'):
                progress(f'Product image {index + 1}/{len(points)}')
                product_image = _product_image(client, point.get('image_url'), cache)
                if product_image:
                    backgrounds.append({
                        'topic': 'consumer', 'provider': 'product',
                        'image': 'data:image/jpeg;base64,' + base64.b64encode(product_image).decode(),
                    })
                    credits.append({'scene': index + 1, 'provider': 'product',
                                    'query': 'product image', 'license': 'Product catalogue image'})
                    continue
                progress(f'Scene {index + 1}: product image unavailable; using a stock/illustrated background')
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
