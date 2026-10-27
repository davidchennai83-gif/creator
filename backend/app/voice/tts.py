"""Shared text-to-speech for the platform.

One engine used by both the video renderer's narration *and* the 24x7 voice agent,
so spoken announcements use the very same Tamil neural voices as the channel.
Primary engine is `edge-tts` (free Microsoft neural voices). If the network is
unavailable the agent falls back to the offline Windows SAPI voice, so the agent
stays audible even without internet.
"""
import asyncio
import logging
import subprocess
from pathlib import Path

from app.config.settings import settings

log = logging.getLogger(__name__)

VOICES = {
    "ta-IN-PallaviNeural": "Tamil · India · female (Pallavi) ★",
    "ta-IN-ValluvarNeural": "Tamil · India · male (Valluvar) ★",
    "ta-LK-KumarNeural": "Tamil · Sri Lanka · male (Kumar)",
    "ta-LK-SaranyaNeural": "Tamil · Sri Lanka · female (Saranya)",
    "ta-MY-KaniNeural": "Tamil · Malaysia · female (Kani)",
    "ta-MY-SuryaNeural": "Tamil · Malaysia · male (Surya)",
    "ta-SG-AnbuNeural": "Tamil · Singapore · male (Anbu)",
    "ta-SG-VenbaNeural": "Tamil · Singapore · female (Venba)",
    "en-IN-NeerjaNeural": "English (India) · female",
    "en-IN-NeerjaExpressiveNeural": "English (India) · female (expressive)",
    "en-IN-PrabhatNeural": "English (India) · male",
}
DEFAULT_VOICE = "ta-IN-PallaviNeural"
# Every Tamil voice edge-tts offers, for the video projects' voice pickers.
TAMIL_VOICES = (
    "ta-IN-PallaviNeural", "ta-IN-ValluvarNeural",
    "ta-LK-KumarNeural", "ta-LK-SaranyaNeural",
    "ta-MY-KaniNeural", "ta-MY-SuryaNeural",
    "ta-SG-AnbuNeural", "ta-SG-VenbaNeural",
)


def root() -> Path:
    path = Path(settings.STORAGE_PATH) / "voice"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _synth(text, destination, voice, rate, pitch, volume):
    import edge_tts
    await asyncio.wait_for(
        edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume).save(str(destination)),
        timeout=120)


def synth(text, destination=None, voice=DEFAULT_VOICE, rate="+0%", pitch="+0Hz", volume="+0%") -> Path:
    """Synthesise speech to an mp3 (blocking). Call from a worker thread, not an event loop."""
    destination = Path(destination) if destination else (root() / "last.mp3")
    destination.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_synth(text, destination, voice, rate, pitch, volume))
    return destination


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def to_wav(mp3_path, wav_path=None):
    wav_path = Path(wav_path) if wav_path else Path(mp3_path).with_suffix(".wav")
    try:
        subprocess.run([ffmpeg_exe(), "-y", "-i", str(mp3_path), "-ar", "22050", "-ac", "1", str(wav_path)],
                       capture_output=True, timeout=120)
    except Exception as exc:
        log.warning("mp3->wav failed: %s", exc)
        return None
    return wav_path if wav_path.exists() else None


def play(path) -> bool:
    """Best-effort playback through the PC speakers (Windows SoundPlayer)."""
    path = Path(path)
    if path.suffix.lower() != ".wav":
        wav = to_wav(path)
        if not wav:
            return False
        path = wav
    ps = f"(New-Object Media.SoundPlayer '{path}').PlaySync()"
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                                capture_output=True, timeout=300)
        return result.returncode == 0
    except Exception as exc:
        log.warning("speaker playback failed: %s", exc)
        return False


def sapi_speak(text) -> bool:
    """Offline fallback: speak with the built-in Windows voice (no internet needed)."""
    safe = str(text).replace("'", "''")[:600]
    ps = ("Add-Type -AssemblyName System.Speech; "
          "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          f"$s.Speak('{safe}')")
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                                capture_output=True, timeout=300)
        return result.returncode == 0
    except Exception as exc:
        log.warning("SAPI fallback failed: %s", exc)
        return False


def speak(text: str, voice=DEFAULT_VOICE, play_it=True) -> dict:
    """Synthesise (and optionally play) one announcement. Never raises."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "reason": "empty"}
    out = {"ok": True, "voice": voice, "chars": len(text), "audio": None, "played": False, "engine": "edge-tts"}
    try:
        mp3 = synth(text, root() / "last.mp3", voice)
        out["audio"] = str(mp3)
        if play_it:
            out["played"] = play(mp3)
    except Exception as exc:
        log.warning("edge-tts failed (%s); using offline SAPI voice", exc)
        out["engine"] = "sapi"
        out["ok"] = True
        out["error"] = str(exc)
        if play_it:
            out["played"] = sapi_speak(text)
    return out
