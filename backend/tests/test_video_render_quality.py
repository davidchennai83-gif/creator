"""The animated-scene engine and the mastering/composite helpers.

These cover the two stages that were rewritten for speed and picture quality:
motion.py (eased sub-pixel camera, parallax dust, light sweep) and render.py
(cropped overlay blending, sidechain ducking). They run on small frames so the
suite stays fast.
"""
import numpy as np
import pytest

from app.video_creator import motion
from app.video_creator import render as renderer

W, H = 216, 384


def background(seed=3):
    rng = np.random.default_rng(seed)
    return (rng.random((H, W, 3)) * 180 + 40).astype(np.uint8)


def test_render_frame_shape_and_movement():
    base = background()
    overlays = motion.make_overlays(W, H, seed=5)
    first = motion.render_frame(base, 1, 0.0, 4.0, overlays, (W, H))
    later = motion.render_frame(base, 1, 3.5, 4.0, overlays, (W, H))
    assert first.shape == (H, W, 3) and first.dtype == np.uint8
    # The camera has moved, so the two frames must differ.
    assert np.abs(first.astype(np.int16) - later.astype(np.int16)).mean() > 1.0


def test_render_frame_is_deterministic_per_seed():
    base = background()
    a = motion.render_frame(base, 2, 1.0, 4.0, motion.make_overlays(W, H, seed=9), (W, H))
    b = motion.render_frame(base, 2, 1.0, 4.0, motion.make_overlays(W, H, seed=9), (W, H))
    assert np.array_equal(a, b)


def test_canvas_is_reused_for_the_whole_scene():
    base = background()
    overlays = motion.make_overlays(W, H, seed=1)
    motion.render_frame(base, 0, 0.0, 4.0, overlays, (W, H))
    canvas = overlays['canvas']
    motion.render_frame(base, 0, 2.0, 4.0, overlays, (W, H))
    assert overlays['canvas'] is canvas  # prepared once, not per frame


def test_crossfade_endpoints():
    left = np.zeros((H, W, 3), np.uint8)
    right = np.full((H, W, 3), 200, np.uint8)
    assert motion.crossfade(left, right, 0.0).max() == 0
    assert motion.crossfade(left, right, 1.0).min() == 200
    middle = motion.crossfade(left, right, 0.5)
    assert 90 <= middle.mean() <= 110


def test_duck_gain_is_one_without_voice_and_dips_under_speech():
    rate = 8000
    silence = np.zeros(rate * 3)
    assert np.all(renderer._duck_gain(silence, rate) == pytest.approx(1.0))

    voice = np.zeros(rate * 3)
    voice[rate:rate * 2] = np.sin(2 * np.pi * 220 * np.arange(rate) / rate) * 0.5
    gain = renderer._duck_gain(voice, rate)
    assert gain[rate + rate // 2] < 0.5      # bed pushed down under speech
    assert gain[rate // 2] > 0.95            # untouched before the sentence


def test_overlay_composites_only_its_bounding_box(tmp_path):
    import cv2
    frame = np.full((H, W, 3), 30, np.uint8)
    overlay = np.zeros((H, W, 4), np.uint8)
    overlay[100:140, 60:120] = (0, 0, 255, 255)  # opaque red block
    path = tmp_path / 'overlay-1.png'
    cv2.imwrite(str(path), overlay)

    prepared = renderer._prepare_overlay(path, (W, H))
    assert prepared['w'] == 60 and prepared['h'] == 40

    out = renderer._apply_overlay(frame.copy(), prepared)
    assert tuple(out[120, 90]) == (0, 0, 255)
    assert tuple(out[20, 20]) == (30, 30, 30)
    # Alpha 0 pixels inside the crop stay transparent.
    assert tuple(out[101, 61]) == (0, 0, 255)


def test_missing_overlay_is_ignored(tmp_path):
    frame = np.full((H, W, 3), 30, np.uint8)
    assert renderer._prepare_overlay(tmp_path / 'nope.png', (W, H)) is None
    assert np.array_equal(renderer._apply_overlay(frame, None), frame)
