"""Per-show visual identity for the video renderer.

One place that gives every daily show a consistent accent colour, an on-screen
badge, a short hook line (first seconds) and an end call-to-action. Keeping the
identity in one table makes the channel look coherent across kinds and lets the
accent flow into the illustration, the scene card, the captions and the progress
bar without touching each project.
"""


def _rgb(hex_colour):
    value = hex_colour.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _bgr(hex_colour):
    r, g, b = _rgb(hex_colour)
    return (b, g, r)


def _ass(hex_colour):
    """ASS/SSA colour is &HBBGGRR (byte-reversed RGB)."""
    r, g, b = _rgb(hex_colour)
    return f'{b:02X}{g:02X}{r:02X}'


THEMES = {
    'history':    {'accent': '#5eead4', 'badge': 'DAY OF HISTORY',           'hook': 'இன்றைய 10 நிகழ்வுகள்'},
    'indian-law': {'accent': '#fcd34d', 'badge': 'INDIAN LAW · DAILY 5 ACTS', 'hook': 'இன்றைய 5 சட்டங்கள்'},
    'make-money': {'accent': '#86efac', 'badge': 'MAKE MONEY · 5 IDEAS',      'hook': 'இன்றைய 5 வழிகள்'},
    'thirukkural': {'accent': '#fda4af', 'badge': 'THIRUKKURAL · DAILY',      'hook': 'இன்றைய திருக்குறள்'},
    'english':    {'accent': '#93c5fd', 'badge': 'SPOKEN ENGLISH · 3 PHRASES', 'hook': 'இன்றைய 3 Phrases'},
    'gk':         {'accent': '#c4b5fd', 'badge': 'AMAZING FACTS · 3',        'hook': 'இன்றைய 3 உண்மைகள்'},
    'kids':       {'accent': '#fdba74', 'badge': 'KIDS LEARNING',            'hook': 'இன்றைய Kids பாடம்'},
    'health':     {'accent': '#6ee7b7', 'badge': 'HEALTH TIPS · 3',          'hook': 'இன்றைய 3 Health Tips'},
    'motivation': {'accent': '#fde68a', 'badge': 'LIFE LESSONS · 3',         'hook': 'இன்றைய 3 பாடங்கள்'},
    'news':       {'accent': '#7dd3fc', 'badge': 'TAMIL NEWS · 10',          'hook': 'இன்றைய 10 முக்கிய செய்திகள்',
                   'cta': 'முழு விவரம் source link-ல · Like · Share · Subscribe'},
    'meesho':     {'accent': '#fb7185', 'badge': 'TAMIL BUDGET FINDS',       'hook': 'இன்றைய Budget Pick',
                   'cta': 'Link-ல click பண்ணி வாங்குங்க · Like · Share'},
}

DEFAULT = {'accent': '#5eead4', 'badge': 'DAILY VIDEO', 'hook': 'இன்றைய பதிவு'}

CTA = 'தினமும் புது வீடியோ · Like · Share · Subscribe'


def theme_for(kind):
    """Return the resolved theme for a kind (never raises).

    The hook and end-call-to-action come from the growth agent's daily playbook
    so the ask varies day to day; if that module is unavailable the static copy
    below is used instead, so a render can never fail because of it.
    """
    base = THEMES.get(kind, DEFAULT)
    accent = base['accent']
    hook, cta = base['hook'], base.get('cta', CTA)
    if kind != 'meesho':
        try:
            from app.growth import playbook
            variant = playbook.variant_for(kind)
            hook = variant.get('hook') or hook
            cta = variant.get('cta') or cta
        except Exception:
            pass
    return {
        'accent': accent,
        'accent_bgr': _bgr(accent),
        'accent_ass': _ass(accent),
        'badge': base['badge'],
        'hook': hook,
        'cta': cta,
    }
