"""Tamil scene renderer: Chromium frames -> animated scenes -> GPU-encoded MP4.

No silent audio-only success fallbacks: the exported file must carry both a
video stream and narration, or the render fails loudly.
"""
import asyncio
import json
import logging
import shutil
import subprocess
import time
import wave
from pathlib import Path

from app.config.settings import settings

log = logging.getLogger(__name__)


async def speech(text, destination, voice, rate='+15%', pitch='+0Hz', volume='+0%'):
    import edge_tts
    from .cues import normalise_for_speech
    text = normalise_for_speech(text)
    await asyncio.wait_for(
        edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume).save(str(destination)), timeout=120)


def render_frames(folder, script='render_frames.cjs'):
    """Run a Chromium frame renderer; failures must carry the renderer's own message."""
    try:
        result = subprocess.run([shutil.which('node') or 'node', str(Path(__file__).with_name(script)), str(folder)],
                                timeout=1800, capture_output=True, text=True, encoding='utf-8', errors='replace')
    except FileNotFoundError as exc:
        raise RuntimeError('Node.js was not found on PATH. The frame renderer (render_frames.cjs) '
                           'needs Node + npm install in the frontend folder.') from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip()[-1500:]
        raise RuntimeError(f'Frame renderer failed (exit code {result.returncode}): {detail or "no output"}')


def render_outro_frames(folder, index, seconds, theme, fps):
    """Render the animated Like / Share / Subscribe end-card as the final scene."""
    conf = json.loads((folder / 'frames.json').read_text(encoding='utf-8'))
    conf['theme'] = {'accent': theme['accent'], 'badge': theme['badge']}
    conf['outro'] = {'seconds': seconds, 'fps': fps, 'out': f'seq-{index}',
                     'channel': settings.CHANNEL_NAME, 'tagline': theme['cta'], 'badge': theme['badge']}
    (folder / 'frames.json').write_text(json.dumps(conf, ensure_ascii=False), encoding='utf-8')
    render_frames(folder, 'render_outro_frames.cjs')


