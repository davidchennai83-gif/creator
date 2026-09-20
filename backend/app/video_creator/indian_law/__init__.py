"""Indian central Acts: date-based selection and source-grounded Tamil explanations."""
import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field
from ..scripts import Point


class LawPoint(Point):
    lines: list[str] = Field(min_length=4, max_length=4)


class LawScript(BaseModel):
    points: list[LawPoint] = Field(min_length=5, max_length=5)


def daily_acts(day: date):
    catalog = json.loads(Path(__file__).with_name('catalog.json').read_text(encoding='utf-8'))
    start = ((day - date(2026, 1, 1)).days * 5) % len(catalog)
    return [catalog[(start + i) % len(catalog)] for i in range(5)]


def create_script(day: date, progress):
    acts = daily_acts(day)
    progress('Preparing four Tamil reference lines for each of five Acts')
    tamil = json.loads(Path(__file__).with_name('tamil.json').read_text(encoding='utf-8'))
    result = LawScript(points=[LawPoint(source_id=i, lines=tamil[a['id']]) for i, a in enumerate(acts)])
    return [dict(source_id=p.source_id, title=acts[p.source_id]['title'], year=acts[p.source_id]['year'],
                 lines=p.lines, text=' '.join(acts[p.source_id]['facts']), sections=acts[p.source_id]['sections'],
                 links=[{'title': 'India Code — search the exact Act title and cited sections', 'link': 'https://www.indiacode.nic.in/'}])
            for p in result.points]
