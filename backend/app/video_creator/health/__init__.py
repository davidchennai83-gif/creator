"""Daily Health Tip — three safe, everyday wellbeing tips in spoken Tamil.

Curated catalogue (no network, no model). Three tips are chosen each day from\ntwenty, and the daily line-up stays unique for 1,140 days. Tips are simple,\nwidely accepted lifestyle advice — food, sleep, movement, hygiene and mind —\nwritten so a general audience can act on them.
"""
from pathlib import Path

from ..daily_catalog import make_creator

PER_EDITION = 3

create_script = make_creator(Path(__file__).parent, PER_EDITION, 'tips')
