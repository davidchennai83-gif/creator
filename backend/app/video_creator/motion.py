"""Local animated-image rendering: the "moving scene" engine (v2).

Turn one 1080x1920 scene art PNG into a convincingly moving shot: eased
camera moves (slow push-in / pull-back / pan / tilt) with sub-pixel accuracy,
a handheld drift, two layers of parallax dust, a travelling light sweep and a
vignette, then a smooth crossfade into the next scene.

Performance notes (v2). The old engine rebuilt the supersampled canvas and the
per-pixel light sweep on every frame, which cost ~230 ms per frame on this
4-core i5 and made the motion stage the slowest part of a render. Everything
static is now prepared once per scene and every frame does a single sub-pixel
warp plus three vectorised passes (~30-45 ms per frame), so the GPU-encoded
final pass is no longer waiting on the animation.

Fully deterministic per seed: the same job always renders the same frames.
"""
import cv2
import numpy as np

SUPER = 1.24          # supersampled canvas allows re-cropping without jaggies
SWEEP_GAIN = 12.0     # light-sweep amplitude in 8-bit levels
SWEEP_SCALE = 4       # the sweep is a smooth gradient; compute it at 1/4 size

DEFAULT_SIZE = (1080, 1920)


# --------------------------------------------------------------- preparation

def _vignette(w, h):
    y, x = np.ogrid[:h, :w]
    center_x, center_y = w / 2, h / 2
    distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
    max_distance = np.sqrt(center_x ** 2 + center_y ** 2)
    return np.clip(1.14 - 0.42 * (distance / max_distance) ** 1.5, 0.5, 1.14).astype(np.float32)


