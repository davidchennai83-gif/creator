"""Voice agent API: status, on-demand speech, config and narration health."""
import asyncio
import hashlib
import re

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import editor
from app.schemas.common import success
from app.voice import agent, tts
from app.voice.narration import day_videos

router = APIRouter()


class SayRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    voice: str | None = None
    play: bool = True


class ConfigRequest(BaseModel):
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=720)
    voice: str | None = None
    speak_heartbeat: bool | None = None
    speak_alerts: bool | None = None


@router.get("/status")
def get_status():
    data = agent.state()
    return success({**data, "voices": tts.VOICES, "running": agent._STARTED.is_set()})


@router.get("/narration")
def get_narration():
    videos = day_videos()
    return success({"videos": videos,
                    "all_narrated": all(v["has_narration"] for v in videos if v["status"] == "complete") if videos else True})


@router.post("/say")
async def say(data: SayRequest, user=Depends(editor)):
    if data.voice and data.voice not in tts.VOICES:
        return JSONResponse({"success": False, "message": "Unknown voice"}, status_code=400)
    if data.play:
        result = await asyncio.to_thread(agent.speech_now, data.text, data.voice)
    else:
        result = await asyncio.to_thread(tts.speak, data.text, data.voice or tts.DEFAULT_VOICE, False)
    return success(result)


@router.post("/config")
def set_config(data: ConfigRequest, user=Depends(editor)):
    cfg = agent.save_config(data.model_dump(exclude_none=True))
    return success(cfg)


@router.post("/check")
async def check_now(user=Depends(editor)):
    return success(await asyncio.to_thread(agent.tick, True))


@router.get("/audio")
def latest_audio():
    path = tts.root() / "last.mp3"
    if not path.is_file():
        return JSONResponse({"success": False, "message": "No announcement yet"}, status_code=404)
    return FileResponse(path, media_type="audio/mpeg", filename="voice-agent.mp3")


SAMPLE_TEXT = "வணக்கம்! இது உங்கள் வீடியோ நரேஷன் மாதிரி. சரித்திரம், சட்டம், பணம், கார்ட்டூன் — எல்லா வீடியோவுக்கும் இந்தக் குரல் பொருத்தமா என்று கேளுங்கள்."


@router.get("/sample")
async def sample(voice: str = tts.DEFAULT_VOICE, text: str = SAMPLE_TEXT, rate: str = '+0%'):
    """Synthesise a short preview of a voice so it can be auditioned before choosing."""
    if voice not in tts.VOICES:
        return JSONResponse({"success": False, "message": "Unknown voice"}, status_code=400)
    if not re.fullmatch(r'[+-]\d{1,3}%', rate):
        rate = '+0%'
    text = (text or SAMPLE_TEXT)[:400]
    key = hashlib.md5(f"{voice}:{rate}:{text}".encode("utf-8")).hexdigest()[:12]
    path = tts.root() / f"sample-{key}.mp3"
    if not path.is_file():
        await asyncio.to_thread(tts.synth, text, path, voice, rate)
    return FileResponse(path, media_type="audio/mpeg", filename=f"sample-{voice}.mp3")
