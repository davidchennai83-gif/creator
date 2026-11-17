import json
import subprocess

import httpx
import pytest
from pydantic import SecretStr

from app.video_creator import stock_video as stock


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setattr(stock.settings, 'STORAGE_PATH', str(tmp_path))
    monkeypatch.setattr(stock.settings, 'PEXELS_API_KEY', SecretStr('test-secret'))
    monkeypatch.setattr(stock.settings, 'VIDEO_SOURCE', 'stock')
    monkeypatch.setattr(stock.settings, 'STOCK_VIDEO_KINDS', '')
    monkeypatch.setattr(stock.settings, 'STOCK_SKIP_KINDS', 'meesho,news')
    monkeypatch.setattr(stock.settings, 'STOCK_REUSE_DAYS', 21)
    # Optional extras stay off unless a test asks for them.
    monkeypatch.setattr(stock.settings, 'PIXABAY_API_KEY', SecretStr(''))
    monkeypatch.setattr(stock.settings, 'UNSPLASH_ACCESS_KEY', SecretStr(''))
    monkeypatch.setattr(stock.settings, 'OPENVERSE_TOKEN', SecretStr(''))
    # The local model is optional: a deterministic phrase keeps the test offline.
    monkeypatch.setattr(stock, '_ollama_query', lambda text, cache, timeout=90: 'ancient temple india')
    return tmp_path


def transport(monkeypatch, handler):
    client = httpx.Client
    monkeypatch.setattr(stock.httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))


def video(video_id, duration=20, width=1080, height=1920, host='videos.pexels.com', slug='ancient-temple'):
    return {
        'id': video_id, 'duration': duration, 'user': {'name': f'Filmer {video_id}'},
        'url': f'https://www.pexels.com/video/{slug}-{video_id}/',
        'video_files': [{'file_type': 'video/mp4', 'width': width, 'height': height,
                         'link': f'https://{host}/video-files/{video_id}.mp4'}],
    }


def test_source_setting_gates_footage(configured, monkeypatch):
    assert stock.enabled_for('history') is True
    assert stock.enabled_for('meesho') is False     # product photos must stay
    assert stock.enabled_for('news') is False       # publisher photo is better
    monkeypatch.setattr(stock.settings, 'STOCK_VIDEO_KINDS', 'history')
    assert stock.enabled_for('health') is False
    monkeypatch.setattr(stock.settings, 'VIDEO_SOURCE', 'photos')
    assert stock.enabled_for('history') is False


def test_clean_keeps_only_concrete_words():
    assert stock._clean('Sleep, night, 7 hours of darkness.') == 'sleep night hours darkness'


def test_unrelated_slug_is_not_a_match():
    festival = video(5, slug='vibrant-tamil-hindu-festival-celebration')
    assert stock._matches('ancient tamil palm leaf manuscript', festival) is False
    assert stock._matches('ancient tamil palm leaf manuscript', video(6, slug='old-palm-leaf-manuscript')) is True


def test_a_visual_adjective_alone_is_not_a_match():
    # "glowing" is how the shot looks; "script" is what it must show.
    assert stock._matches('ancient script glowing softly', video(7, slug='3d-render-glowing-lines')) is False
    assert stock._matches('ancient script glowing softly', video(8, slug='hand-writing-script-on-paper')) is True


def test_motion_graphics_are_not_footage():
    assert stock._matches('glowing script', video(9, slug='a-3d-animation-of-a-glowing-geometric-design')) is False
    assert stock._matches('glowing script', video(10, slug='glowing-script-on-stone')) is True


def test_pick_prefers_portrait_and_skips_used():
    videos = [
        video(1, width=1920, height=1080),        # landscape: unusable
        video(2, duration=6),                     # too short for a 10 s scene
        video(3),
        video(4),
    ]
    chosen = stock._pick(videos, 10.0, used=set(), query='temple')
    assert chosen[0]['id'] == 3
    assert stock._pick(videos, 10.0, used={'3'}, query='temple')[0]['id'] == 4


def test_pick_keeps_search_ranking_between_long_enough_clips():
    videos = [video(1, duration=25), video(2, duration=12)]
    assert stock._pick(videos, 10.0, used=set(), query='temple')[0]['id'] == 1


