"""Daily Tamil cinema news: ten film stories from Tamil publisher RSS feeds.

This is the general-news bulletin (``news``) with a cinema edition: the same
RSS parsing, duplicate detection, attribution rules and nine-scene narration,
only a different feed mix and a stricter filter.

Sources, in the order they are read:

* Ananda Vikatan's cinema desk (``cinema.vikatan.com``) — a dedicated film feed
  with a lead photo per story, updated several times a day.
* Sathiyam TV's cinema category — a dedicated feed, quieter on slow news days.
* The six Tamil newsroom feeds from ``news.FEEDS``, each read through
  ``FILM_STORY`` so only film stories leave them. A general feed's description
  often mentions a film in passing ("the CM said this at a film event"), so the
  filter looks at the headline and section only, never the body copy.

Every scene keeps the publisher's name and link (on-screen credit and the video
description), so a viewer can always reach the original report.
"""
import re

from .. import news

PER_VIDEO = 10

# Headline/section filter for a general newsroom feed. Film-medium words only:
# a bare actor name is not enough ("Vijay" is also a chief minister's name).
FILM_STORY = re.compile(
    r'சினிமா|திரைப்பட|படப்பிடிப்பு|பட விழா|படத்தின்|திரையரங்க|டிரைலர்|டீசர்|'
    r'ஓடிடி|OTT|பாக்ஸ்.?ஆபிஸ்|பாக்ஸ்.?ஆபீஸ்|வசூல்|இயக்குநர|கதாநாயக|'
    r'வெப்.?சீரிஸ்|பிக்.?பாஸ்|இசையமைப்பாளர|நடிகர்|நடிகை|ரிலீஸ்|'
    r'சீரியல்|தயாரிப்பாளர|ஒளிப்பதிவாளர|டப்பிங்|ரீமேக்|முதல் நாள் காட்சி',
    re.IGNORECASE)

# Ananda Vikatan's cinema desk also republishes the day's trending story (a
# retirement, a party removal, a bank order), so its feed needs the wider
# show-business filter: film words plus the people and the TV shows the film
# audience follows.
SHOWBIZ = re.compile(
    FILM_STORY.pattern +
    r'|பிக்.?பாஸ்|Bigg.?boss|வைரல்|ரீல்ஸ்|Reels|இசை|பாடல்|நடிக|நடிப்ப|'
    r'ரஜினி|கமல்ஹாசன்|கமல்|அஜித்|விஜய்|சூர்யா|தனுஷ்|விக்ரம்|மம்மூட்டி|மோகன்லால்|'
    r'நயன்தாரா|த்ரிஷா|கீர்த்தி|சமந்தா|தமன்னா|தயாரிப்பு|வெளியீட்டு விழா',
    re.IGNORECASE)

CINEMA_FEEDS = [
    {'name': 'Ananda Vikatan Cinema', 'url': 'https://cinema.vikatan.com/feed/',
     'site': 'https://cinema.vikatan.com', 'kind': 'publisher', 'keep': SHOWBIZ},
    {'name': 'Sathiyam TV Cinema', 'url': 'https://sathiyam.tv/category/cinema/feed/',
     'site': 'https://sathiyam.tv', 'kind': 'publisher'},
]

# Dedicated feeds first (they are all film news), then the general newsrooms
# behind the headline filter.
FEEDS = CINEMA_FEEDS + [dict(feed, keep=FILM_STORY) for feed in news.FEEDS
                        if feed['name'] != 'Sathiyam TV']

# Illustration topics. A film story is the default; the few non-film topics a
# cinema feed carries (a wedding, a match, a court case) keep a matching picture.
TOPIC_RULES = [
    ('family', r'திருமணம்|நிச்சயதார்த்தம்|காதல்|குழந்தை|மகள்|மகன்|விவாகரத்து'),
    ('sports', r'கிரிக்கெட்|ஐபிஎல்|ஒருநாள்|போட்டி|அணி|கோப்பை|வீரர்'),
    ('justice', r'வழக்கு|நீதிமன்ற|காவல்|கைது|புகார்|தடை'),
    ('politics', r'அமைச்சர்|தேர்தல்|கட்சி|அரசியல்|முதல்வர்'),
]
TOPIC_DEFAULT = 'cinema'

# Two stories about the same film are one story; these groups keep a bulletin
# from being five release-date posts in a row.
GROUP_RULES = [
    ('release', r'வெளியீடு|ரிலீஸ்|திரையரங்க|காட்சி|முதல் நாள்|வருகிறது|வெளியாகிறது'),
    ('boxoffice', r'வசூல்|பாக்ஸ்.?ஆபிஸ்|பாக்ஸ்.?ஆபீஸ்|சாதனை|கோடி'),
    ('ott', r'ஓடிடி|OTT|நெட்ஃபிளிக்ஸ்|Netflix|ஆமேஸான்|Amazon|ஹாட்.?ஸ்டார்|Hotstar|ஜியோ'),
    ('tv', r'பிக்.?பாஸ்|சீரியல்|வெப்.?சீரிஸ்|தொலைக்காட்சி|நிகழ்ச்சி'),
    ('personal', r'திருமணம்|நிச்சய|காதல்|பிறந்தநாள்|விவாகரத்து|குடும்பம்|புகைப்பட'),
    ('sports', r'கிரிக்கெட்|ஐபிஎல்|போட்டி|அணி|கோப்பை'),
    ('politics', r'அமைச்சர்|தேர்தல்|கட்சி|அரசியல்|முதல்வர்'),
]

FALLBACK_QUERY = {
    'cinema': 'cinema theatre entrance', 'family': 'wedding hall decoration',
    'sports': 'cricket stadium', 'justice': 'courthouse law',
    'politics': 'assembly building india',
}

PROFILE = news.Profile(
    name='cinema',
    feeds=FEEDS,
    blocked=news.BLOCKED,
    groups=GROUP_RULES,
    topics=TOPIC_RULES,
    fallback_query=FALLBACK_QUERY,
    default_topic=TOPIC_DEFAULT,
    per_video=PER_VIDEO,
    max_age_hours=news.MAX_AGE_HOURS,
    # Two film feeds plus filtered general feeds: a tighter per-feed cap would
    # make ten scenes impossible on a day when only two sources are fresh.
    max_per_feed=4,
    max_per_topic=6,
    max_per_group=3,
    prefer=FILM_STORY,
    narrating='a short Tamil cinema news bulletin',
    fetching='Reading today’s Tamil cinema RSS feeds',
    selecting='Selecting {count} film stories from {total} recent items',
    summaries='Preparing attributed Tamil summaries from the publisher text',
    ready='{count} Tamil cinema stories ready with images and source credits',
)


def create_script(day, progress):
    return news.create_script(day, progress, PROFILE)
