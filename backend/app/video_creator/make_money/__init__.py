"""How to Make Money: date-based selection of five practical ideas, narrated in standard written Tamil."""
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from ..scripts import Point

HERE = Path(__file__).parent
EPOCH = date(2026, 1, 1)
PER_EDITION = 5
MAX_LINE = 110  # longer lines make the renderer shrink the font below a readable size


class MoneyPoint(Point):
    lines: list[str] = Field(min_length=4, max_length=4)

    @field_validator('lines')
    @classmethod
    def fits_frame(cls, lines):
        if any(len(line) > MAX_LINE for line in lines):
            raise ValueError(f'Each line must be {MAX_LINE} characters or fewer to fit the video frame')
        return lines


class MoneyScript(BaseModel):
    points: list[MoneyPoint] = Field(min_length=5, max_length=5)


@lru_cache(maxsize=1)
def catalog():
    return json.loads((HERE / 'catalog.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def tamil_lines():
    return json.loads((HERE / 'tamil.json').read_text(encoding='utf-8'))


def daily_ideas(day: date):
    """Five ideas per date. Consecutive days never overlap; the cycle repeats after len(catalog) / 5 days."""
    ideas = catalog()
    start = ((day - EPOCH).days * PER_EDITION) % len(ideas)
    return [ideas[(start + i) % len(ideas)] for i in range(PER_EDITION)]


def create_script(day: date, progress):
    ideas = daily_ideas(day)
    progress('Preparing four Tamil lines for each of five money ideas')
    tamil = tamil_lines()
    result = MoneyScript(points=[MoneyPoint(source_id=i, lines=tamil[idea['id']]) for i, idea in enumerate(ideas)])
    return [dict(source_id=p.source_id, title=ideas[p.source_id]['title_ta'], title_en=ideas[p.source_id]['title'],
                 year='', lines=p.lines, text=' '.join(ideas[p.source_id]['facts']),
                 topic=ideas[p.source_id]['topic'], photo_query=ideas[p.source_id]['photo'],
                 links=ideas[p.source_id]['links'])
            for p in result.points]
