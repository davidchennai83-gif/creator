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
from . import commons
from . import fresh
from . import openverse
from . import pixabay
from . import search_text
from . import stock_image
from . import unsplash
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


def _search(client, query, cache, key, page=1):
    path = cache / (hashlib.sha256(f'{query}|{page}'.encode()).hexdigest() + '.json')
    try:
        if time.time() - path.stat().st_mtime < 86400:
            return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    response = client.get('https://api.pexels.com/v1/search',
                          headers={'Authorization': key},
                          params={'query': query, 'orientation': 'portrait', 'per_page': 12,
                                  'page': page})
    response.raise_for_status()
    photos = response.json()['photos']
    path.write_text(json.dumps(photos), encoding='utf-8')
    return photos


def _pick_photo(photos, blocked, query):
    """First unused photo that describes the query, else one with no alt text.

    ``alt`` is Pexels' own description of the picture, so it is a reliable label
    for rejecting a loose match without needing a vision model. A photo labelled
    something else is skipped rather than shown: an unrelated picture is the
    complaint this pipeline exists to fix.
    """
    unused = [photo for photo in photos if str(photo.get('id')) not in blocked]
    return (next((p for p in unused if search_text.matches(query, p.get('alt'))), None)
            or next((p for p in unused if not str(p.get('alt') or '').strip()), None))


SOURCE_NAMES = {
    'pexels': 'Pexels', 'pixabay': 'Pixabay', 'unsplash': 'Unsplash',
    'openverse': 'Openverse', 'commons': 'Wikimedia Commons',
}
# Order matters: catalogues with strong hand-written labels come first, and the
# broad keyless aggregator comes last because its anonymous quota is tiny.
PHOTO_SOURCES = ('pexels', 'pixabay', 'unsplash', 'openverse', 'commons')
PEXELS_LICENSE = 'Pexels license — free to use, credited here'


def _entry(provider, **fields):
    """One normalised record for every provider, so the caller stays generic."""
    return dict(fields, provider=provider, source_name=SOURCE_NAMES[provider])


def _pexels_scene(client, query, cache, key, blocked, disabled_reason):
    """(entry, jpeg bytes) from Pexels, or ValueError explaining why not."""
    if disabled_reason:
        raise ValueError(disabled_reason)
    # Page 2 is fetched only when page 1 has nothing usable (all used or all
    # unrelated), because every page costs one request from a small hourly quota.
    photos = _search(client, query, cache, key, page=1)
    photo = _pick_photo(photos, blocked, query)
    if not photo:
        photos += _search(client, query, cache, key, page=2)
        photo = _pick_photo(photos, blocked, query)
    if not photo:
        raise ValueError('No unused matching photo')
    return _entry('pexels', id=photo['id'], photographer=photo.get('photographer', ''),
                  source_url=photo.get('url', ''),
                  license=PEXELS_LICENSE,
                  license_url='https://www.pexels.com/license/'), _image(client, photo, cache)


def _pixabay_scene(client, query, cache, blocked):
    """(entry, jpeg bytes) from Pixabay, or ValueError."""
    hit = pixabay.pick_photo(pixabay.photos(client, query), blocked, query)
    if not hit:
        raise ValueError('No unused Pixabay photo')
    data = stock_image.download(client, pixabay.photo_link(hit), pixabay.CDN_HOSTS)
    return _entry('pixabay', **pixabay.photo_credit(hit)), stock_image.portrait(data)


def _unsplash_scene(client, query, cache, blocked):
    """(entry, jpeg bytes) from Unsplash, or ValueError."""
    if not unsplash.configured():
        raise ValueError('Unsplash key not configured')
    photo = unsplash.pick_photo(unsplash.search(client, query), blocked, query)
    if not photo:
        raise ValueError('No unused Unsplash photo')
    data = stock_image.download(client, unsplash.photo_link(photo), unsplash.CDN_HOSTS)
    return _entry('unsplash', **unsplash.photo_credit(photo)), stock_image.portrait(data)


