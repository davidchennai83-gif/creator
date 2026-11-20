"""The spoken register every video script follows.

A scene names its subject in the first line and only then explains it, and it
talks to the viewer the way a person would. Two habits are banned outright:

* stock openers — the same "ஒரு நிமிஷம் யோசிச்சு பாருங்க," / "இன்றைய ...:" frame
  opening every scene, which made every edition sound alike;
* a line that ends in "பாருங்க" — the sentence-final tic.

Model prompts (``scripts.py``, ``meesho/ai_copy.py``) state the same rule in
words; this module is what curated data and generated scripts are checked
against.
"""
import re

# Prefixes that mark a stock opener rather than real content.
FILLERS = (
    'ஒரு நிமிஷம் யோசிச்சு பாருங்க',
    'இதுக்கு பின்னாடி இருக்குற',
    'இங்கதான் ஒரு',
    'இன்றைய உடல்நல குறிப்பு:',
    'இன்றைய அறிய தகவல்:',
    'இன்றைய கற்றல்:',
    'இன்றைய ஆங்கில வாக்கியம்:',
    'இன்றைய வாழ்க்கை பாடம்:',
)

TIC = 'பாருங்க'
_TRAILING_TIC = re.compile(TIC + r'\s*[.!?]?$')


def breaches(line):
    """Why ``line`` breaks the house style, or ``None`` when it is fine."""
    text = ' '.join(str(line or '').split())
    for filler in FILLERS:
        if text.startswith(filler):
            return f'stock opener: {filler}'
    if _TRAILING_TIC.search(text):
        return f'line ends with {TIC}'
    return None


def check(lines, where='script'):
    """Raise ``ValueError`` on the first line that breaks the house style."""
    for line in lines:
        reason = breaches(line)
        if reason:
            raise ValueError(f'{where}: {reason}: {line}')
    return lines
