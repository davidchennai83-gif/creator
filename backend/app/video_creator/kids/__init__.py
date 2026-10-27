"""Kids Learning — three simple Tamil basics a day for young children.

Curated catalogue (no network, no model). Three items are chosen each day from
thirty-six, and the daily line-up stays unique for 7,140 days. Content is
family safe and factual: the twelve Tamil vowels (உயிர் எழுத்து), the counting
words ஒன்று–எட்டு, common animals and basic colours, each with one example a
small child can follow.
"""
from pathlib import Path

from ..daily_catalog import make_creator

PER_EDITION = 3

create_script = make_creator(Path(__file__).parent, PER_EDITION, 'items')
