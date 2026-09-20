from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import httpx
from app.api.deps import editor, unavailable
from app.schemas.common import success
from app.utils import get_ai_provider

router = APIRouter()

class Prompt(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)

@router.post("/generate", dependencies=[Depends(editor)])
def generate(data: Prompt):
    """Generate content from AI prompt.
    
    Note: Video generation feature is planned and ready to be enabled
    when the video AI provider environment is fully configured.
    Currently returns 501 Not Implemented for video generation.
    """
    try:
        # For now, use the standard AI provider for text generation
        provider = get_ai_provider()
        result = provider.generate(data.prompt)
        return success(asdict(result))
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "AI provider unavailable or returned invalid output")
    except NotImplementedError:
        raise HTTPException(501, "Video generation feature coming soon - provider configuration needed")

@router.get("/health")
def health():
    try:
        healthy = get_ai_provider().health_check()
    except NotImplementedError:
        healthy = False
    if not healthy:
        raise HTTPException(503, "AI provider unavailable")
    return success({"healthy": True})

@router.post("/generate-script")
@router.post("/analyze-analytics")
def pending():
    unavailable()