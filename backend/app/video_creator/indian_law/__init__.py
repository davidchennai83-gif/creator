"""Indian central Acts: date-based selection and source-grounded Tamil explanations.

Every scene opens by naming the Act and its year, then says in plain words what
it means. The spoken name comes from ``catalog.json`` (``title_ta``) and the gist
from line 1 of ``tamil.json``, so the Act can never be described before it is
named, and the order cannot drift between editions.
"""
import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field
from ..scripts import Point

HERE = Path(__file__).parent
MAX_LINE = 126  # a longer opener forces the law card below a readable font size


class LawPoint(Point):
    lines: list[str] = Field(min_length=4, max_length=4)


class LawScript(BaseModel):
    points: list[LawPoint] = Field(min_length=5, max_length=5)


def opening_line(act, tamil_lines):
    """Name the Act first, then its year, then the plain-words gist."""
    line = f'{act["title_ta"]}, {act["year"]} — {tamil_lines[0]}'
    if len(line) > MAX_LINE:
        raise ValueError(f'{act["id"]}: opening line is {len(line)} chars, over {MAX_LINE}')
    return line


def daily_acts(day: date):
    catalog = json.loads((HERE / 'catalog.json').read_text(encoding='utf-8'))
    start = ((day - date(2026, 1, 1)).days * 5) % len(catalog)
    return [catalog[(start + i) % len(catalog)] for i in range(5)]


def create_script(day: date, progress):
    acts = daily_acts(day)
    progress('Preparing four Tamil reference lines for each of five Acts')
    tamil = json.loads((HERE / 'tamil.json').read_text(encoding='utf-8'))
    lines = {a['id']: [opening_line(a, tamil[a['id']])] + tamil[a['id']][1:] for a in acts}
    result = LawScript(points=[LawPoint(source_id=i, lines=lines[a['id']]) for i, a in enumerate(acts)])
    return [dict(source_id=p.source_id, title=acts[p.source_id]['title'], year=acts[p.source_id]['year'],
                 lines=p.lines, text=' '.join(acts[p.source_id]['facts']), sections=acts[p.source_id]['sections'],
                 links=[{'title': 'India Code — search the exact Act title and cited sections', 'link': 'https://www.indiacode.nic.in/'}])
            for p in result.points]