def _sweep_phase(w, h):
    """Static phase of the diagonal light band, at reduced resolution."""
    sw, sh = max(1, w // SWEEP_SCALE), max(1, h // SWEEP_SCALE)
    rows = (np.arange(sh, dtype=np.float32) / sh)[:, None]
    cols = (np.arange(sw, dtype=np.float32) / sw)[None, :]
    phase = (2.0 * np.pi * 0.5 * (rows + cols)).astype(np.float32)
    return np.cos(phase), np.sin(phase)


def _sprite(radius, blur):
    """A soft round dust mote, precomputed once per radius."""
    radius = max(1, int(radius))
    pad = max(2, int(radius * 3 + blur * 3))
    size = pad * 2 + 1
    canvas = np.zeros((size, size), dtype=np.float32)
    cv2.circle(canvas, (pad, pad), radius, 1.0, -1, lineType=cv2.LINE_AA)
    if blur > 0:
        canvas = cv2.GaussianBlur(canvas, (0, 0), blur)
    peak = float(canvas.max())
    return canvas / peak if peak > 0 else canvas


def make_overlays(w=DEFAULT_SIZE[0], h=DEFAULT_SIZE[1], seed=7, particles=70):
    """Vignette, light sweep and two parallax dust layers for one scene.

    Also acts as the per-scene cache for the supersampled canvas, so a scene
    never upscales its background twice.
    """
    rng = np.random.default_rng(seed)
    layers = []
    # Far layer: small, slow, dim, sharp. Near layer: larger, quicker, softer.
    for count, r_range, speed, strength, blur in (
            (int(particles * 0.62), (1.5, 3.4), (6.0, 16.0), (0.030, 0.055), 0.6),
            (int(particles * 0.38), (4.0, 8.0), (18.0, 42.0), (0.045, 0.085), 2.2)):
        xs = rng.uniform(0, w, count).astype(np.float32)
        ys = rng.uniform(0, h, count).astype(np.float32)
        radii = rng.uniform(r_range[0], r_range[1], count).astype(np.float32)
        vx = rng.uniform(-1, 1, count).astype(np.float32) * rng.uniform(speed[0], speed[1], count)
        vy = rng.uniform(-0.45, 0.45, count).astype(np.float32) * rng.uniform(speed[0], speed[1], count)
        gain = rng.uniform(strength[0], strength[1], count).astype(np.float32)
        sprites = [_sprite(round(float(r)), blur) for r in radii]
        layers.append({'x': xs, 'y': ys, 'vx': vx, 'vy': vy, 'r': radii,
                       'gain': gain, 'sprites': sprites})
    vignette = _vignette(w, h)
    cos_phase, sin_phase = _sweep_phase(w, h)
    return {'w': w, 'h': h, 'vignette': np.repeat(vignette[:, :, None], 3, axis=2),
            'cos': cos_phase, 'sin': sin_phase, 'layers': layers,
            'canvas': None, 'canvas_key': None}


def _canvas_for(base, overlays):
    """Supersampled working copy of the background, cached for the scene."""
    key = (id(base), base.shape, overlays['w'], overlays['h'])
    if overlays.get('canvas_key') != key or overlays.get('canvas') is None:
        overlays['canvas'] = cv2.resize(
            base, (int(overlays['w'] * SUPER), int(overlays['h'] * SUPER)),
            interpolation=cv2.INTER_AREA)
        overlays['canvas_key'] = key
    return overlays['canvas']


# ------------------------------------------------------------------ camera

def _ease(x):
    """Smoothstep: shots start and stop gently instead of sliding at a fixed rate."""
    x = 0.0 if x < 0 else (1.0 if x > 1 else x)
    return x * x * (3.0 - 2.0 * x)


def _zoom(variant, p):
    if variant % 6 == 0:
        return 1.14 - 0.10 * p          # slow pull-back from a closer look
    if variant % 6 == 1:
        return 1.04 + 0.10 * p          # slow push-in
    if variant % 6 in (2, 3):
        return 1.11                      # steady pan
    return 1.12 - 0.06 * p               # tilt: slight zoom while rising/sinking


def _pan(variant, p, t):
    """Normalised camera offset in [-1, 1] plus a gentle handheld drift."""
    drift_x = 0.055 * np.sin(2 * np.pi * (0.23 * t + 0.11 * (variant % 5)))
    drift_y = 0.045 * np.cos(2 * np.pi * (0.19 * t + 0.07 * (variant % 3)))
    span = 0.9
    if variant % 6 == 2:
        return span * (2 * p - 1) + drift_x, 0.14 * np.sin(2 * np.pi * 0.8 * p) + drift_y
    if variant % 6 == 3:
        return span * (1 - 2 * p) + drift_x, 0.14 * np.cos(2 * np.pi * 0.8 * p) + drift_y
    if variant % 6 == 4:
        return drift_x, span * 0.7 * (2 * p - 1) + drift_y
    if variant % 6 == 5:
        return drift_x, span * 0.7 * (1 - 2 * p) + drift_y
    return 0.10 * np.sin(2 * np.pi * (0.7 * p + 0.2)) + drift_x, \
        0.08 * np.cos(2 * np.pi * (0.6 * p + 0.4)) + drift_y


def _camera(canvas, variant, progress, t, w, h):
    """Sub-pixel crop of the supersampled canvas -> one w x h frame."""
    canvas_h, canvas_w = canvas.shape[:2]
    zoom = _zoom(variant, progress)
    crop_w = canvas_w / zoom
    crop_h = canvas_h / zoom
    dx, dy = _pan(variant, progress, t)
    half_x = max(0.0, (canvas_w - crop_w) / 2)
    half_y = max(0.0, (canvas_h - crop_h) / 2)
    cx = min(canvas_w - crop_w / 2, max(crop_w / 2, canvas_w / 2 + dx * half_x))
    cy = min(canvas_h - crop_h / 2, max(crop_h / 2, canvas_h / 2 + dy * half_y))
    scale = w / crop_w
    matrix = np.array([[scale, 0.0, w / 2 - cx * scale],
                       [0.0, scale, h / 2 - cy * scale]], dtype=np.float32)
    return cv2.warpAffine(canvas, matrix, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)


def _blit(buffer, sprite, x, y):
    """Add one dust mote, wrapping across the frame edges."""
    buf_h, buf_w = buffer.shape[:2]
    size = sprite.shape[0]
    half = size // 2
    for ox in (-buf_w, 0, buf_w):
        for oy in (-buf_h, 0, buf_h):
            left = int(round(x)) + ox - half
            top = int(round(y)) + oy - half
            if left >= buf_w or top >= buf_h or left + size <= 0 or top + size <= 0:
                continue
            sx0 = max(0, -left)
            sy0 = max(0, -top)
            dx0 = max(0, left)
            dy0 = max(0, top)
            dx1 = min(buf_w, left + size)
            dy1 = min(buf_h, top + size)
            buffer[dy0:dy1, dx0:dx1] += sprite[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0), None]


