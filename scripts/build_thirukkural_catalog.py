"""Build the Thirukkural catalogue from the bundled raw corpus (one-time build).

Source: tk120404/thirukkural (public-domain Sangam text + commentaries).
We keep the first two sections — அறத்துப்பால் (Virtue) and பொருட்பால் (Wealth),
kurals 1-1080 — so the daily show stays family friendly, and pair the Tamil
couplet with Mu. Varadarajan's standard Tamil explanation, wrapped into short
on-screen lines.

Run from the repo root:
    python scripts/build_thirukkural_catalog.py RAW_JSON OUT_JSON
"""
import json
import re
import sys
from pathlib import Path

MAX_LINE = 150
MAX_KURAL = 1080  # Virtue + Wealth sections only


def clean(text):
    text = re.sub(r'[`\u201c\u201d"]+', '', text or '')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\d+', '', text)  # the narration voice reads digits unpredictably
    return re.sub(r'\s+', ' ', text).strip(' .,')


def wrap(text, limit=MAX_LINE):
    lines, current = [], ''
    for word in text.split():
        if current and len(current) + 1 + len(word) > limit:
            lines.append(current)
            current = word
        else:
            current = (current + ' ' + word).strip()
    if current:
        lines.append(current)
    return lines


def section_for(number):
    return 'அறத்துப்பால்' if number <= 380 else 'பொருட்பால்'


def build(raw_path, out_path):
    data = json.loads(Path(raw_path).read_text(encoding='utf-8'))
    raw = data['kural'] if isinstance(data, dict) else data
    items = []
    for entry in raw:
        number = int(entry['Number'])
        if number > MAX_KURAL:
            continue
        couplet = [clean(entry['Line1']), clean(entry['Line2'])]
        meaning = clean(entry.get('mv') or entry.get('sp') or entry.get('mk') or '')
        english = (entry.get('Translation') or entry.get('explanation') or '').strip()
        lines = [line for line in couplet if line] + wrap(meaning)
        chapter = (number - 1) // 10 + 1
        items.append({
            'id': f'kural-{number}',
            'theme': section_for(number),
            'title': f'குறள் {number}',
            'title_en': english,
            'topic': 'book',
            'photo': 'ancient tamil palm leaf manuscript',
            'lines': lines,
            'facts': [f'{section_for(number)} · அதிகாரம் {chapter}', english],
            'links': [{'title': 'Thirukkural — Project Madurai (public domain text)',
                       'link': 'https://www.projectmadurai.org/pm_etexts/utf8/pmuni0001.html'}],
        })
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding='utf-8')
    return len(items)


if __name__ == '__main__':
    count = build(sys.argv[1], sys.argv[2])
    print(f'wrote {count} kurals')
