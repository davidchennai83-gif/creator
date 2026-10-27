"""Daily Life Lesson — three short, positive Tamil lessons a day.

Curated catalogue (no network, no model). Three lessons are chosen each day from\ntwenty, and the daily line-up stays unique for 1,140 days. Themes are evergreen\nand family friendly — effort, discipline, resilience, values, money habits,\nlearning and health — never politics, religion or anything divisive.
"""
from pathlib import Path

from ..daily_catalog import make_creator

PER_EDITION = 3

create_script = make_creator(Path(__file__).parent, PER_EDITION, 'lessons')
