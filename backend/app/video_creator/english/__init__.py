"""Spoken English Daily — three everyday English phrases with their Tamil meaning.

Curated catalogue (no network, no model): each day three different phrases are
chosen from twenty, and the daily line-up stays unique for 1,140 days, so the
show runs for years without repeating a combination. Every line keeps a Tamil
word so the Tamil narration voice reads the phrase naturally, the way a spoken
English class for Tamil learners sounds.
"""
from pathlib import Path

from ..daily_catalog import make_creator

PER_EDITION = 3

create_script = make_creator(Path(__file__).parent, PER_EDITION, 'phrases')
