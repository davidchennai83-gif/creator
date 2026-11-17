"""Real stock footage per scene (Pexels Videos) with a local-LLM search phrase.

The photo pipeline already uses Pexels under a free API key; the same key also
serves portrait video clips, so a scene can be real filmed footage instead of a
Ken Burns still. Two problems are solved here:

* Finding the right clip. History and Thirukkural points carry no English text,
  and the Pexels search needs English nouns. A small local model (Ollama) turns
  the Tamil title and first line into 3-4 concrete things a camera can film.
  Its phrases are cleaned (no numbers, no punctuation) and cached per text.
* Never failing a render. Every step degrades: no Ollama -> kind presets, no
  results -> a simpler query, no clip -> the caller keeps the animated photo.
  A Pexels outage costs a nicer background, not the video.

Downloads are bounded (host allow-list, size cap) and cached by video id, so a
re-render of the same topics does not fetch the same clip twice.
"""
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config.settings import settings
from . import fresh
from . import pixabay
from . import search_text

API = 'https://api.pexels.com/videos/search'

# Last-resort queries when neither the point nor the model gives us one.
KIND_QUERIES = {
    'history': ('ancient temple india', 'historic fort india', 'indian city street',
                'old manuscript paper', 'stone sculpture india'),
    'news': ('india city street', 'newspaper printing press', 'rain clouds city',
             'crowd walking india', 'traffic india'),
    'health': ('fresh vegetables market', 'sleeping bedroom', 'walking park morning',
               'drinking water glass', 'yoga stretching'),
    'motivation': ('sunrise mountain', 'running track morning', 'open notebook desk',
                   'climbing stairs', 'calm ocean waves'),
    'indian-law': ('courthouse building', 'law books shelf', 'indian flag building',
                   'gavel wooden desk', 'documents archive'),
    'make-money': ('laptop work desk', 'coins savings jar', 'delivery scooter city',
                   'market shop india', 'smartphone social media'),
    'meesho': ('clothing shop india', 'fabric textile closeup', 'shopping bags',
               'jewellery closeup', 'home decor shelf'),
    'kids': ('children playing park', 'colourful toys', 'school classroom',
             'kite flying sky', 'cartoon drawing hands'),
    'thirukkural': ('ancient tamil manuscript', 'palm leaf book', 'stone temple carving',
                    'oil lamp flame', 'old library books'),
    'english': ('two people talking', 'student writing notebook', 'classroom blackboard',
                'office meeting conversation', 'reading book closeup'),
    'gk': ('earth from space', 'world map globe', 'telescope night sky',
           'museum dinosaur skeleton', 'microscope laboratory'),
}
GENERIC = ('india city street', 'nature landscape', 'people walking city')

MIN_HEIGHT = 1280
MAX_HEIGHT = 1920          # 1080x1920 is the target; UHD only inflates downloads
MAX_MB = 30


def _cache_dir():
    path = Path(settings.STORAGE_PATH) / 'video_creator' / 'pexels-cache'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _kinds(value):
    return {part.strip().lower() for part in str(value).split(',') if part.strip()}


def _prune_cache(cache, limit_mb=8000):
    """Keep the clip cache under a size cap by dropping the oldest downloads.

    Every day brings new topics, so cached clips accumulate. Search JSON and
    LLM phrases are tiny and stay; only the mp4s are evicted, oldest first.
    """
    clips = sorted(cache.glob('video-*.mp4'), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in clips)
    for path in clips:
        if total <= limit_mb * 1024 * 1024:
            break
        size = path.stat().st_size
        try:
            path.unlink()
            total -= size
        except OSError:
            break


def enabled_for(kind):
    """True when this kind renders real footage instead of animated stills."""
    if str(settings.VIDEO_SOURCE).strip().lower() != 'stock':
        return False
    name = str(kind).strip().lower()
    allowed = _kinds(settings.STOCK_VIDEO_KINDS)
    if allowed and name not in allowed:
        return False
    return name not in _kinds(settings.STOCK_SKIP_KINDS)


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _clean(phrase):
    """LLMs answer with sentences; keep a few concrete lowercase words."""
    words = []
    for token in phrase.replace(',', ' ').replace('.', ' ').split():
        token = token.strip('"\'()[]:;-').lower()
        if not token or not token.isascii() or not token.isalpha():
            continue
        if token in {'the', 'a', 'an', 'of', 'in', 'on', 'with', 'and', 'for', 'to', 'at'}:
            continue
        words.append(token)
        if len(words) == 4:
            break
    return ' '.join(words)


