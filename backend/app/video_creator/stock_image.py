"""Download and frame one stock still without trusting the network.

Every free photo library hands back a CDN link, and a CDN link is untrusted
input: it can point at localhost, at a different site, or at a 200 MB original.
The providers in this package (Pixabay, Unsplash, Openverse) all need the same
three checks, so they share them here: an https host allow-list, a size cap and
a pixel cap. The frame is cover-cropped to the 1080x1920 output, which is also
where EXIF rotation is applied — a portrait photo taken sideways is otherwise
pasted in rotated.
"""
import io
from urllib.parse import urlparse

from PIL import Image, ImageOps

WIDTH, HEIGHT = 1080, 1920
MAX_MB = 20
MAX_PIXELS = 40_000_000
# Wikimedia's image hosts (and Openverse results served from them) answer 403 to
# a generic or missing agent, so every download identifies the project.
USER_AGENT = 'CreatorPlatform/1.0 (https://github.com/davidchennai83-gif/creator) python-httpx'


def allowed(url, hosts):
    """True when `url` is https and its host is (a subdomain of) an allow-listed host."""
    parsed = urlparse(str(url or ''))
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or not host:
        return False
    return any(host == name or host.endswith('.' + name) for name in hosts)


def download(client, url, hosts, limit_mb=MAX_MB, headers=None):
    """Bytes of an image from an allow-listed host, capped at `limit_mb`."""
    if not allowed(url, hosts):
        raise ValueError(f'unexpected image host: {urlparse(str(url)).hostname}')
    data = bytearray()
    headers = dict(headers or {}, **{'User-Agent': USER_AGENT})
    with client.stream('GET', url, headers=headers) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > limit_mb * 1024 * 1024:
                raise ValueError('image exceeds download limit')
    if len(data) < 5_000:
        raise ValueError('image download too small')
    return bytes(data)


def portrait(data, width=WIDTH, height=HEIGHT):
    """Cover-crop to the portrait output frame and re-encode as JPEG."""
    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError('image exceeds pixel limit')
        image = ImageOps.exif_transpose(image).convert('RGB')
        frame = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
        output = io.BytesIO()
        frame.save(output, format='JPEG', quality=88)
        return output.getvalue()