def test_prepare_downloads_caches_and_credits(configured, monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.host == 'api.pexels.com':
            assert request.headers['Authorization'] == 'test-secret'
            return httpx.Response(200, json={'videos': [video(7)]})
        assert 'authorization' not in request.headers
        return httpx.Response(200, content=b'\0' * 200_000)

    transport(monkeypatch, handle)
    clips, credits = stock.prepare([{'title': 'தமிழ்'}], 'history', configured, lambda _: None)
    assert clips[0]['id'] == 7 and clips[0]['path'].is_file()
    assert credits[0]['video_id'] == 7 and credits[0]['provider'] == 'pexels'
    assert 'test-secret' not in json.dumps(credits)

    stock.prepare([{'title': 'தமிழ்'}], 'history', configured, lambda _: None)
    assert len(requests) <= 3  # Search JSON and clip are reused, not refetched.


def test_a_scene_that_keeps_its_publisher_photo_is_skipped(configured, monkeypatch):
    """News/cinema scenes keep the story's own photo; no clip is fetched for them."""
    requests = []

    def handle(request):
        requests.append(str(request.url))
        if request.url.host == 'api.pexels.com':
            return httpx.Response(200, json={'videos': [video(21)]})
        return httpx.Response(200, content=b'\0' * 200_000)

    transport(monkeypatch, handle)
    points = [{'title': 'A', 'photo_query': 'newspaper headlines'}, {'title': 'B'}]
    clips, credits = stock.prepare(points, 'cinema', configured, lambda _: None, skip={0})
    assert clips[0] is None
    assert credits[0]['video_reason'] == 'the story keeps its own publisher photo'
    assert credits[0]['scene'] == 1
    assert clips[1]['id'] == 21
    # Only the second scene was searched for.
    assert sum(1 for url in requests if 'api.pexels.com' in url) == 1


def test_recent_video_is_not_reused(configured, monkeypatch):
    def handle(request):
        if request.url.host == 'api.pexels.com':
            return httpx.Response(200, json={'videos': [video(11), video(12)]})
        return httpx.Response(200, content=b'\0' * 200_000)
    transport(monkeypatch, handle)
    first = stock.prepare([{'title': 'A'}], 'history', configured, lambda _: None)[0][0]
    second = stock.prepare([{'title': 'A'}], 'history', configured, lambda _: None)[0][0]
    assert first['id'] != second['id']


@pytest.mark.parametrize('status', [401, 403, 429])
def test_quota_stops_requests_and_falls_back(configured, monkeypatch, status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={})

    transport(monkeypatch, handle)
    clips, credits = stock.prepare([{'title': 'A'}, {'title': 'B'}], 'history', configured, lambda _: None)
    assert clips == [None, None]
    assert credits[0]['video_reason'].startswith('Pexels unavailable')
    assert len(calls) == 1


def test_untrusted_clip_host_is_rejected(configured, monkeypatch):
    def handle(request):
        if request.url.host == 'api.pexels.com':
            return httpx.Response(200, json={'videos': [video(9, host='127.0.0.1')]})
        raise AssertionError('untrusted host must never be fetched')

    transport(monkeypatch, handle)
    clips, credits = stock.prepare([{'title': 'A'}], 'history', configured, lambda _: None)
    assert clips == [None]
    assert 'download failed' in credits[0]['video_reason']


def test_pixabay_clip_is_used_when_pexels_has_none(configured, monkeypatch):
    monkeypatch.setattr(stock.settings, 'PIXABAY_API_KEY', SecretStr('pb-key'))

    def handle(request):
        if request.url.host == 'api.pexels.com':
            return httpx.Response(200, json={'videos': []})
        if request.url.host == 'pixabay.com':
            assert request.url.params['key'] == 'pb-key'
            assert request.url.path == '/api/videos/'
            return httpx.Response(200, json={'hits': [{
                'id': 9, 'duration': 30, 'user': 'PB Filmer', 'tags': 'ancient temple ruins',
                'pageURL': 'https://pixabay.com/videos/id-9/',
                'videos': {'large': {'url': 'https://cdn.pixabay.com/video/9.mp4',
                                     'width': 1080, 'height': 1920}}}]})
        assert request.url.host == 'cdn.pixabay.com'
        return httpx.Response(200, content=b'\0' * 200_000)

    transport(monkeypatch, handle)
    clips, credits = stock.prepare([{'title': 'A'}], 'history', configured, lambda _: None)
    assert clips[0]['id'] == 'pixabay-9' and clips[0]['path'].is_file()
    assert credits[0]['provider'] == 'pixabay'
    assert credits[0]['source_name'] == 'Pixabay'
    assert credits[0]['video_id'] == 'pixabay-9'
    assert 'pb-key' not in json.dumps(credits)


def test_pexels_quota_still_lets_pixabay_answer(configured, monkeypatch):
    """A dead Pexels quota must not also lose the Pixabay catalogue."""
    monkeypatch.setattr(stock.settings, 'PIXABAY_API_KEY', SecretStr('pb-key'))

    def handle(request):
        if request.url.host == 'api.pexels.com':
            return httpx.Response(429, json={})
        if request.url.host == 'pixabay.com':
            return httpx.Response(200, json={'hits': [{
                'id': 3, 'duration': 30, 'user': 'PB Filmer', 'tags': 'ancient temple ruins',
                'pageURL': 'https://pixabay.com/videos/id-3/',
                'videos': {'large': {'url': 'https://cdn.pixabay.com/video/3.mp4',
                                     'width': 1080, 'height': 1920}}}]})
        return httpx.Response(200, content=b'\0' * 200_000)

    transport(monkeypatch, handle)
    clips, credits = stock.prepare([{'title': 'A'}], 'history', configured, lambda _: None)
    assert clips[0]['id'] == 'pixabay-3'
    assert credits[0]['provider'] == 'pixabay'


def test_expand_writes_exact_scene_frames(tmp_path):
    import imageio_ffmpeg

    clip = tmp_path / 'source.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-v', 'error',
                    '-f', 'lavfi', '-i', 'testsrc=size=540x960:rate=24:duration=1',
                    '-pix_fmt', 'yuv420p', str(clip)], check=True, timeout=120)
    out = tmp_path / 'seq-0'
    assert stock.expand({'path': clip, 'duration': 1.0}, out, 1.0, 10, 1080, 1920)
    frames = sorted(out.glob('f-*.jpg'))
    assert len(frames) == 10
