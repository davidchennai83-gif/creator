"""Optional Wan 2.2 (TI2V-5B) AI video for the opening scene.

Measured on this machine (RTX 2060 SUPER 8 GB, i5-4570, 12 GB RAM) one 2 second
clip at 480x832 costs ~6-10 minutes, so Wan can never be the main animation
engine for 11 daily videos. It is therefore opt-in, budgeted to one scene per
video (``WAN_SCENES``), and always falls back to the local motion engine when
the ComfyUI server is down, busy or too slow.

The clip is generated from the scene photo the pipeline already rendered, so
colours and composition match the other scenes. ``expand`` then stretches the
short clip across the whole scene with a forward/backward ramp so a 2 second
generation covers a 10-12 second narration without a hard loop cut.

The ComfyUI server is *not* started from here: it shares the GPU with the daily
uploads (see AGENTS.md), so the operator starts it with ``D:\\ai\\run_comfy.ps1``
when there is no upload running and sets ``VIDEO_WAN=true``.
"""
import json
import logging
import shutil
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from app.config.settings import settings

log = logging.getLogger(__name__)

# Official Wan 2.2 quality negative prompt from the Comfy-Org template.
NEGATIVE = ('色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，'
            'JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，'
            '形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景里人很多，倒着走')

# ComfyUI queue entries are arrays; the prompt id is the second element.
_PROGRESS_EVERY = 45.0
_POLL_EVERY = 5.0

_probe = {'checked_at': 0.0, 'ok': False}


def _url(path=''):
    return settings.WAN_URL.rstrip('/') + path