# ------------------------------------------------------------------- frames

def render_frame(base, variant, frame_time, duration, overlays, out_size=DEFAULT_SIZE):
    """Return the animated frame (BGR uint8) for the given time in the scene."""
    w, h = out_size
    progress = _ease(frame_time / duration) if duration > 0 else 1.0
    canvas = _canvas_for(base, overlays)
    frame = _camera(canvas, variant, progress, frame_time, w, h)

    # Vignette and the travelling light band in one float pass each. The frame
    # is kept float only between these two vectorised operations.
    out = cv2.multiply(frame, overlays['vignette'], dtype=cv2.CV_32F)

    angle = 2.0 * np.pi * (0.05 * frame_time)
    sweep = 0.5 + 0.5 * (np.sin(angle) * overlays['cos'] + np.cos(angle) * overlays['sin'])
    sweep = (sweep * SWEEP_GAIN).astype(np.float32)
    sweep = cv2.resize(sweep, (w, h), interpolation=cv2.INTER_LINEAR)
    cv2.add(out, cv2.merge((sweep, sweep, sweep)), dst=out)

    for layer in overlays['layers']:
        xs = np.mod(layer['x'] + layer['vx'] * frame_time, w)
        ys = np.mod(layer['y'] + layer['vy'] * frame_time, h)
        for x, y, gain, sprite in zip(xs, ys, layer['gain'], layer['sprites']):
            _blit(out, sprite * gain, x, y)

    return cv2.convertScaleAbs(out)


def render_scene(base, out_dir, duration, fps, variant, seed, out_size=DEFAULT_SIZE):
    """Write every frame of one animated scene as out_dir / f-000001.jpg ...

    JPEG (quality 95) instead of PNG: the frames are re-encoded to H.264 a
    minute later, and writing 1080x1920 PNGs dominated the motion stage.
    """
    import shutil
    import time
    from pathlib import Path
    out_dir = Path(out_dir)

    def fresh_dir():
        """Empty out_dir for a new scene. The dying disk raises WinError 145
        (locked files) or WinError 1392 (corrupt metadata) during rmtree, so
        retry first and then park the stubborn folder aside so the scene can
        still be rebuilt instead of failing the whole render."""
        if out_dir.exists():
            cleared = False
            for _ in range(5):
                try:
                    shutil.rmtree(out_dir)
                    cleared = True
                    break
                except FileNotFoundError:
                    cleared = True
                    break
                except OSError:
                    time.sleep(1.0)
            if not cleared:
                for suffix in ('.stale', '.stale2', '.stale3'):
                    alt = out_dir.with_name(out_dir.name + suffix)
                    shutil.rmtree(alt, ignore_errors=True)
                    try:
                        out_dir.rename(alt)
                        cleared = True
                        break
                    except OSError:
                        continue
                if not cleared:
                    shutil.rmtree(out_dir, ignore_errors=True)
                    if out_dir.exists():
                        raise OSError(f'Cannot clear corrupt scene folder {out_dir}')
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            for suffix in ('.stale', '.stale2', '.stale3'):
                alt = out_dir.with_name(out_dir.name + suffix)
                shutil.rmtree(alt, ignore_errors=True)
                try:
                    out_dir.rename(alt)
                    break
                except OSError:
                    continue
            else:
                raise
            out_dir.mkdir(parents=True, exist_ok=True)

    fresh_dir()
    overlays = make_overlays(out_size[0], out_size[1], seed=seed)
    count = int(round(duration * fps))
    encode = [cv2.IMWRITE_JPEG_QUALITY, 95]
    for index in range(count):
        frame = render_frame(base, variant, index / fps, duration, overlays, out_size)
        target = out_dir / f'f-{index:06d}.jpg'
        for attempt in range(5):
            try:
                if cv2.imwrite(str(target), frame, encode) and target.stat().st_size > 0:
                    break
            except (cv2.error, OSError):
                pass
            time.sleep(0.5)
        else:
            raise OSError(f'Could not write frame {target}')
    overlays['canvas'] = None
    return count


def crossfade(first, second, progress):
    """Blend two same-sized frames; progress 0 = first, 1 = second."""
    return cv2.addWeighted(first, 1.0 - progress, second, progress, 0.0)
