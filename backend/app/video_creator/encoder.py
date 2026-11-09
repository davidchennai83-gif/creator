"""Pick the fastest H.264 encoder that actually works on this machine.

The final pass of a render is one FFmpeg encode of the whole frame sequence.
This box used to be CPU-only (libx264, `preset medium`), which on a 4-core
i5-4570 costs more wall-clock than the frame compositing itself. Now that an
NVIDIA card is installed, NVENC does the same job in hardware and leaves the
CPU for Chromium/OpenCV.

NVENC must never break a render, so it is only used after a real one-frame
probe succeeds, and render.py retries the encode with libx264 if the hardware
path fails at any point (driver update, GPU busy with another encode session,
card without NVENC). VIDEO_ENCODER=x264 forces the software path.
"""
import functools
import logging
import subprocess

from app.config.settings import settings
from app.voice.tts import ffmpeg_exe

log = logging.getLogger(__name__)

# Constant-quality VBR keeps the look consistent with the old `crf 22`; a fixed
# bitrate would smear the slow camera moves that carry these shorts. p7 + AQ +
# lookahead costs a little GPU time and buys the highest NVENC profile quality.
# The quality target is VIDEO_CQ (lower = better/larger, 23 ≈ the old crf 22).
def _nvenc_args():
    cq = str(min(34, max(14, int(settings.VIDEO_CQ))))
    return ['-c:v', 'h264_nvenc', '-preset', 'p7', '-tune', 'hq',
            '-rc', 'vbr', '-cq', cq, '-b:v', '0',
            '-spatial-aq', '1', '-temporal-aq', '1', '-rc-lookahead', '20',
            '-bf', '3', '-profile:v', 'high', '-pix_fmt', 'yuv420p']


X264_ARGS = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '22', '-pix_fmt', 'yuv420p']

# Process-wide memo. `_nvenc` is None until probed, then True/False for the rest
# of the worker's life; disable_nvenc() latches it off after a real failure.
_nvenc = None
_reason = ''


def _forced_off():
    return str(settings.VIDEO_ENCODER).strip().lower() in ('x264', 'libx264', 'cpu', 'off', 'none')


def _probe(args):
    """Encode one tiny frame with the exact argument set a render will use."""
    try:
        result = subprocess.run(
            [ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
             '-i', 'color=c=black:s=640x360:d=0.2', *args, '-f', 'null', '-'],
            capture_output=True, timeout=90)
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning('Encoder probe (%s) could not run: %s', args[1], exc)
        return False
    if result.returncode != 0:
        detail = (result.stderr or b'')[-400:].decode('utf-8', 'replace').strip()
        log.info('Encoder probe (%s) failed: %s', args[1], detail or 'no output')
        return False
    return True


@functools.lru_cache(maxsize=1)
def gpu_name():
    """Marketing name of the first NVIDIA GPU, or '' when there is none."""
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total',
                                 '--format=csv,noheader'], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ''
    return (result.stdout or '').strip().splitlines()[0].strip() if result.returncode == 0 else ''


def nvenc_ready():
    """True when this process should encode with h264_nvenc."""
    global _nvenc, _reason
    if _forced_off():
        _reason = 'VIDEO_ENCODER disables hardware encoding'
        return False
    if _nvenc is None:
        _nvenc = _probe(_nvenc_args())
        _reason = '' if _nvenc else 'h264_nvenc probe failed — using libx264'
        if _nvenc:
            log.info('NVENC available (%s); hardware H.264 encoding enabled', gpu_name() or 'NVIDIA GPU')
        else:
            log.info('NVENC unavailable; rendering with libx264')
    return _nvenc


def disable_nvenc():
    """Latch the hardware path off after a failed encode so later renders stay fast and reliable."""
    global _nvenc, _reason
    if _nvenc:
        log.warning('Disabling NVENC for this process after an encode failure')
    _nvenc = False
    _reason = 'NVENC failed during a render — fell back to libx264'


def video_args():
    """Return (ffmpeg codec arguments, label) for the chosen encoder."""
    if nvenc_ready():
        return _nvenc_args(), 'nvenc'
    return list(X264_ARGS), 'x264'


def x264_args():
    return list(X264_ARGS)


def state():
    """Small snapshot for /capabilities and the UI."""
    ready = nvenc_ready()
    return {'encoder': 'h264_nvenc' if ready else 'libx264',
            'hardware': ready,
            'gpu': gpu_name() or None,
            'reason': '' if ready else _reason}