def run_ffmpeg(command, cwd, timeout):
    """Encode with stderr captured, so a failure reports ffmpeg's own reason."""
    result = subprocess.run(command, cwd=str(cwd), timeout=timeout,
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        # Windows reports exit statuses as unsigned 32-bit; keep the POSIX byte.
        code = result.returncode & 0xFF
        detail = (result.stderr or result.stdout or '').strip()[-2000:]
        raise RuntimeError(f'FFmpeg failed (exit code {code}): {detail or "no output"}')
    return result


def read_frame(path, attempts=5):
    """Read a rendered still with retries; a failing disk returns unreadable files under load."""
    import cv2
    path = Path(path)
    for _ in range(attempts):
        frame = cv2.imread(str(path))
        if frame is not None and frame.size:
            return frame
        time.sleep(1.0)
    raise RuntimeError(f'Unreadable rendered frame after {attempts} attempts: {path}')


def cleanup_intermediates(folder):
    """Delete per-frame scratch files once a render finishes (or fails).

    Every render regenerates them from the job script, but a single portrait
    video can leave behind several GB of frame_*.png / seq-* stills if they are
    kept. Small inputs (scene art, narration mp3, subtitles, logs) are retained.
    """
    folder = Path(folder)
    for pattern in ('frame_*.png', 'frame_*.jpg', 'full.wav', 'clip-*.mp4', 'timeline.json'):
        for path in folder.glob(pattern):
            path.unlink(missing_ok=True)
    for seq in folder.glob('seq-*'):
        shutil.rmtree(seq, ignore_errors=True)
    shutil.rmtree(folder / 'portrait', ignore_errors=True)


def render(points, folder, day, voice, progress, kind='history', rate='+15%', pitch='+0Hz', volume='+0%'):
    # Imported lazily so the API, login and scheduler still start when the optional video packages are absent.
    try:
        from moviepy import VideoFileClip
    except ImportError as exc:
        raise RuntimeError('Video packages are not installed. Run: pip install -r requirements-video.txt') from exc
    folder = Path(folder)
    try:
        return render_scenes(points, folder, day, voice, progress, kind, rate, pitch, volume, VideoFileClip)
    finally:
        # Also runs on failure so a crashed render never leaves multi-GB stills behind.
        try:
            cleanup_intermediates(folder)
        except OSError:
            log.warning('Could not clean intermediate frames in %s', folder)


def render_scenes(points, folder, day, voice, progress, kind, rate, pitch, volume, VideoFileClip):
    """Portrait short-video pipeline for photo/illustration kinds.

    Topic frames -> narration with word timings -> animated/moving scenes
    (provider AI clips or local Ken Burns/parallax) -> crossfade timeline ->
    word-level Tamil subtitles -> ambient bed -> one FFmpeg render.
    """
    import imageio_ffmpeg
    import cv2

    from . import encoder
    from . import motion
    from . import video_gen
    from . import wan
    from .cues import build_phrases, speech_with_cues, write_srt
    from .stock_photos import prepare_backgrounds

    width, height = settings.VIDEO_OUTPUT_WIDTH, settings.VIDEO_OUTPUT_HEIGHT
    fps = settings.VIDEO_FPS
    sample_rate = 44100
    lead, tail, cross = 0.40, 0.55, 0.50

    background = prepare_backgrounds(points, kind, folder, progress)
    from .theme import theme_for
    theme = theme_for(kind)
    progress('Rendering Tamil scene frames with Chromium')
    (folder / 'frames.json').write_text(json.dumps(
        {'points': points, 'day': day, 'kind': kind, 'backgrounds': background,
         'theme': {'accent': theme['accent'], 'badge': theme['badge']}}, ensure_ascii=False), encoding='utf-8')
    render_frames(folder)
    # The text is rendered as a separate transparent PNG so the camera move is
    # applied only to the background photo. Without this the Ken Burns zoom also
    # zoomed the words, which is exactly what looked "zoomed in" on Facebook.
    overlays = [_prepare_overlay(folder / f'overlay-{index + 1}.png', (width, height))
                for index in range(len(points))]

    # 1) Narration first: exact voice durations and word timings drive everything.
    scenes = []
    for index, point in enumerate(points, 1):
        progress(f'Tamil voice and word timings {index}/{len(points)}')
        audio_path = folder / f'voice-{index}.mp3'
        # `speech` is an optional natural-Tamil sentence written for the ear;
        # display lines contain prices/symbols and are not always ideal to read.
        speech_text = point.get('speech') or '. '.join(point['lines'])
        cues = speech_with_cues(speech_text, audio_path, voice, rate, pitch, volume)
        duration = cues[-1]['end'] if cues else _probe_audio(audio_path, VideoFileClip)
        scenes.append({'cues': cues, 'duration': max(duration, 0.4)})

    content_count = len(points)
    raw = [s['duration'] + lead + tail for s in scenes]
    starts = [0.0]
    for i in range(1, content_count):
        starts.append(starts[-1] + raw[i - 1] - cross)
    # The Like / Share / Subscribe end-card is one more scene at the tail.
    outro_seconds = max(2.0, float(settings.OUTRO_SECONDS))
    starts.append(starts[-1] + raw[-1] - cross)
    raw.append(outro_seconds)
    scene_count = content_count + 1
    total = starts[-1] + raw[-1]

    # 2) Moving scene visuals: Wan 2.2 AI clip (opt-in), else an external AI
    # provider clip, else local animation. Wan is budgeted to the opening scene
    # because it needs minutes of GPU time per second of footage.
    wan_ok = set()
    wan_done = set()
    if wan.enabled_for(kind) and wan.available():
        for index in range(min(settings.WAN_SCENES, content_count)):
            progress(f'Generating AI video with Wan 2.2 for scene {index + 1}')
            if wan.generate(folder / f'scene-{index + 1}.png',
                            wan.prompt_for(points[index], index),
                            folder / f'wan-{index + 1}.mp4', seed=index + 7, progress=progress):
                wan_ok.add(index)
            else:
                progress(f'Scene {index + 1}: Wan 2.2 unavailable; using local motion')

    provider = video_gen.provider_state()
    provider_ok = set()
    if provider['configured']:
        pending = [i for i in range(content_count) if i not in wan_ok]
        if pending:
            progress('Animating scenes with the video provider')
        for index in pending:
            ok = video_gen.generate_scene_clip(folder / f'scene-{index + 1}.png',
                                               video_gen.provider_prompt(points[index], index),
                                               raw[index], folder / f'clip-{index + 1}.mp4')
            if not ok:
                progress(f'Scene {index + 1}: provider failed; using local motion')
                break
            provider_ok.add(index)
    for index in range(content_count):
        progress(f'Building moving scene {index + 1}/{content_count}')
        base = folder / f'scene-{index + 1}.png'
        scene_dir = folder / f'seq-{index}'
        if index in wan_ok and wan.expand(folder / f'wan-{index + 1}.mp4', scene_dir,
                                          raw[index], fps, width, height):
            wan_done.add(index)
            continue
        if index in provider_ok:
            _extract_clip_frames(folder / f'clip-{index + 1}.mp4', scene_dir, fps, width, height)
        else:
            motion.render_scene(read_frame(base), scene_dir, raw[index], fps, index, seed=index + 1,
                                out_size=(width, height))
    progress('Rendering the Like / Share / Subscribe end-card')
    render_outro_frames(folder, content_count, outro_seconds, theme, fps)

    # 3) Crossfade timeline into one frame sequence whose times match starts[].
    progress('Compositing scenes with smooth transitions')
    frame_count = int(round(total * fps))
    scene_paths = [sorted((folder / f'seq-{i}').glob('f-*.*')) for i in range(scene_count)]
    scene_frames = [len(p) for p in scene_paths]
    missing = [i + 1 for i, count in enumerate(scene_frames) if count == 0]
    if missing:
        raise RuntimeError(f'Scenes produced no frames: {missing}')

    def scene_timing(scene_index, global_time):
        local = (global_time - starts[scene_index]) * fps
        index = max(0, min(int(round(local)), scene_frames[scene_index] - 1))
        return scene_paths[scene_index][index]

    for frame_idx in range(frame_count):
        global_time = frame_idx / fps
        active = [i for i in range(scene_count) if starts[i] <= global_time < starts[i] + raw[i]]
        if len(active) == 2:
            current, following = active
            alpha = (global_time - starts[following]) / cross
            first = read_frame(scene_timing(current, global_time))
            second = read_frame(scene_timing(following, global_time))
            # Crossfade only the moving backgrounds. The words are composited
            # afterwards from the dominant scene, so two sets of Tamil lines are
            # never visible on top of each other during a transition.
            frame = motion.crossfade(first, second, min(1.0, max(0.0, alpha)))
            overlay_scene = following if alpha >= 0.5 else current
            frame = _apply_overlay(frame, overlays[overlay_scene] if overlay_scene < len(overlays) else None)
        else:
            scene = active[0] if active else max(0, min(scene_count - 1, int(global_time * fps)))
            frame = read_frame(scene_timing(scene, global_time))
            frame = _apply_overlay(frame, overlays[scene] if scene < len(overlays) else None)
        frame = _draw_progress(frame, frame_idx / max(1, frame_count - 1), theme['accent_bgr'])
        target = folder / f'frame_{frame_idx:06d}.jpg'
        for attempt in range(5):
            try:
                if cv2.imwrite(str(target), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]) and target.stat().st_size > 0:
                    break
            except (cv2.error, OSError):
                pass
            time.sleep(0.5)
        else:
            raise OSError(f'Could not write composited frame {target}')

    # 4) Word-level Tamil subtitles on absolute timeline.
    phrases = []
    for index, scene in enumerate(scenes):
        scene_phrases = build_phrases(scene['cues'])
        if not scene_phrases and scene['cues']:
            scene_phrases = [{'text': ' '.join(c['text'] for c in scene['cues']),
                              'start': 0.0, 'end': scene['duration']}]
        for phrase in scene_phrases:
            start = starts[index] + phrase['start']
            end = min(starts[index] + phrase['end'], starts[index] + raw[index] - cross * 0.5)
            if end > start:
                phrases.append({'text': phrase['text'], 'start': start, 'end': end})
    write_srt(phrases, folder / 'subs.srt')
    if phrases and settings.BURN_SUBTITLES:
        _write_ass(phrases, folder / 'subs.ass', folder, kind, total)
    (folder / 'subtitles.json').write_text(json.dumps(phrases, ensure_ascii=False), encoding='utf-8')

    # 5) Soundtrack: narration placed at its scene times + ambient bed + whooshes.
    progress('Mixing narration, ambient bed and transition swells')
    _write_full_audio(folder, scenes, starts, raw, lead, cross, total, sample_rate,
                      [(starts[i], starts[i] + raw[i - 1]) for i in range(1, scene_count)])

    # 6) One FFmpeg render: animated background + static text overlay + soundtrack.
    progress('Encoding portrait MP4 with moving backgrounds and clean on-screen text')
    output = folder / 'history.mp4'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    head = [ffmpeg, '-y', '-framerate', str(fps), '-i', 'frame_%06d.jpg', '-i', 'full.wav']
    # The frames come from JPEG (full-range) but YouTube/Facebook expect
    # limited-range BT.709 HD. Without this the upload looks washed out and the
    # player has to guess the colour matrix.
    filters = ['scale=in_range=full:out_range=tv:out_color_matrix=bt709', 'setsar=1']
    if phrases and settings.BURN_SUBTITLES:
        filters.append('ass=subs.ass:fontsdir=fonts')
    head += ['-vf', ','.join(filters), '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11']
    tail = ['-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2',
            '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
            '-color_range', 'tv', '-movflags', '+faststart',
            '-shortest', 'history.mp4']
    codec, codec_name = encoder.video_args()
    try:
        run_ffmpeg(head + codec + tail, folder, 1800)
    except RuntimeError:
        # A driver update, a second encode session or a full VRAM pool must not
        # lose a render that already spent minutes compiling frames.
        if codec_name != 'nvenc':
            raise
        log.warning('NVENC encode failed in %s; retrying with libx264', folder)
        encoder.disable_nvenc()
        run_ffmpeg(head + encoder.x264_args() + tail, folder, 1800)

    credits = json.loads((folder / 'media-sources.json').read_text(encoding='utf-8'))
    for index, credit in enumerate(credits):
        if index in wan_done:
            credit['motion'] = 'wan-2.2-ai-clip'
        elif index in provider_ok:
            credit['motion'] = 'ai-provider-clip'
        else:
            credit['motion'] = 'local-animated'
    (folder / 'media-sources.json').write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding='utf-8')

    with VideoFileClip(str(output)) as check:
        if not check.audio or check.duration < 1:
            raise ValueError('Export validation failed: missing video or audio')
        return round(check.duration, 2)


