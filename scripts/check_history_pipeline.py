"""Explicit live smoke test; output is separate from user jobs."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.video_creator.scripts import create_script
from app.video_creator.render import render
from app.video_creator.jobs import root

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--kind', choices=['history', 'indian-law', 'make-money'], default='history')
    parser.add_argument('--script', type=Path, help='Reuse a previously generated smoke-test script')
    args = parser.parse_args()
    folder = root() / ('smoke-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    folder.mkdir()
    day = datetime.now().date()
    if args.kind == 'indian-law':
        from app.video_creator.indian_law import create_script
    elif args.kind == 'make-money':
        from app.video_creator.make_money import create_script
    points = json.loads(args.script.read_text(encoding='utf-8')) if args.script else create_script(day, lambda message: print(message, flush=True))
    (folder / 'script.json').write_text(json.dumps(points, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Validated {len(points)} Tamil points. Output: {folder}', flush=True)
    if args.render:
        seconds = render(points, folder, day.isoformat(), 'ta-IN-PallaviNeural', lambda message: print(message, flush=True), args.kind)
        print(f'Video with audio verified: {seconds} seconds', flush=True)
