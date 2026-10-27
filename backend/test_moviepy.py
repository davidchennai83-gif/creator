"""Check the MoviePy text-clip API this machine provides (diagnostic helper).

moviepy>=2 removed the `moviepy.editor` module; this script reports which API
the installed version exposes so render requirements can be matched to it.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

try:
    from moviepy.editor import TextClip
    print('moviepy.editor imported OK')
    print('TextClip imported OK')
except ImportError as exc:
    print(f'moviepy.editor unavailable ({exc})')
    from moviepy import TextClip
    print('MoviePy 2 API: `from moviepy import TextClip` works')