# Words that describe the channel, not the shot. They must never be what makes a
# search result "relevant": "ancient tamil palm leaf manuscript" once matched a
# Tamil festival dance clip through "tamil" alone.
GENERIC = search_text.GENERIC


def _matches(query, video):
    """True when the clip's own Pexels slug describes something we asked for.

    Pexels free-text search is loose: it returns festival dances for manuscript
    queries. The slug (…/video/tamil-festival-dance-123/) is Pexels' own label,
    so requiring one shared meaningful word rejects the worst mismatches, and
    animated/graphics clips are refused because the channel promises real video.
    """
    slug = urlparse(str(video.get('url') or '')).path
    return search_text.footage(slug) and search_text.matches(query, slug)


def _ollama_query(text, cache, timeout=90):
    """English filming phrase for a topic, cached forever (the text is the key)."""
    if not text.strip():
        return ''
    path = cache / f'llm4-{_sha(text)[:24]}.txt'
    try:
        phrase = path.read_text(encoding='utf-8').strip()
        if phrase:
            return phrase
    except OSError:
        pass
    url = (settings.OLLAMA_BASE_URL or 'http://localhost:11434').rstrip('/') + '/api/generate'
    prompt = ('You describe one stock-footage shot for a short video. Given the topic, reply with ONE line of '
              '2-4 English words for what a viewer would SEE on screen, as a simple action or object: '
              '"hands sharing food", "child writing letters", "waves hitting rocks", "salt being harvested". '
              'Name the picture, not the moral or the lesson. No names, no dates, no festival or dance unless '
              'the topic is about it, no punctuation, no second line.\n'
              f'Topic: {text[:240]}\nShot:')
    body = {'model': settings.OLLAMA_MODEL or 'gemma3:4b', 'prompt': prompt, 'stream': False,
            'options': {'temperature': 0.3, 'num_predict': 24}}
    try:
        response = httpx.post(url, json=body, timeout=timeout)
        response.raise_for_status()
        answer = str(response.json().get('response', '')).strip().splitlines()
        phrase = _clean(next((line for line in answer if line.strip()), ''))
    except (httpx.HTTPError, ValueError, KeyError):
        return ''
    if phrase:
        try:
            path.write_text(phrase, encoding='utf-8')
        except OSError:
            pass
    return phrase


# Kinds whose catalogue photo_query is one constant string for every item, so it
# would select the same clip day after day. Their own English title is a better
# description of what each scene is about. (Other catalogue kinds carry a
# different, specific query per item and keep it.)
PER_ITEM_TEXT = {'thirukkural'}


def _topic_text(point):
    """Best English description available for the local model."""
    parts = [str(point.get('title_en') or point.get('title') or '').strip()]
    parts += [str(line).strip() for line in (point.get('lines') or [])[:2]]
    return '. '.join(part for part in parts if part)


def query_for(point, kind, index, cache):
    """What to search, most specific first.

    An explicit per-item ``video_query`` wins. Kinds whose ``photo_query`` is a
    single constant use the local model on the item's own English title instead.
    Otherwise the point's photo query is concrete enough to reuse.
    """
    explicit = str(point.get('video_query') or '').strip()
    if explicit:
        return explicit
    photo_query = str(point.get('photo_query') or '').strip()
    name = str(kind).strip().lower()
    if photo_query and name not in PER_ITEM_TEXT:
        return photo_query if len(photo_query.split()) <= 5 else _clean(photo_query) or photo_query
    phrase = _ollama_query(_topic_text(point), cache)
    if phrase:
        return phrase
    if photo_query:
        return photo_query
    presets = KIND_QUERIES.get(kind, GENERIC)
    return presets[index % len(presets)]