def _request(path, payload=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(_url(path), data=data,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _valid_size():
    """Wan 2.2 only accepts widths/heights in steps of 32 and 4n+1 frames.

    The defaults already comply; this keeps a hand-edited WAN_WIDTH/WAN_FRAMES
    from failing every render with a ComfyUI graph error instead of falling
    back quietly.
    """
    width = max(32, int(settings.WAN_WIDTH) // 32 * 32)
    height = max(32, int(settings.WAN_HEIGHT) // 32 * 32)
    frames = max(5, (int(settings.WAN_FRAMES) - 1) // 4 * 4 + 1)
    return width, height, frames


def _unavailable(reason):
    """Remember a failed probe so the remaining scenes skip Wan immediately."""
    _probe['ok'] = False
    _probe['checked_at'] = time.time()
    log.warning('Wan 2.2 disabled for this render: %s', reason)


def available(recheck_after=180.0):
    """True when the local ComfyUI answers. Cached so renders stay fast."""
    if not settings.VIDEO_WAN:
        return False
    now = time.time()
    if now - _probe['checked_at'] < recheck_after:
        return _probe['ok']
    try:
        _request('/system_stats', timeout=3)
        _probe['ok'] = True
    except Exception:                              # noqa: BLE001 - any failure means "not available"
        _probe['ok'] = False
    _probe['checked_at'] = now
    return _probe['ok']


def state():
    """Capabilities snapshot for the API and the status script."""
    enabled = bool(settings.VIDEO_WAN)
    width, height, frames = _valid_size()
    return {'enabled': enabled,
            'reachable': available() if enabled else False,
            'url': settings.WAN_URL,
            'model': settings.WAN_UNET,
            'scenes': settings.WAN_SCENES,
            'kinds': sorted(_kinds(settings.WAN_KINDS)),
            'skip_kinds': sorted(_kinds(settings.WAN_SKIP_KINDS)),
            'size': f'{width}x{height}',
            'frames': frames,
            'steps': settings.WAN_STEPS,
            'timeout': settings.WAN_TIMEOUT}


def _kinds(value):
    return {part.strip().lower() for part in str(value).split(',') if part.strip()}


def enabled_for(kind):
    """True when this video kind may spend GPU time on Wan.

    ``WAN_KINDS`` is an optional allow list (empty = every kind), and
    ``WAN_SKIP_KINDS`` always wins. That makes it possible to keep the slow AI
    scene on one video a day without delaying the 11:00 upload of the others.
    """
    if not settings.VIDEO_WAN:
        return False
    name = str(kind).strip().lower()
    if name in _kinds(settings.WAN_SKIP_KINDS):
        return False
    allowed = _kinds(settings.WAN_KINDS)
    return not allowed or name in allowed


def prompt_for(point, index=0):
    """Scene description for Wan: the story beat plus a motion instruction."""
    text = ' '.join(point.get('lines') or [])[:220].strip()
    title = (point.get('title_en') or point.get('title') or '').strip()
    subject = title or text
    extra = (settings.WAN_PROMPT or '').strip()
    prompt = (f'{subject}. Subtle natural motion, gentle cinematic camera drift, '
              f'photorealistic, high detail, no text, no captions')
    return f'{prompt}. {extra}' if extra else prompt


def build_graph(prompt, image_name, seed=42):
    """ComfyUI prompt graph for Wan 2.2 TI2V-5B GGUF at the configured size.

    Mirrors the official ``video_wan2_2_5B_ti2v`` template: GGUF loaders,
    ``ModelSamplingSD3`` shift 8.0, ``Wan22ImageToVideoLatent`` and a 20 step
    ``uni_pc`` sampler. ``SaveImage`` hands us the frame batch as lossless PNGs.
    """
    width, height, frames = _valid_size()
    return {
        '1': {'class_type': 'UnetLoaderGGUF',
              'inputs': {'unet_name': settings.WAN_UNET}},
        '2': {'class_type': 'CLIPLoaderGGUF',
              'inputs': {'clip_name': settings.WAN_CLIP, 'type': 'wan'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': settings.WAN_VAE}},
        '4': {'class_type': 'LoadImage', 'inputs': {'image': image_name}},
        '5': {'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': ['2', 0]}},
        '6': {'class_type': 'CLIPTextEncode', 'inputs': {'text': NEGATIVE, 'clip': ['2', 0]}},
        '7': {'class_type': 'ModelSamplingSD3', 'inputs': {'model': ['1', 0], 'shift': 8.0}},
        '8': {'class_type': 'Wan22ImageToVideoLatent',
              'inputs': {'vae': ['3', 0], 'width': width, 'height': height,
                         'length': frames, 'batch_size': 1,
                         'start_image': ['4', 0]}},
        '9': {'class_type': 'KSampler',
              'inputs': {'model': ['7', 0], 'positive': ['5', 0], 'negative': ['6', 0],
                         'latent_image': ['8', 0], 'seed': seed,
                         'steps': int(settings.WAN_STEPS), 'cfg': 5.0,
                         'sampler_name': 'uni_pc', 'scheduler': 'simple',
                         'denoise': 1.0}},
        '10': {'class_type': 'VAEDecode', 'inputs': {'samples': ['9', 0], 'vae': ['3', 0]}},
        '11': {'class_type': 'SaveImage',
               'inputs': {'images': ['10', 0], 'filename_prefix': 'wan_scene'}},
    }


def _busy():
    """True when ComfyUI is already working on something else.

    A render must never queue behind a leftover job (each video is allowed only
    a few minutes of GPU time), so a busy server simply means "use local motion".
    """
    try:
        queue = _request('/queue', timeout=5)
    except Exception:                              # noqa: BLE001 - treat unknown state as busy
        return True
    return bool(queue.get('queue_running') or queue.get('queue_pending'))


def _queue_id(item):
    """Prompt id of one ComfyUI /queue entry (array or dict form)."""
    if isinstance(item, (list, tuple)) and len(item) > 1:
        return str(item[1])
    if isinstance(item, dict):
        return str(item.get('prompt_id') or item.get('id') or '')
    return ''


def _cancel(prompt_id):
    """Drop our job from the queue and stop it only when it is the running one.

    Without this a timed-out Wan job keeps the GPU for minutes and every later
    render sees a busy server. ``/interrupt`` stops whatever is executing, so it
    is only sent when the running entry is ours.
    """
    running = []
    try:
        running = _request('/queue', timeout=10).get('queue_running') or []
    except Exception:                              # noqa: BLE001 - best effort cleanup
        pass
    try:
        _request('/queue', {'delete': [prompt_id]}, timeout=10)
    except Exception:                              # noqa: BLE001 - pending delete is optional
        pass
    if any(_queue_id(entry) == prompt_id for entry in running):
        try:
            _request('/interrupt', {}, timeout=10)
        except Exception:                          # noqa: BLE001 - interrupt is best effort
            pass


def _error_detail(status):
    """One short line from a failed ComfyUI history entry (never a full dump)."""
    for item in status.get('messages') or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        event, data = item[0], item[1]
        if event in ('execution_error', 'execution_interrupted'):
            text = (data or {}).get('exception_message') if isinstance(data, dict) else event
            return str(text or event).strip().splitlines()[0][:200]
    return 'unknown ComfyUI error'


def _download(item, target):
    query = urllib.parse.urlencode({'filename': item['filename'],
                                    'subfolder': item.get('subfolder', ''),
                                    'type': item.get('type', 'output')})
    urllib.request.urlretrieve(_url(f'/view?{query}'), target)
    return target.exists() and target.stat().st_size > 0


def generate(image_path, prompt, output_path, seed=42, progress=None):
    """Generate one clip; returns True when a playable mp4 was written.

    Every failure (server down, timeout, ComfyUI error, broken download) returns
    False so the caller simply keeps the local motion render. Failures that say
    something about this machine (graph rejected, too slow) also mark Wan
    unavailable for the next few minutes, so the other scenes do not each burn
    another ``WAN_TIMEOUT``.
    """
    image = Path(image_path)
    output = Path(output_path)
    if not image.exists() or not available() or _busy():
        return False
    started = time.time()
    prompt_id = None
    upload = None
    frames = None
    ok = False
    try:
        input_dir = Path(settings.WAN_INPUT_DIR)
        input_dir.mkdir(parents=True, exist_ok=True)
        # Unique name: two renders must never overwrite each other's input and
        # ComfyUI's LoadImage cache must not hand back the previous scene.
        upload = input_dir / f'wan-{uuid.uuid4().hex[:12]}{image.suffix.lower() or ".png"}'
        shutil.copy(image, upload)

        width, height, clip_frames = _valid_size()
        work = build_graph(prompt, upload.name, seed)
        queued = _request('/prompt', {'prompt': work, 'client_id': str(uuid.uuid4())}, timeout=60)
        prompt_id = queued.get('prompt_id')
        if not prompt_id:
            detail = queued.get('error') or queued.get('node_errors') or 'no prompt_id'
            _unavailable(f'ComfyUI rejected the graph ({str(detail)[:160]})')
            return False
        if progress:
            progress(f'Wan 2.2 started ({width}x{height}, '
                     f'{clip_frames} frames, {settings.WAN_STEPS} steps)')

        entry = None
        next_note = started + _PROGRESS_EVERY
        while time.time() - started < settings.WAN_TIMEOUT:
            try:
                history = _request(f'/history/{prompt_id}', timeout=30)
            except Exception as exc:               # noqa: BLE001 - one dropped poll is not a failure
                log.debug('Wan 2.2 history poll failed: %s', exc)
            else:
                if prompt_id in history:
                    entry = history[prompt_id]
                    break
            if progress and time.time() >= next_note:
                elapsed = int(time.time() - started)
                progress(f'Wan 2.2 still rendering ({elapsed}s of {settings.WAN_TIMEOUT}s budget)')
                next_note = time.time() + _PROGRESS_EVERY
            time.sleep(_POLL_EVERY)
        if not entry:
            _cancel(prompt_id)
            _unavailable(f'the clip took longer than WAN_TIMEOUT={settings.WAN_TIMEOUT}s')
            return False

        status = entry.get('status') or {}
        if status.get('status_str') == 'error':
            log.warning('Wan 2.2 job failed: %s', _error_detail(status))
            return False

        images = (entry.get('outputs') or {}).get('11', {}).get('images') or []
        if not images:
            log.warning('Wan 2.2 finished without an image batch')
            return False
        frames = output.with_suffix('')
        if frames.exists():
            shutil.rmtree(frames)
        frames.mkdir(parents=True)
        for index, item in enumerate(images):
            if not _download(item, frames / f'f-{index:05d}.png'):
                log.warning('Wan 2.2 frame download was empty (%s)', item.get('filename'))
                return False
        _encode(frames, output)
        ok = output.exists() and output.stat().st_size > 0
        if not ok:
            log.warning('Wan 2.2 encode produced no clip')
        return ok
    except Exception as exc:                       # noqa: BLE001 - optional feature, never fatal
        log.warning('Wan 2.2 generation failed: %s', exc)
        # Never leave our job running: it would block every later video.
        if prompt_id:
            _cancel(prompt_id)
        return False
    finally:
        if upload is not None:
            try:
                upload.unlink(missing_ok=True)
            except OSError:
                pass
        if frames is not None and not ok:
            shutil.rmtree(frames, ignore_errors=True)
        if not ok:
            output.unlink(missing_ok=True)


def _encode(frames_dir, clip_path):
    """Assemble the PNG batch into an H.264 clip the renderer can decode."""
    import imageio_ffmpeg
    import subprocess
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, '-y', '-loglevel', 'error',
                    '-framerate', str(settings.WAN_FPS),
                    '-i', str(frames_dir / 'f-%05d.png'),
                    '-vf', 'setsar=1', '-c:v', 'libx264', '-crf', '17',
                    '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                    str(clip_path)], check=True, timeout=600)


def frame_plan(count, scene_frames):
    """Map output frame indices onto source frames, forward then backward.

    A 2 second clip stretched over a 12 second scene would show six loops of the
    same motion; a single forward+backward ramp reads as a slow, continuous
    camera move instead. Longer scenes get whole cycles.
    """
    if count <= 1:
        return [0] * max(0, scene_frames)
    last = count - 1
    period = 2 * last
    plan = []
    for index in range(scene_frames):
        step = index % period
        plan.append(step if step <= last else period - step)
    return plan


def expand(clip_path, out_dir, duration, fps, width, height):
    """Turn the Wan clip into seq frames matching the scene duration.

    The clip is short, so the motion is slowed down and played forward then
    backward. A gentle push-in plus a little lateral drift is added on top:
    the camera move keeps the scene alive even when the generated motion is
    subtle, and it matches the look of the local motion scenes.

    Frames are written to a sibling temp directory and swapped in at the end so
    a decode/warp failure never leaves a half-filled ``seq-*`` folder that the
    crossfade pass would try to use.
    """
    import cv2
    import numpy as np

    clip_path = Path(clip_path)
    out_dir = Path(out_dir)
    if not clip_path.exists() or clip_path.stat().st_size == 0:
        return False
    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        return False
    frames = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(frame)
    finally:
        capture.release()
    if not frames:
        return False

    total = max(1, int(round(duration * fps)))
    plan = frame_plan(len(frames), total)
    src_h, src_w = frames[0].shape[:2]
    base = max(width / src_w, height / src_h)
    encode = [cv2.IMWRITE_JPEG_QUALITY, 95]
    staging = out_dir.with_name(out_dir.name + '.tmp')
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        for index, source in enumerate(plan):
            progress = index / max(1, total - 1)
            eased = progress * progress * (3.0 - 2.0 * progress)
            zoom = base * (1.05 + 0.055 * eased)
            drift = base * width * 0.012 * np.sin(2 * np.pi * (0.5 * progress))
            matrix = np.array([[zoom, 0.0, (width - src_w * zoom) / 2 - drift],
                               [0.0, zoom, (height - src_h * zoom) / 2]], dtype=np.float32)
            frame = cv2.warpAffine(frames[source], matrix, (width, height),
                                   flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)
            cv2.imwrite(str(staging / f'f-{index:06d}.jpg'), frame, encode)
    except Exception:                              # noqa: BLE001 - fall back to local motion
        shutil.rmtree(staging, ignore_errors=True)
        return False
    if out_dir.exists():
        shutil.rmtree(out_dir)
    staging.rename(out_dir)
    return True
