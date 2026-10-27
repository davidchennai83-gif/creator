"""Check that the optional video-provider adapter imports (diagnostic helper)."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from app.integrations.video_provider import get_video_provider

print('Import OK')
provider = get_video_provider()
print('Provider:', type(provider))