def _openverse_scene(client, query, cache, blocked):
    """(entry, jpeg bytes) from Openverse, or ValueError.

    Openverse sources live on many hosts, so a fixed allow-list cannot apply;
    the URL must pass the project's public-address guard instead, and only that
    one validated host is allowed for the download.
    """
    item = openverse.pick_photo(openverse.search(client, query), blocked, query)
    if not item:
        raise ValueError('No unused Openverse image')
    link = openverse.photo_link(item)
    from app.store import _is_public_http_url
    if not _is_public_http_url(link):
        raise ValueError('Openverse returned a non-public image URL')
    data = stock_image.download(client, link, ((urlparse(link).hostname or '').lower(),))
    return _entry('openverse', **openverse.photo_credit(item)), stock_image.portrait(data)


def _commons_scene(client, query, cache, blocked):
    """(entry, 1080x1920 jpeg) from Wikimedia Commons, or ValueError."""
    images = commons.search_images(client, query, cache)
    # Commons file names always describe the object, so a title that names none
    # of the query words is the loose-search case that produced the off-topic
    # backgrounds; the topic illustration is a better result than that.
    image = next((item for item in images if str(item['id']) not in blocked
                  and search_text.matches(query, item['title'])), None)
    if not image:
        raise ValueError('No matching free-licence Commons image')
    return (_entry('commons', id=image['id'],
                   photographer=image['artist'] or SOURCE_NAMES['commons'],
                   source_url=image['page'],
                   license=image['license'],
                   license_url=image['license_url']),
            commons.portrait(commons.download(client, image, cache)))


def _scene_from(provider, client, query, cache, key, blocked, blockers):
    if provider == 'pexels':
        return _pexels_scene(client, query, cache, key, blocked, blockers.get('pexels', ''))
    if provider == 'pixabay':
        return _pixabay_scene(client, query, cache, blocked)
    if provider == 'unsplash':
        return _unsplash_scene(client, query, cache, blocked)
    if provider == 'openverse':
        return _openverse_scene(client, query, cache, blocked)
    return _commons_scene(client, query, cache, blocked)


def _note_failure(blockers, provider, exc):
    """Remember a source that is out of quota or offline, so later scenes skip it."""
    name = SOURCE_NAMES.get(provider, provider)
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403, 429):
            blockers[provider] = f'{name} unavailable (HTTP {status})'
    elif isinstance(exc, httpx.RequestError):
        blockers[provider] = f'{name} network unavailable'


def _reason(provider, exc):
    """One plain sentence for the review screen, never a traceback."""
    name = SOURCE_NAMES.get(provider, provider)
    if isinstance(exc, httpx.HTTPStatusError):
        return f'{name} unavailable (HTTP {exc.response.status_code})'
    if isinstance(exc, httpx.RequestError):
        return f'{name} network unavailable'
    message = str(exc).strip()
    return f'{name}: {message}' if message else f'{name} returned nothing usable'


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
    # One blocker per source: a 429/401 stops that source for the rest of the
    # render instead of spending a request per scene on a dead quota.
    blockers = {
        'pexels': 'Pexels key not configured' if not key else '',
        'pixabay': '' if pixabay.configured() else 'Pixabay key not configured',
        'unsplash': '' if unsplash.configured() else 'Unsplash key not configured',
        'openverse': '', 'commons': '',
    }
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
            blocked = {str(asset_id) for asset_id in used} | fresh.recent('photo')
            image, last_error = None, ''
            for provider_name in PHOTO_SOURCES:
                if blockers.get(provider_name):
                    continue
                try:
                    found, image = _scene_from(provider_name, client, query, cache, key,
                                               blocked, blockers)
                except (httpx.HTTPError, ValueError, KeyError, OSError) as exc:
                    _note_failure(blockers, provider_name, exc)
                    last_error = _reason(provider_name, exc)
                    continue
                used.add(str(found['id']))
                fresh.remember('photo', [found['id']])
                background.update(provider=found['provider'], image='data:image/jpeg;base64,'
                                  + base64.b64encode(image).decode(),
                                  photographer=found['photographer'],
                                  source_name=found['source_name'])
                credit.update(provider=found['provider'], photo_id=found['id'],
                              photographer=found['photographer'],
                              source_url=found['source_url'],
                              license=found['license'],
                              license_url=found['license_url'])
                break
            if image is None:
                credit['fallback_reason'] = last_error or 'No free-licence photo matched this scene'
                progress(f"Scene {index + 1}: {credit['fallback_reason']}; using illustration")
            backgrounds.append(background)
            credits.append(credit)
    (folder / 'media-sources.json').write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding='utf-8')
    return backgrounds