def _search(client, query, cache, key, page=1):
    path = cache / (f'video-{_sha(f"{query}|{page}")[:24]}.json')
    try:
        if time.time() - path.stat().st_mtime < 86400:
            return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    response = client.get(API, headers={'Authorization': key},
                          params={'query': query, 'orientation': 'portrait',
                                  'size': 'medium', 'per_page': 15, 'page': page})
    response.raise_for_status()
    videos = response.json().get('videos', [])
    path.write_text(json.dumps(videos), encoding='utf-8')
    return videos


def _pick(videos, need, used, query=''):
    """Best portrait file for a scene of `need` seconds, as (video, file).

    Only clips whose slug matches the query are eligible, and Pexels' ranking
    stays a tiebreaker behind "long enough to cover the scene": a top-ranked
    12 s clip beats a lower-ranked 10 s one, but a 4 s clip never wins.
    """
    best, best_score = None, None
    for rank, video in enumerate(videos):
        if str(video.get('id')) in used or float(video.get('duration') or 0) < 4:
            continue
        if not _matches(query, video):
            continue
        files = [f for f in video.get('video_files') or []
                 if f.get('file_type') == 'video/mp4' and f.get('width') and f.get('height')
                 and f['width'] < f['height'] and f['height'] >= MIN_HEIGHT]
        if not files:
            continue
        near = [f for f in files if f['height'] <= MAX_HEIGHT] or files
        file = max(near, key=lambda f: f['height'])
        duration = float(video['duration'])
        # A clip long enough to cover the scene comes first, then how much of the
        # query its own label names: one that says "bread" only should lose to
        # one that says "shared meal", even if Pexels ranked it higher.
        detail = search_text.overlap(query, urlparse(str(video.get('url') or '')).path)
        score = (0 if duration >= need else 1, -min(detail, 3), rank, abs(duration - need))
        if best_score is None or score < best_score:
            best, best_score = (video, file), score
    return best


def _download(client, link, cache, video_id):
    host = (urlparse(link).hostname or '').lower()
    if not any(host == name or host.endswith('.' + name)
               for name in ('videos.pexels.com', 'cdn.pixabay.com')):
        raise ValueError('unexpected video host')
    path = cache / f'video-{video_id}.mp4'
    if path.is_file() and path.stat().st_size > 100_000:
        return path
    data = bytearray()
    with client.stream('GET', link) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > MAX_MB * 1024 * 1024:
                raise ValueError(f'clip exceeds {MAX_MB} MB')
    if len(data) < 100_000:
        raise ValueError('clip download too small')
    path.write_bytes(bytes(data))
    return path


