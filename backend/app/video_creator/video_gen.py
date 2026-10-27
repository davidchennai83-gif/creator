"""Provider-based AI picture-to-video generation.

This machine has no CUDA GPU, so diffusion / SVD-style video models cannot run
locally. Instead the app talks to any external provider that implements this
tiny REST contract (keep it that generic on purpose):

    POST {VIDEO_PROVIDER_URL}/generate
        body  : {"image": "<data:image/png;base64,..>", "prompt": str, "duration": float, "model": "..."}
        header: Authorization: Bearer {VIDEO_PROVIDER_KEY}
        -> 200 {"id": "<task id>", "status": "pending" | "done"}
    GET  {VIDEO_PROVIDER_URL}/generate/{id}
        -> 200 {"status": "pending" | "done" | "failed", "download_url"?: "https://..."}
    GET  {download_url}  -> bytes (mp4 clip)

The video provider is optional. When it is not configured or fails, rendering
falls back to the local animated-image engine (motion.py) so videos still
contain convincing moving visuals instead of static screenshots.
"""
import base64
import time
from pathlib import Path

import httpx

from app.config.settings import settings


def provider_state():
    """Capabilities snapshot for the API/frontend."""
    if settings.VIDEO_PROVIDER != 'http':
        return {'provider': 'local', 'configured': False,
                'reason': 'VIDEO_PROVIDER is local — animated-image motion renderer'}
    if not settings.VIDEO_PROVIDER_URL:
        return {'provider': 'http', 'configured': False,
                'reason': 'VIDEO_PROVIDER_URL is empty — using animated-image fallback'}
    return {'provider': 'http', 'configured': True,
            'url': settings.VIDEO_PROVIDER_URL,
            'model': settings.VIDEO_PROVIDER_MODEL or None,
            'reason': ''}


def generate_scene_clip(image_path, prompt, duration, output_path, timeout=None):
    """Ask the provider to animate one scene image into a short mp4 clip.

    Returns True on success (clip written to output_path), False on any failure.
    The caller decides whether to keep its local fallback output.
    """
    if settings.VIDEO_PROVIDER != 'http' or not settings.VIDEO_PROVIDER_URL:
        return False
    base_url = settings.VIDEO_PROVIDER_URL.rstrip('/')
    key = settings.VIDEO_PROVIDER_KEY.get_secret_value()
    headers = {'Authorization': f'Bearer {key}'} if key else {}
    timeout = timeout or settings.VIDEO_PROVIDER_TIMEOUT
    try:
        image = Path(image_path).read_bytes()
        payload = {'image': 'data:image/png;base64,' + base64.b64encode(image).decode(),
                   'prompt': prompt, 'duration': round(float(duration), 2),
                   'model': settings.VIDEO_PROVIDER_MODEL or None}
        with httpx.Client(timeout=httpx.Timeout(60, connect=10)) as client:
            response = client.post(f'{base_url}/generate', json=payload, headers=headers)
            response.raise_for_status()
            task = response.json()
            task_id = task.get('id')
            if not task_id:
                return False
            deadline = time.time() + timeout
            while time.time() < deadline:
                status_response = client.get(f'{base_url}/generate/{task_id}', headers=headers)
                status_response.raise_for_status()
                state = status_response.json()
                if state.get('status') == 'done':
                    download_url = state.get('download_url')
                    if not download_url:
                        return False
                    clip = client.get(download_url, timeout=httpx.Timeout(300, connect=30))
                    clip.raise_for_status()
                    Path(output_path).write_bytes(clip.content)
                    return True
                if state.get('status') == 'failed':
                    return False
                time.sleep(3)
    except (httpx.HTTPError, OSError, ValueError, KeyError):
        return False
    return False


def provider_prompt(point, index):
    """A short natural prompt for animating a scene image."""
    text = ' '.join(point.get('lines') or []).strip()
    title = point.get('title') or point.get('year') or ''
    return f"Subtle cinematic motion, gentle camera drift over this scene. {title} {text}".strip()