import sys
sys.path.insert(0, r'G:\my_tool\creator-platform\backend')
from app.integrations.video_provider import get_video_provider
print('Import OK')
provider = get_video_provider()
print('Provider:', type(provider))