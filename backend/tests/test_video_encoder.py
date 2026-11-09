"""Encoder selection: hardware path when it works, and a safe software fallback.

CI and this dev box differ (some machines have no NVIDIA card at all), so the
tests assert the contract — coherent argument sets and a working fallback —
instead of assuming NVENC is present.
"""
import pytest

from app.video_creator import encoder
from app.config.settings import settings


@pytest.fixture(autouse=True)
def reset_probe(monkeypatch):
    monkeypatch.setattr(encoder, '_nvenc', None)
    monkeypatch.setattr(encoder, '_reason', '')
    yield


def test_args_match_label(monkeypatch):
    monkeypatch.setattr(encoder, '_nvenc', True)
    args, label = encoder.video_args()
    assert label == 'nvenc'
    assert 'h264_nvenc' in args and 'libx264' not in args

    monkeypatch.setattr(encoder, '_nvenc', False)
    args, label = encoder.video_args()
    assert label == 'x264'
    assert 'libx264' in args and 'h264_nvenc' not in args
    assert 'yuv420p' in args


def test_forced_x264_skips_probe(monkeypatch):
    monkeypatch.setattr(settings, 'VIDEO_ENCODER', 'x264')
    assert encoder.nvenc_ready() is False
    assert encoder.video_args()[1] == 'x264'


def test_disable_nvenc_latches_software(monkeypatch):
    monkeypatch.setattr(encoder, '_nvenc', True)
    encoder.disable_nvenc()
    assert encoder.nvenc_ready() is False
    assert encoder.video_args()[1] == 'x264'


def test_state_reports_encoder_and_gpu():
    state = encoder.state()
    assert state['encoder'] in ('h264_nvenc', 'libx264')
    assert state['hardware'] is (state['encoder'] == 'h264_nvenc')
    assert 'gpu' in state and 'reason' in state