def _prepare_overlay(path, size):
    """Load a transparent text layer once, cropped to its ink.

    The words cover a fraction of the portrait frame, so blending only that
    sub-rectangle instead of the full 1080x1920 keeps the compositing pass
    cheap: the mask, its inverse and the premultiplied colour are computed
    here (once per scene), not for every one of the ~1,500 frames.
    """
    import cv2
    import numpy as np
    overlay = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if overlay is None or overlay.ndim != 3 or overlay.shape[2] != 4:
        return None
    width, height = size
    if overlay.shape[0] != height or overlay.shape[1] != width:
        overlay = cv2.resize(overlay, (width, height), interpolation=cv2.INTER_AREA)
    alpha = overlay[:, :, 3]
    x, y, w, h = cv2.boundingRect((alpha > 6).astype(np.uint8))
    if w <= 0 or h <= 0:
        return None
    patch = overlay[y:y + h, x:x + w]
    mask = patch[:, :, 3:4].astype(np.float32) / 255.0
    colour = patch[:, :, :3].astype(np.float32)
    return {'x': x, 'y': y, 'w': w, 'h': h, 'mask': mask,
            'inverse': 1.0 - mask, 'premultiplied': colour * mask}


def _apply_overlay(frame, overlay):
    """Composite the static words over an animated frame, preserving the photo behind."""
    if not overlay:
        return frame
    import numpy as np
    frame_h, frame_w = frame.shape[:2]
    x = overlay['x']
    y = overlay['y']
    w = min(overlay['w'], frame_w - x)
    h = min(overlay['h'], frame_h - y)
    if w <= 0 or h <= 0:
        return frame
    region = frame[y:y + h, x:x + w]
    blended = region.astype(np.float32) * overlay['inverse'][:h, :w] + overlay['premultiplied'][:h, :w]
    np.clip(blended, 0, 255, out=blended)
    frame[y:y + h, x:x + w] = blended.astype(np.uint8)
    return frame


