"""Local animated-image rendering: the fallback "moving scene" engine.

When no AI video provider is configured (hardware here has no CUDA GPU, so
diffusion video models are not feasible), each 1080x1920 scene frame is turned
into a convincingly moving shot with slow camera work (Ken Burns -style zooms,
pans and tilts), drifting dust particles, a light sweep and vignette, plus a
smooth crossfade into the next scene. Fully deterministic per seed so the same
job always renders the same frames.
"""
import cv2
import numpy as np

SUPER = 1.24  # supersampled canvas allows re-cropping without visible jaggies

DEFAULT_SIZE = (1080, 1920)


def _vignette(w, h):
    y, x = np.ogrid[:h, :w]
    center_x, center_y = w / 2, h / 2
    distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
    max_distance = np.sqrt(center_x ** 2 + center_y ** 2)
    return np.clip(1.14 - 0.42 * (distance / max_distance) ** 1.5, 0.5, 1.14).astype(np.float32)


def make_overlays(w=DEFAULT_SIZE[0], h=DEFAULT_SIZE[1], seed=7, particles=90):
    """Vignette mask plus drifting dust particles for parallax-depth feel."""
    rng = np.random.default_rng(seed)
    dust = []
    for _ in range(particles):
        dust.append((float(rng.uniform(0, w)), float(rng.uniform(0, h)),
                     float(rng.uniform(2, 6)), float(rng.uniform(-18, 18)),
                     float(rng.uniform(-8, 8)), float(rng.uniform(0.6, 1.4))))
    return _vignette(w, h), dust


def _zoom(variant, p):
    if variant % 6 == 0:
        return 1.14 - 0.10 * p          # slow pull-back from a closer look
    if variant % 6 == 1:
        return 1.05 + 0.10 * p          # slow push-in
    if variant % 6 in (2, 3):
        return 1.11                      # steady pan
    return 1.12 - 0.06 * p               # tilt: slight zoom while rising/sinking


def _pan(variant, p, w, h):
    pan = 0.9
    if variant % 6 == 2:
        return pan * (2 * p - 1), 0.14 * np.sin(2 * np.pi * 0.8 * p)
    if variant % 6 == 3:
        return pan * (1 - 2 * p), 0.14 * np.cos(2 * np.pi * 0.8 * p)
    if variant % 6 == 4:
        return 0.0, pan * 0.7 * (2 * p - 1)
    if variant % 6 == 5:
        return 0.0, pan * 0.7 * (1 - 2 * p)
    return (0.10 * np.sin(2 * np.pi * (0.7 * p + 0.2)),
            0.08 * np.cos(2 * np.pi * (0.6 * p + 0.4)))


def _crop(base, variant, p, w, h):
    """Resize base so the moving crop window always covers exactly w x h."""
    canvas = cv2.resize(base, (int(w * SUPER), int(h * SUPER)), interpolation=cv2.INTER_AREA)
    canvas_w, canvas_h = canvas.shape[1], canvas.shape[0]
    zoom = _zoom(variant, p)
    crop_w = canvas_w / zoom
    crop_h = canvas_h / zoom
    dx, dy = _pan(variant, p, canvas_w, canvas_h)
    center_x = canvas_w / 2 + dx * (canvas_w - crop_w) / 2
    center_y = canvas_h / 2 + dy * (canvas_h - crop_h) / 2
    x0 = int(np.clip(center_x - crop_w / 2, 0, canvas_w - crop_w))
    y0 = int(np.clip(center_y - crop_h / 2, 0, canvas_h - crop_h))
    crop = canvas[y0:y0 + int(crop_h), x0:x0 + int(crop_w)]
    return cv2.resize(crop, (w, h), interpolation=cv2.INTER_CUBIC)


def render_frame(base, variant, frame_time, duration, overlays, out_size=DEFAULT_SIZE):
    """Return the animated frame (BGR uint8) for the given time in the scene."""
    w, h = out_size
    progress = min(1.0, frame_time / duration) if duration > 0 else 1.0
    frame = _crop(base, variant, progress, w, h).astype(np.float32)
    vignette, dust = overlays
    frame *= vignette[:, :, None]
    overlay = np.zeros_like(frame)
    for x0, y0, radius, vx, vy, strength in dust:
        x = int((x0 + vx * frame_time) % w)
        y = int((y0 + vy * frame_time) % h)
        cv2.circle(overlay, (x, y), int(radius), (255.0, 255.0, 255.0), -1)
    overlay = cv2.GaussianBlur(overlay, (0, 0), 1.8)
    frame += overlay * 0.055
    sweep = 0.5 + 0.5 * np.sin(2 * np.pi * (0.05 * frame_time + 0.5 * (np.arange(h)[:, None] / h + np.arange(w)[None, :] / w)))
    frame += sweep[:, :, None] * 12.0
    return np.clip(frame, 0, 255).astype(np.uint8)


def render_scene(base, out_dir, duration, fps, variant, seed, out_size=DEFAULT_SIZE):
    """Write every frame of one animated scene as out_dir / f-000001.png ..."""
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
            for attempt in range(5):
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
    for index in range(count):
        frame = render_frame(base, variant, index / fps, duration, overlays, out_size)
        target = out_dir / f'f-{index:06d}.png'
        for attempt in range(5):
            try:
                if cv2.imwrite(str(target), frame) and target.stat().st_size > 0:
                    break
            except (cv2.error, OSError):
                pass
            time.sleep(0.5)
        else:
            raise OSError(f'Could not write frame {target}')
    return count


def crossfade(first, second, progress):
    """Blend two same-sized frames; progress 0 = first, 1 = second."""
    return (first.astype(np.float32) * (1 - progress)
            + second.astype(np.float32) * progress).astype(np.uint8)