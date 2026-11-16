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
    # The local model is optional: a deterministic phrase keeps the test offline.
    monkeypatch.setattr(stock, '_ollama_query', lambda text, cache, timeout=90: 'ancient temple india')
    return tmp_path


def transport(monkeypatch, handler):
    client = httpx.Client
    monkeypatch.setattr(stock.httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))


def video(video_id, duration=20, width=1080, height=1920, host='videos.pexels.com'):
    return {
        'id': video_id, 'duration': duration, 'user': {'name': f'Filmer {video_id}'},
        'url': f'https://www.pexels.com/video/clip-{video_id}/',
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


def test_pick_prefers_portrait_and_skips_used():
    videos = [
        video(1, width=1920, height=1080),        # landscape: unusable
        video(2, duration=6),                     # too short for a 10 s scene
        video(3),
        video(4),
    ]
    chosen = stock._pick(videos, 10.0, used=set())
    assert chosen[0]['id'] == 3
    assert stock._pick(videos, 10.0, used={3})[0]['id'] == 4


def test_pick_keeps_search_ranking_between_long_enough_clips():
    videos = [video(1, duration=25), video(2, duration=12)]
    assert stock._pick(videos, 10.0, used=set())[0]['id'] == 1


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
    assert len(requests) == 2  # Search JSON and clip are reused, not refetched.


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
