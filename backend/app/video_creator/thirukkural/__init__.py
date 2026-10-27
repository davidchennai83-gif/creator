"""Daily Thirukkural — two couplets a day with the standard Tamil explanation.

The full Sangam text is bundled locally (`catalog.json`, built once from the
public-domain Project Madurai corpus), so this show is fully deterministic and
offline — no network and no language model at render time. Only the Virtue
(அறத்துப்பால்) and Wealth (பொருட்பால்) sections, kurals 1-1080, are used so the
channel stays family friendly. Two couplets a day give a 540-day cycle: a fresh
daily line-up for more than a year without repeating.
"""
from pathlib import Path

from ..daily_catalog import make_creator

PER_EDITION = 2

create_script = make_creator(Path(__file__).parent, PER_EDITION, 'couplets')