def prepare(points, kind, folder, progress, need=None):
    """Download one portrait clip per point.

    Pexels is asked first (largest catalogue, one key also serves photos), then
    Pixabay when it has no fresh matching clip. Returns ``(clips, credits)``
    aligned with ``points``; a slot is ``None`` when no usable footage was found
    and the caller must keep its photo animation.
    """
    key = settings.PEXELS_API_KEY.get_secret_value()
    cache = _cache_dir()
    _prune_cache(cache)
    clips, credits = [], []
    # Ids already used by recent videos stay out, so a fixed query cannot put the
    # same clip in every video for weeks.
    used = {str(asset_id) for asset_id in fresh.recent('video')}
    needs = list(need or [10.0] * len(points))
    # A quota/authorisation failure latches per source: every scene keeps its
    # photo anyway, so retrying the same dead quota only makes the render slower.
    blockers = {
        'pexels': '' if key else 'Pexels key not configured',
        'pixabay': '' if pixabay.configured() else 'Pixabay key not configured',
    }
    with httpx.Client(timeout=httpx.Timeout(20, connect=8), follow_redirects=False) as client:
        for index, point in enumerate(points):
            query = query_for(point, kind, index, cache)
            credits_entry = {'query': query, 'scene': index + 1}
            seconds = needs[index] if index < len(needs) else 10.0
            candidates = [query]
            words = query.split()
            if len(words) > 3:
                candidates.append(' '.join(words[:3]))
            candidates.append(KIND_QUERIES.get(kind, GENERIC)[index % len(KIND_QUERIES.get(kind, GENERIC))])
            found = None
            for provider in ('pexels', 'pixabay'):
                if found or blockers[provider]:
                    continue
                for text in dict.fromkeys(candidates):
                    progress(f'Stock video {index + 1}/{len(points)}: {text}')
                    try:
                        if provider == 'pexels':
                            found = None
                            for page in (1, 2):
                                videos = _search(client, text, cache, key, page=page)
                                found = _pick(videos, seconds, used, text)
                                if found:
                                    break
                        else:
                            found = pixabay.pick_video(pixabay.videos(client, text, cache),
                                                       seconds, used, text)
                    except httpx.HTTPStatusError as exc:
                        found = None
                        if exc.response.status_code in (401, 403, 429):
                            blockers[provider] = ('Pexels' if provider == 'pexels' else 'Pixabay') \
                                + f' unavailable (HTTP {exc.response.status_code})'
                            break
                    except (httpx.HTTPError, ValueError, KeyError):
                        found = None
                    if found:
                        credits_entry['query'] = text
                        break
            if not found:
                # Prefer a real failure over "key not configured": the second
                # message is what actually stopped the search this time.
                reasons = [message for message in blockers.values() if message]
                reason = next((message for message in reasons
                               if 'key not configured' not in message), '')
                credits_entry['video_reason'] = reason or (reasons[0] if reasons else '') \
                    or 'no matching portrait clip'
                clips.append(None)
                credits.append(credits_entry)
                continue
            video, file = found
            try:
                path = _download(client, file['link'], cache, video['id'])
            except (httpx.HTTPError, ValueError, OSError) as exc:
                credits_entry['video_reason'] = f'download failed ({type(exc).__name__})'
                clips.append(None)
                credits.append(credits_entry)
                continue
            used.add(str(video['id']))
            fresh.remember('video', [video['id']])
            clips.append({'path': path, 'duration': float(video['duration']), 'id': video['id']})
            credits_entry.update({
                'provider': video.get('provider', 'pexels'),
                'source_name': video.get('source_name', 'Pexels'),
                'kind': 'video', 'video_id': video['id'],
                'photographer': (video.get('user') or {}).get('name', ''),
                'source_url': video.get('url', ''),
                'license': video.get('license', 'Pexels license — free to use, credited here'),
                'license_url': video.get('license_url', 'https://www.pexels.com/license/'),
            })
            credits.append(credits_entry)
    return clips, credits


def expand(clip, out_dir, seconds, fps, width, height):
    """Decode the clip to the scene's frames (JPEG), looping or slowing as needed.

    The crossfade timeline reads one frame per output frame, so the footage has
    to be exactly ``seconds`` long. A clip shorter than the scene is slowed up to
    1.5x before looping, which hides the seam; longer clips start a little past
    their first second so the shot is already moving.
    """
    import imageio_ffmpeg
    out_dir = Path(out_dir)
    frames = int(round(seconds * fps))
    if frames < 2:
        return False
    duration = max(0.5, float(clip.get('duration') or 0))
    filters = []
    offset = 0.0
    if duration >= seconds:                      # long enough: start inside it
        offset = min(max(0.0, (duration - seconds) * 0.3), duration - seconds)
    elif duration < seconds * 0.72:              # much too short: slow it down first
        factor = min(1.45, seconds / duration)
        filters.append(f'setpts=PTS*{factor:.3f}')
    filters.append(f'fps={fps}')
    filters.append(f'scale={width}:{height}:force_original_aspect_ratio=increase')
    filters.append(f'crop={width}:{height}')
    # Footage is usually brighter and busier than the still photos this replaces,
    # so a gentle grade keeps the Tamil text layer readable on top of it.
    filters.append('eq=brightness=-0.05:contrast=1.04:saturation=1.03')
    filters.append('setsar=1')
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-hide_banner', '-loglevel', 'error',
               '-ss', f'{offset:.2f}', '-stream_loop', '-1', '-i', str(clip['path']),
               '-t', f'{seconds + 1.0:.2f}', '-an', '-sn', '-dn',
               '-vf', ','.join(filters), '-frames:v', str(frames),
               '-q:v', '2', str(out_dir / 'f-%06d.jpg')]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=600)
    written = len(list(out_dir.glob('f-*.jpg')))
    if result.returncode != 0 or written < frames - 2:
        shutil.rmtree(out_dir, ignore_errors=True)
        return False
    return True
