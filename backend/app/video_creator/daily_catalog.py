"""Deterministic daily selection engine for catalogue-based video projects.

A catalogue project ships a ``catalog.json``: a list of items shaped like

    {"id": "greetings", "theme": "small talk", "title": "Good morning",
     "title_en": "Good morning", "topic": "chat", "photo": "people greeting",
     "lines": ["Tamil line 1", "Tamil line 2", ...],
     "facts": ["English reference for the review panel", ...],
     "links": [{"title": "...", "link": "https://..."}]}

``lines`` are the Tamil narration; the renderer joins them with '. ' and speaks
them with the chosen Tamil voice. Every line must contain Tamil script and stay
short enough that the frame keeps a readable font size.

Why a combination stride instead of a plain slice: the older kinds pick a
contiguous block of five items a day, so a 30-item catalogue repeats every 6
days. Here each day is a distinct **set** chosen by striding through the space
of all k-combinations (combinadic unranking). Even a small catalogue then has a
cycle length of ``C(n, k)`` days, and consecutive days share few items, so a
year of videos never repeats a daily line-up. ``cycle_days`` reports the exact
figure so a project can assert it covers at least a year.
"""
import json
import math
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from .scripts import Point

EPOCH = date(2026, 1, 1)
MAX_LINE = 150          # longer lines shrink the on-screen font below readability
MIN_CYCLE_DAYS = 365    # every catalogue project must cover at least a year


class CataloguePoint(Point):
    """One narrated scene of a catalogue video (a couplet, phrase or fact)."""
    lines: list[str] = Field(min_length=2, max_length=6)


class CatalogueScript(BaseModel):
    points: list[CataloguePoint] = Field(min_length=1, max_length=12)


def day_index(day):
    """Whole days since the fixed epoch (never negative for supported dates)."""
    return max(0, (day - EPOCH).days)


def combination_at(index, n, k):
    """Unrank ``index`` into the k-combination of ``range(n)`` (lexicographic)."""
    if k < 0 or k > n or not 0 <= index < math.comb(n, k):
        raise ValueError(f'combination index {index} out of range for n={n}, k={k}')
    result = []
    start = 0
    for remaining in range(k):
        choose = k - 1 - remaining
        candidate = start
        while True:
            block = math.comb(n - 1 - candidate, choose)
            if index < block:
                result.append(candidate)
                start = candidate + 1
                break
            index -= block
            candidate += 1
    return result


def stride_for(total, k):
    """A step through the combination space that is coprime to its size.

    Coprime means the stride visits every index before repeating, so the cycle
    is the full ``C(n, k)``. Starting near ``total / k`` also keeps consecutive
    days far apart, so their daily sets barely overlap.
    """
    step = max(1, total // max(1, k))
    while math.gcd(step, total) != 1:
        step += 1
    return step


def cycle_days(count, per_day):
    """How many consecutive days before the first daily set can repeat."""
    k = min(per_day, count)
    if k <= 0:
        return 1
    return math.comb(count, k)


def select_positions(count, day, per_day):
    """``per_day`` distinct item positions for ``day`` with a long, fresh cycle."""
    k = min(per_day, count)
    if k <= 0:
        return []
    total = math.comb(count, k)
    step = stride_for(total, k)
    index = (day_index(day) * step) % total
    return combination_at(index, count, k)


@lru_cache(maxsize=8)
def _load(folder):
    return json.loads((Path(folder) / 'catalog.json').read_text(encoding='utf-8'))


def load_catalog(folder):
    """The catalogue for a project directory (cached, read-only)."""
    return _load(str(folder))


def build_points(items, day, per_day):
    """The renderer-shaped points for one day, validated against the schema."""
    picks = [items[i] for i in select_positions(len(items), day, per_day)]
    validated = CatalogueScript(points=[CataloguePoint(source_id=i, lines=item['lines'])
                                        for i, item in enumerate(picks)])
    points = []
    for i, item in enumerate(picks):
        points.append({
            'source_id': i,
            'title': item.get('title', ''),
            'title_en': item.get('title_en', ''),
            'text': ' '.join(item.get('facts', [])),
            'lines': validated.points[i].lines,
            'topic': item.get('topic', 'book'),
            'photo_query': item.get('photo', ''),
            'links': item.get('links', []),
        })
    return points


def make_creator(folder, per_day, label='items'):
    """Build a ``create_script(day, progress)`` for a catalogue project."""
    folder = Path(folder)

    def create_script(day, progress):
        items = load_catalog(folder)
        days = cycle_days(len(items), per_day)
        if days < MIN_CYCLE_DAYS:
            raise ValueError(f'{folder.name} catalogue only covers {days} days; needs at least {MIN_CYCLE_DAYS}')
        progress(f'Selecting {min(per_day, len(items))} {label} for {day.isoformat()}')
        return build_points(items, day, per_day)

    return create_script
