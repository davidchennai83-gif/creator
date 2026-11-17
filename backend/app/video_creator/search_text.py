"""Cheap keyword checks that keep a stock search honest.

Pexels ranks loosely: a manuscript query can return a festival dance, and the
same page comes back every day. These helpers pull meaningful words out of a
query and compare them with the asset's own label (Pexels slug, photo alt text,
Commons file name), so an unrelated result is rejected instead of used.
"""
STOP = {'the', 'a', 'an', 'of', 'in', 'on', 'with', 'and', 'for', 'to', 'at'}

# Words that describe the channel or the medium, not the shot. "ancient tamil
# palm leaf manuscript" once matched a Tamil festival clip through "tamil".
GENERIC = {
    'india', 'indian', 'tamil', 'tamilnadu', 'ancient', 'traditional', 'old', 'historic',
    'historical', 'people', 'person', 'man', 'woman', 'video', 'footage', 'clip', 'stock',
    'background', 'beautiful', 'nature', 'life', 'daily', 'modern', 'scene', 'shot',
}

# Visual adjectives and adverbs that a model likes to add. They say how a shot
# looks, not what it shows, so on their own they cannot make a result relevant.
WEAK = {
    'glowing', 'glow', 'softly', 'soft', 'gently', 'gentle', 'shiny', 'vibrant',
    'cinematic', 'moody', 'peaceful', 'calm', 'dramatic', 'abstract', 'closeup', 'macro',
    'slowly', 'slow', 'beautiful', 'blurred', 'blurry',
}

# Slugs that are not camera footage at all: the channel promises real video.
NOT_FOOTAGE = ('animation', 'animated', '3d', 'motion-graphics', 'motion-graphic',
               'template', 'slideshow', 'screensaver', 'graphic-design', 'render')


def tokens(text):
    """Meaningful lowercase words from a query, slug, alt text or file name."""
    clean = str(text or '').replace('-', ' ').replace('_', ' ').replace('/', ' ')
    words = ''.join(ch if ch.isalnum() else ' ' for ch in clean.lower()).split()
    return {word for word in words if len(word) > 2 and word not in STOP and word not in GENERIC}


def _hit(left, right):
    if left == right:
        return True
    return len(left) >= 4 and len(right) >= 4 and left[:4] == right[:4]


def overlap(query, label):
    """How many different meaningful query words the label names (0 = unrelated)."""
    wanted = tokens(query) - WEAK
    have = tokens(label)
    return sum(1 for left in wanted if any(_hit(left, right) for right in have))


def matches(query, label):
    """True when the asset's own label shares a meaningful word with the query.

    A match on a visual adjective alone ("glowing") is not enough: something in
    the label has to name what the shot actually shows. English inflections
    differ between a model's phrase and a Pexels slug ("shared" / "sharing"), so
    longer words also match on a four-letter prefix.
    """
    wanted = tokens(query)
    if not wanted:
        return True
    if overlap(query, label):
        return True
    if not (wanted - WEAK):
        return bool((wanted & WEAK) & tokens(label))
    return False


def footage(slug):
    """False for slugs that are motion graphics rather than filmed footage."""
    text = str(slug or '').lower()
    return not any(word in text for word in NOT_FOOTAGE)