def _draw_progress(frame, fraction, colour_bgr, height=12):
    """Burn a thin retention progress bar into the top edge of a composited frame."""
    import numpy as np
    if frame.dtype != np.uint8:
        frame = np.clip(frame, 0, 255).astype(np.uint8)
    band = min(int(height), frame.shape[0])
    frame[:band] = (frame[:band].astype(np.float32) * 0.45).astype(np.uint8)
    filled = int(round(frame.shape[1] * max(0.0, min(1.0, fraction))))
    if filled > 0:
        frame[:band, :filled] = colour_bgr
    return frame


def _probe_audio(path, VideoFileClip):
    from moviepy import AudioFileClip
    try:
        with AudioFileClip(str(path)) as clip:
            return clip.duration
    except Exception:
        return 3.0


def _decode_mono(path, sample_rate):
    from moviepy import AudioFileClip
    import numpy as np
    with AudioFileClip(str(path)) as clip:
        array = clip.to_soundarray(fps=sample_rate)
    if array.ndim == 2:
        array = array.mean(axis=1)
    return array.astype(np.float64)


def _moving_average(values, window):
    """Centred moving average in O(n) — no convolution over multi-million samples."""
    import numpy as np
    total = len(values)
    window = max(1, min(int(window), total))
    cumulative = np.concatenate(([0.0], np.cumsum(values, dtype=np.float64)))
    starts = np.clip(np.arange(total) - window // 2, 0, total)
    ends = np.clip(starts + window, 0, total)
    return (cumulative[ends] - cumulative[starts]) / np.maximum(1, ends - starts)


def _duck_gain(voice, sample_rate):
    """Gain curve that pushes the ambient bed under the narration (~-7 dB).

    Smooth 30 ms level detection plus a 250 ms attack/release window: the bed
    never pumps audibly between Tamil syllables, but the words always win.
    """
    import numpy as np
    level = _moving_average(np.abs(voice), int(0.030 * sample_rate))
    loud = level[level > 1e-4]
    reference = float(np.percentile(loud, 92)) if loud.size else 1.0
    level = np.clip(level / max(reference, 1e-6), 0.0, 1.0)
    level = _moving_average(level, int(0.250 * sample_rate))
    return (1.0 - 0.60 * np.clip(level, 0.0, 1.0)).astype(np.float32)


def _write_full_audio(folder, scenes, starts, raw, lead, cross, total, sample_rate, transitions):
    import numpy as np
    samples = int(round(total * sample_rate))
    voice = np.zeros(samples)
    timeline = np.arange(samples) / sample_rate
    for index, scene in enumerate(scenes):
        take = _decode_mono(folder / f'voice-{index + 1}.mp3', sample_rate)
        offset = int(round((starts[index] + lead) * sample_rate))
        end = min(offset + len(take), samples)
        voice[offset:end] += take[:end - offset]
    bed = _bed(timeline, sample_rate)
    swells = np.zeros(samples)
    for start, _overlap in transitions:
        d = timeline - (start + cross * 0.5)
        mask = (d >= 0) & (d < 0.60)
        frequency = 170 + (d / 0.60) * 540
        envelope = np.sin(np.pi * np.clip(d / 0.60, 0.0, 1.0)) ** 1.5
        swells = np.where(mask, np.sin(2 * np.pi * frequency * d) * envelope * 0.06, swells)
    # Sidechain-style ducking keeps the narration clearly in front of the pad,
    # and the soft limiter stops AAC from clipping on plosives.
    duck = _duck_gain(voice, sample_rate)
    master = voice * 0.98 + bed * 0.55 * duck + swells * 0.7 * duck
    master = np.tanh(master * 1.05) / np.tanh(1.05)
    master = np.clip(master, -1.0, 1.0)
    stereo = np.column_stack((master, master))
    pcm = (stereo * 32767.0).astype('<i2')
    with wave.open(str(folder / 'full.wav'), 'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def _bed(timeline, sample_rate):
    """Slow ambient pad + gentle arpeggio, low in the mix."""
    import numpy as np
    chords = [(220.0, 261.63, 329.63), (196.0, 246.94, 293.66),
              (174.61, 220.0, 261.63), (220.0, 246.94, 293.66)]
    eight = (timeline / 8.0).astype(int) % 4
    tone = np.take(np.array(chords, dtype=float), eight, axis=0)
    swell = 0.5 + 0.5 * np.sin(2 * np.pi * (timeline / 8.0))
    pad = (np.sin(2 * np.pi * tone[:, 0] * timeline)
           + np.sin(2 * np.pi * tone[:, 1] * timeline)
           + np.sin(2 * np.pi * tone[:, 2] * timeline)) * 0.030 * swell
    quarter = (timeline % 2.0) / 2.0
    arp_note = (timeline // 0.5 % 4).astype(int)
    tones = np.take(np.array([440.0, 523.25, 659.25, 493.88], dtype=float), arp_note)
    decay = np.clip(1 - quarter * 4.0, 0, 1) ** 2
    arp = np.sin(2 * np.pi * tones * timeline) * 0.012 * decay
    drone = np.sin(2 * np.pi * 55.0 * timeline) * 0.020
    return pad + arp + drone


def _extract_clip_frames(clip_path, out_dir, fps, width, height):
    import imageio_ffmpeg
    import shutil
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    run_ffmpeg([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-i', str(clip_path),
                '-vf', f'fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,'
                       f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1',
                '-frames:v', str(int(round(fps * 90))), str(out_dir / 'f-%06d.png')],
               out_dir, 900)


def _highlight(text, accent_ass):
    """Wrap numbers (and short exclamations) in the accent colour so the eye
    catches the key facts while the caption is on screen."""
    import re
    text = text.replace('{', '').replace('}', '')

    def mark(match):
        return f'{{\\c&H{accent_ass}&\\b1}}{match.group(0)}{{\\r}}'

    return re.sub(r'\d+(?:[.,]\d+)*|\S{1,12}[!?]', mark, text)


def _write_ass(phrases, path, folder, kind='', total=0.0):
    """Bake readable phrase subtitles plus the show hook, a highlighted caption
    track and the end call-to-action. Nirmala UI is copied next to the video."""
    from .theme import theme_for
    font = settings.SUBTITLE_FONT
    theme = theme_for(kind)
    accent = theme['accent_ass']
    font_dir = folder / 'fonts'
    font_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(settings.HISTORY_FONT, font_dir / 'subfont.ttf')
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {settings.VIDEO_OUTPUT_WIDTH}
PlayResY: {settings.VIDEO_OUTPUT_HEIGHT}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{font},36,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,1,2,60,60,220,1
Style: Hook,{font},44,&H00{accent},&H00FFFFFF,&H00101828,&H00000000,1,0,0,0,100,100,0.5,0,1,0,1,8,60,60,220,1
"""
    events = ['[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    if total > 0:
        hook_end = min(2.90, max(0.7, total - 0.4))
        events.append(f"Dialogue: 0,{_ass_time(0.10)},{_ass_time(hook_end)},Hook,,0,0,0,,{theme['hook']}")
    for phrase in phrases:
        events.append(f"Dialogue: 0,{_ass_time(phrase['start'])},{_ass_time(phrase['end'])},Sub,,0,0,0,,{_highlight(phrase['text'], accent)}")
    path.write_text(header + '\n'.join(events), encoding='utf-8')


def _ass_time(seconds):
    """ASS timestamps are H:MM:SS.cc — the fraction is CENTIseconds (exactly two
    digits). libass reads a longer fraction as a whole number of centiseconds, so
    emitting milliseconds here shifts every subtitle far later in the clip."""
    centis = int(round(max(0.0, seconds) * 100))
    hours, remainder = divmod(centis, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centis = divmod(remainder, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{centis:02}"


def _bed_name(kind):
    return 'background bed'