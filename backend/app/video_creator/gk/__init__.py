"""Amazing Facts — three family-safe general-knowledge facts a day in Tamil.

Curated catalogue (no network, no model). Three facts are chosen each day from
twenty, and the daily line-up stays unique for 1,140 days, so the show never
repeats a combination for years. Facts are evergreen and checkable, written in
simple spoken Tamil for a general audience.
"""
from pathlib import Path

from ..daily_catalog import make_creator

PER_EDITION = 3

create_script = make_creator(Path(__file__).parent, PER_EDITION, 'facts')
