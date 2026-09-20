"""CPU-friendly Tamil scene renderer. No silent audio-only success fallbacks."""
import asyncio
import json
import shutil
import subprocess
from contextlib import ExitStack
from pathlib import Path

async def speech(text, destination, voice):
    import edge_tts
    await asyncio.wait_for(edge_tts.Communicate(text, voice).save(str(destination)), timeout=120)


def render_frames(folder):
    """Run the Chromium frame renderer; failures must carry the renderer's own message."""
    result = subprocess.run([shutil.which('node') or 'node', str(Path(__file__).with_name('render_frames.cjs')), str(folder)],
                            timeout=120, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip()[-1500:]
        raise RuntimeError(f'Frame renderer failed (exit code {result.returncode}): {detail or "no output"}')


def render(points, folder, day, voice, progress, kind='history'):
    # Imported lazily so the API, login and scheduler still start when the optional video packages are absent.
    try:
        from moviepy import AudioFileClip, AudioClip, CompositeAudioClip, ImageClip, VideoFileClip, concatenate_videoclips
    except ImportError as exc:
        raise RuntimeError('Video packages are not installed. Run: pip install -r requirements-video.txt') from exc
    import numpy as np
    from .stock_photos import prepare_backgrounds
    folder = Path(folder)
    backgrounds = prepare_backgrounds(points, kind, folder, progress)
    progress('Rendering Tamil text with Chromium')
    (folder / 'frames.json').write_text(json.dumps({'points': points, 'day': day, 'kind': kind, 'backgrounds': backgrounds}, ensure_ascii=False), encoding='utf-8')
    render_frames(folder)
    with ExitStack() as stack:
        clips = []
        for i, point in enumerate(points, 1):
            progress(f'Tamil voice and scene {i}/{len(points)}')
            audio_path = folder / f'voice-{i}.mp3'
            asyncio.run(speech('. '.join(point['lines']), audio_path, voice))
            audio = stack.enter_context(AudioFileClip(str(audio_path)))
            duration = audio.duration + 0.6
            clip = ImageClip(str(folder / f'scene-{i}.png')).with_duration(duration).with_audio(audio)
            stack.callback(clip.close)
            clips.append(clip)
        video = concatenate_videoclips(clips, method='chain')
        stack.callback(video.close)
        # Minimal ambient bed: simple sine-sweep bed under narration.
        def music(t):
            t = np.asarray(t)
            envelope = 0.3 + 0.2 * np.sin(2 * np.pi * 1.5 * t) ** 2
            wave = sum(np.sin(2 * np.pi * hz * t) for hz in (130.81, 164.81, 196.0)) / 3
            mono = 0.02 * envelope * wave
            return np.column_stack((mono, mono)) if t.ndim else np.array([mono, mono])
        bgm = AudioClip(music, duration=video.duration, fps=44100)
        stack.callback(bgm.close)
        mixed = CompositeAudioClip([video.audio, bgm]).with_duration(video.duration)
        stack.callback(mixed.close)
        final = video.with_audio(mixed)
        stack.callback(final.close)
        progress('Encoding MP4 with Tamil narration and background bed')
        output = folder / 'history.mp4'
        final.write_videofile(str(output), fps=24, codec='libx264', audio_codec='aac',
                             preset='ultrafast', threads=2, logger=None,
                             temp_audiofile=str(folder / 'mix.m4a'), ffmpeg_params=['-movflags', '+faststart'])
    with VideoFileClip(str(output)) as check:
        if not check.audio or check.duration < 1:
            raise ValueError('Export validation failed: missing video or audio')
        return round(check.duration, 2)
