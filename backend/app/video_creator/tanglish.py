"""Deterministic Tamil-script -> Tanglish (Latin) transliteration for on-screen display.

This is a phonetic, readable transliteration (not strict IAST) meant for viewers who prefer
reading Tamil in Latin letters, the way people type it casually. It is used for DISPLAY TEXT
only (video captions, review screen). Narration audio is always synthesised from the original
Tamil script — Tamil neural voices read Tanglish as English and would sound wrong.
"""
import re

_VOWELS = {
    '\u0b85': 'a', '\u0b86': 'aa', '\u0b87': 'i', '\u0b88': 'ii', '\u0b89': 'u', '\u0b8a': 'oo',
    '\u0b8e': 'e', '\u0b8f': 'ae', '\u0b90': 'ai', '\u0b92': 'o', '\u0b93': 'oa', '\u0b94': 'au',
}
_CONSONANTS = {
    '\u0b95': 'k', '\u0b99': 'ng', '\u0b9a': 'ch', '\u0b9c': 'j', '\u0b9e': 'nj', '\u0b9f': 't',
    '\u0ba3': 'n', '\u0ba4': 'th', '\u0ba8': 'n', '\u0ba9': 'n', '\u0baa': 'p', '\u0bae': 'm',
    '\u0baf': 'y', '\u0bb0': 'r', '\u0bb1': 'r', '\u0bb2': 'l', '\u0bb3': 'l', '\u0bb4': 'zh',
    '\u0bb5': 'v', '\u0bb7': 'sh', '\u0bb8': 's', '\u0bb9': 'h',
}
_VOWEL_SIGNS = {
    '\u0bbe': 'aa', '\u0bbf': 'i', '\u0bc0': 'ii', '\u0bc1': 'u', '\u0bc2': 'oo',
    '\u0bc6': 'e', '\u0bc7': 'ae', '\u0bc8': 'ai', '\u0bca': 'o', '\u0bcb': 'oa', '\u0bcc': 'au',
}
_PULLI = '\u0bcd'
_AYTHAM = '\u0b83'
_ANUSVARA = '\u0b82'


def transliterate(text: str) -> str:
    """Word-for-word Tamil -> Tanglish. Non-Tamil characters (spaces, digits, punctuation,
    already-Latin text) pass through unchanged, so mixed Tamil/English input stays readable."""
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in _CONSONANTS:
            base = _CONSONANTS[ch]
            nxt = text[i + 1] if i + 1 < n else ''
            if nxt == _PULLI:
                out.append(base)
                i += 2
            elif nxt in _VOWEL_SIGNS:
                out.append(base + _VOWEL_SIGNS[nxt])
                i += 2
            else:
                out.append(base + 'a')
                i += 1
        elif ch in _VOWELS:
            out.append(_VOWELS[ch])
            i += 1
        elif ch == _AYTHAM:
            out.append('h')
            i += 1
        elif ch == _ANUSVARA:
            out.append('m')
            i += 1
        else:
            out.append(ch)
            i += 1
    result = ''.join(out)
    # Capitalise the first letter of each sentence for readability.
    return re.sub(r'(^\s*[a-z]|[.!?]\s+[a-z])', lambda m: m.group(0).upper(), result)
