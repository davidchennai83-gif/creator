"""Wan 2.2 opt-in AI video: graph shape, budget and clip stretching.

No GPU here: the tests cover the things that can silently break a daily render
— the ComfyUI graph we send, the job lifecycle against a stub server, and the
frame mapping that stretches a 2 second clip over a 10-12 second scene.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

from app.config.settings import settings
from app.video_creator import wan


def test_frame_plan_ramps_forward_then_backward():
    plan = wan.frame_plan(5, 10)
    assert plan == [0, 1, 2, 3, 4, 3, 2, 1, 0, 1]


def test_frame_plan_never_exceeds_the_clip():
    plan = wan.frame_plan(49, 300)
    assert len(plan) == 300
    assert min(plan) == 0 and max(plan) == 48


def test_frame_plan_handles_single_frame_clips():
    assert wan.frame_plan(1, 4) == [0, 0, 0, 0]


def test_graph_uses_the_configured_size_and_model(monkeypatch):
    monkeypatch.setattr(settings, 'WAN_WIDTH', 480, raising=False)
    monkeypatch.setattr(settings, 'WAN_HEIGHT', 832, raising=False)
    monkeypatch.setattr(settings, 'WAN_FRAMES', 49, raising=False)
    monkeypatch.setattr(settings, 'WAN_STEPS', 20, raising=False)
    graph = wan.build_graph('a slow camera drift', 'scene-1.png')

    assert graph['8']['class_type'] == 'Wan22ImageToVideoLatent'
    assert graph['8']['inputs']['width'] == 480
    assert graph['8']['inputs']['height'] == 832
    assert graph['8']['inputs']['length'] == 49
    assert graph['8']['inputs']['start_image'] == ['4', 0]
    assert graph['9']['inputs']['steps'] == 20
    assert graph['9']['inputs']['sampler_name'] == 'uni_pc'
    assert graph['4']['inputs']['image'] == 'scene-1.png'
    # SaveImage in this ComfyUI build only accepts these two inputs.
    assert set(graph['11']['inputs']) == {'images', 'filename_prefix'}
    # The official Wan negative prompt blocks burned-in captions.
    assert '字幕' in graph['6']['inputs']['text']


def test_graph_sanitises_a_hand_edited_size_and_length(monkeypatch):
    # Wan 2.2 wants width/height in steps of 32 and 4n+1 frames. A bad .env
    # value must not make every render fail its ComfyUI graph validation.
    monkeypatch.setattr(settings, 'WAN_WIDTH', 500, raising=False)
    monkeypatch.setattr(settings, 'WAN_HEIGHT', 900, raising=False)
    monkeypatch.setattr(settings, 'WAN_FRAMES', 50, raising=False)
    graph = wan.build_graph('prompt', 'scene-1.png')
    assert graph['8']['inputs']['width'] == 480
    assert graph['8']['inputs']['height'] == 896
    assert graph['8']['inputs']['length'] == 49


def test_cancel_interrupts_only_our_running_job(monkeypatch):
    calls = []

    def fake_request(path, payload=None, timeout=30):
        calls.append((path, payload))
        if path == '/queue' and payload is None:
            return {'queue_running': [[0, 'someone-else', {}, {}, []]],
                    'queue_pending': [[1, 'wan-1', {}, {}, []]]}
        return {}

    monkeypatch.setattr(wan, '_request', fake_request)
    wan._cancel('wan-1')
    assert ('/queue', {'delete': ['wan-1']}) in calls
    assert not any(path == '/interrupt' for path, _ in calls)

    calls.clear()
    monkeypatch.setattr(wan, '_request', lambda path, payload=None, timeout=30: (
        calls.append((path, payload)) or
        ({'queue_running': [[0, 'wan-1', {}, {}, []]], 'queue_pending': []}
         if path == '/queue' and payload is None else {})))
    wan._cancel('wan-1')
    assert ('/interrupt', {}) in calls


def test_disabled_by_default_and_fails_soft(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'VIDEO_WAN', False, raising=False)
    monkeypatch.setattr(wan, '_probe', {'checked_at': 0.0, 'ok': False})
    assert wan.available() is False
    assert wan.generate(tmp_path / 'missing.png', 'prompt', tmp_path / 'out.mp4') is False


def test_expand_stretches_a_clip_to_the_scene_length(tmp_path):
    import cv2
    clip = tmp_path / 'wan-1.mp4'
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*'mp4v'), 24, (96, 160))
    for index in range(12):
        frame = np.full((160, 96, 3), index * 20, np.uint8)
        writer.write(frame)
    writer.release()

    out = tmp_path / 'seq'
    assert wan.expand(clip, out, duration=2.0, fps=10, width=108, height=192) is True
    frames = sorted(out.glob('f-*.jpg'))
    assert len(frames) == 20
    first = cv2.imread(str(frames[0]))
    assert first.shape == (192, 108, 3)


def test_expand_reports_failure_for_a_broken_clip(tmp_path):
    broken = tmp_path / 'broken.mp4'
    broken.write_bytes(b'not a video')
    assert wan.expand(broken, tmp_path / 'seq', 2.0, 10, 108, 192) is False


def test_state_reports_the_budget(monkeypatch):
    monkeypatch.setattr(settings, 'VIDEO_WAN', True, raising=False)
    monkeypatch.setattr(settings, 'WAN_SCENES', 1, raising=False)
    monkeypatch.setattr(wan, '_probe', {'checked_at': 0.0, 'ok': False})
    state = wan.state()
    assert state['enabled'] is True
    assert state['scenes'] == 1
    assert 'x' in state['size']
    assert isinstance(state['reachable'], bool)


def test_enabled_for_honours_allow_and_skip_lists(monkeypatch):
    monkeypatch.setattr(settings, 'VIDEO_WAN', True, raising=False)
    monkeypatch.setattr(settings, 'WAN_KINDS', 'history', raising=False)
    monkeypatch.setattr(settings, 'WAN_SKIP_KINDS', 'meesho', raising=False)
    assert wan.enabled_for('History') is True
    assert wan.enabled_for('news') is False

    monkeypatch.setattr(settings, 'WAN_KINDS', '', raising=False)
    assert wan.enabled_for('news') is True
    assert wan.enabled_for('meesho') is False

    monkeypatch.setattr(settings, 'VIDEO_WAN', False, raising=False)
    assert wan.enabled_for('history') is False


def test_generate_against_a_stub_comfyui(tmp_path, monkeypatch):
    """Full job lifecycle: probe, queue, poll, download the PNG batch, encode."""
    import cv2

    image = tmp_path / 'scene-1.png'
    ok, encoded = cv2.imencode('.png', np.full((96, 64, 3), 40, np.uint8))
    assert ok
    png = encoded.tobytes()
    image.write_bytes(png)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body, content_type='application/json'):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith('/system_stats'):
                return self._send(b'{}')
            if self.path.startswith('/queue'):
                return self._send(b'{"queue_running": [], "queue_pending": []}')
            if self.path.startswith('/history/'):
                return self._send(json.dumps({'p1': {
                    'status': {'status_str': 'success', 'completed': True},
                    'outputs': {'11': {'images': [{'filename': 'wan_scene_00001_.png',
                                                   'subfolder': '', 'type': 'output'}]}}}}).encode())
            if self.path.startswith('/view'):
                return self._send(png, 'image/png')
            self.send_error(404)

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length') or 0))
            self._send(b'{"prompt_id": "p1"}')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setattr(settings, 'VIDEO_WAN', True, raising=False)
        monkeypatch.setattr(settings, 'WAN_URL',
                            f'http://127.0.0.1:{server.server_port}', raising=False)
        monkeypatch.setattr(settings, 'WAN_INPUT_DIR', str(tmp_path / 'input'), raising=False)
        monkeypatch.setattr(settings, 'WAN_WIDTH', 64, raising=False)
        monkeypatch.setattr(settings, 'WAN_HEIGHT', 96, raising=False)
        monkeypatch.setattr(settings, 'WAN_FRAMES', 5, raising=False)
        monkeypatch.setattr(settings, 'WAN_TIMEOUT', 30, raising=False)
        monkeypatch.setattr(wan, '_probe', {'checked_at': 0.0, 'ok': False})

        clip = tmp_path / 'wan-1.mp4'
        assert wan.generate(image, 'slow camera drift', clip) is True
        assert clip.exists() and clip.stat().st_size > 0
        # The uploaded scene copy is removed again, not left in ComfyUI/input.
        assert list((tmp_path / 'input').iterdir()) == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
