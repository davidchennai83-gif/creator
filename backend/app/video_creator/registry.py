"""One place that maps a video kind to the module that writes its daily script.

Adding a new daily show means: create a project package with a ``create_script``
and a ``catalog.json`` (see ``thirukkural``/``english``/``gk``), then add a row
here and to ``schedules.PROJECTS`` and the frontend ``KINDS``.
"""
import importlib

# kind -> (relative module, attribute, start label, finished label)
_CREATORS = {
    'history': ('scripts', 'create_script', 'Fetching historical events and source links',
                'Ten Tamil summaries ready. Review sources, then render.'),
    'indian-law': ('indian_law', 'create_script', 'Selecting five Indian Acts for this date',
                   'Five Acts ready, four Tamil lines each. Review explanations, then render.'),
    'make-money': ('make_money', 'create_script', 'Selecting five money-making ideas for this date',
                   'Five ideas ready, four Tamil lines each. Review the lines, then render.'),
    'news': ('news', 'create_script', 'Reading today’s Tamil news RSS feeds',
             'Ten Tamil news stories ready with source images and credits. Review, then render.'),
    'thirukkural': ('thirukkural', 'create_script', 'Choosing today’s Thirukkural couplets',
                    'Two Thirukkural couplets ready with the Tamil meaning. Review, then render.'),
    'english': ('english', 'create_script', 'Choosing today’s spoken-English phrases',
                'Three English phrases ready with Tamil meaning. Review, then render.'),
    'gk': ('gk', 'create_script', 'Choosing today’s amazing facts',
           'Three amazing facts ready. Review, then render.'),
    'health': ('health', 'create_script', 'Choosing today’s health tips',
               'Three health tips ready. Review, then render.'),
    'motivation': ('motivation', 'create_script', 'Choosing today’s life lessons',
                   'Three life lessons ready. Review, then render.'),
    'kids': ('kids', 'create_script', 'Choosing today’s kids learning',
             'Three kids learning items ready. Review, then render.'),
    'meesho': ('meesho', 'create_script', "Choosing today's Tamil Budget Finds product",
               'Budget product video ready. Review the price, benefits and caution, then render.'),
}

KINDS = tuple(_CREATORS)


def create(kind, day, progress):
    """Write the daily script for ``kind`` using its project module."""
    module, attribute, label, _ = _CREATORS[kind]
    progress(label)
    return getattr(importlib.import_module('.' + module, __package__), attribute)(day, progress)


def finished_message(kind):
    return _CREATORS[kind][3]
