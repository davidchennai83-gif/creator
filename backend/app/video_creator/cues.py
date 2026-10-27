"""edge-tts synthesis that also captures word-level timings for subtitles.

The Microsoft service emits WordBoundary messages (offset/duration in units of
100 ns) when the Communicate request asks for them, so the same synthesis that
saves the voice clip also provides the exact moment every Tamil word is spoken.
"""
import asyncio
import re
import time


_EMOJI = re.compile('[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]')


def normalise_for_speech(text):
    """Make display text comfortable for the Tamil neural voice.

    The catalogue lines include prices, star glyphs, bullets and short fragments.
    Reading those raw produces choppy or unclear narration, so expand the symbols
    into spoken Tamil, keep decimal/comma separators, and give every sentence a
    clear full stop. This changes only the audio text; on-screen text is untouched.
    """
    text = str(text or '')
    # Expand the review star before the emoji sweep, otherwise ★ is stripped.
    text = re.sub(r'[★⭐]', ' நட்சத்திரம் ', text)
    text = _EMOJI.sub(' ', text).replace('\u00a0', ' ')
    text = re.sub(r'₹\s*([\d,]+(?:\.\d+)?)', r'\1 ரூபாய்', text)
    text = re.sub(r'\bRs\.?\s*([\d,]+(?:\.\d+)?)', r'\1 ரூபாய்', text, flags=re.I)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 சதவீதம்', text)
    text = re.sub(r'\bMRP\b', 'எம்.ஆர்.பி.', text, flags=re.I)
    text = re.sub(r'\b(\d+)\s*L\b', r'\1 லிட்டர்', text, flags=re.I)
    text = re.sub(r'\b(\d+)\s*ml\b', r'\1 மில்லி லிட்டர்', text, flags=re.I)
    text = re.sub(r'\b(\d+)\s*kg\b', r'\1 கிலோ', text, flags=re.I)
    text = re.sub(r'\b(\d+)\s*g\b', r'\1 கிராம்', text, flags=re.I)
    text = re.sub(r'[•·|]', ', ', text)
    text = re.sub(r'[→➡]', ', ', text)
    text = re.sub(r'[–—]', ', ', text)
    text = text.replace('&', ' மற்றும் ')
    text = text.replace('+', ' ப்ளஸ் ')
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([,.!?;:])', r'\1', text)
    # A space after punctuation keeps the voice from running sentences together.
    # Do not split "4.3" or "1,349" because the next character is a digit.
    text = re.sub(r'([,.!?;:])(?=[^\s\d])', r'\1 ', text)
    text = text.strip()
    if text and text[-1] not in '.?!':
        text += '.'
    return text


def speech_with_cues(text, destination, voice, rate='+15%', pitch='+0Hz', volume='+0%',
                     attempts=3, retry_wait=4.0):
    """Save the spoken audio to destination and return word cues.

    Returns a list of {'text', 'start', 'end'} in seconds, ordered as spoken.
    Transient edge-tts failures (network hiccups, throttling, a stale
    Sec-MS-GEC handshake) are retried a few times with a growing pause before
    the error is raised, so one bad connection never kills a whole render.
    """
    import edge_tts
    text = normalise_for_speech(text)
    last_error = None
    for attempt in range(1, max(1, attempts) + 1):
        cues = []

        async def run():
            communicator = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                                volume=volume, boundary='WordBoundary')
            with open(destination, 'wb') as stream:
                async for chunk in communicator.stream():
                    if chunk['type'] == 'audio':
                        stream.write(chunk['data'])
                    elif chunk['type'] == 'WordBoundary':
                        start = chunk['offset'] / 1e7
                        cues.append({'text': chunk['text'],
                                     'start': round(start, 3),
                                     'end': round(start + chunk['duration'] / 1e7, 3)})

        try:
            asyncio.run(_run_with_timeout(run, 120))
            return cues
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < attempts:
                time.sleep(retry_wait * attempt)
    raise last_error


async def _run_with_timeout(run, timeout):
    return await asyncio.wait_for(run(), timeout=timeout)


def build_phrases(cues, max_words=6, max_duration=2.2, min_gap=0.06):
    """Group word cues into readable on-screen phrases.

    Consecutive words stick together while the silence between them stays under
    min_gap seconds, the phrase stays short enough to read at a glance and the
    whole phrase fits max_duration. Word-level cueing is therefore respected, but
    subtitles look like natural phrases instead of flickering single words.
    """
    phrases = []
    current = []
    for cue in cues:
        word = (cue.get('text') or '').strip()
        if not word:
            continue
        if current and (cue['start'] - current[-1]['end'] > min_gap
                        or len(current) >= max_words
                        or cue['end'] - current[0]['start'] > max_duration):
            phrases.append(current)
            current = []
        current.append(cue)
    if current:
        phrases.append(current)
    return [{'text': ' '.join(w['text'] for w in group),
             'start': group[0]['start'], 'end': group[-1]['end']} for group in phrases]


def write_srt(phrases, path):
    """Write an SRT file from a flat list of absolute-time phrase cues."""
    lines = []
    for index, phrase in enumerate(phrases, 1):
        start, end = phrase['start'], phrase['end']
        lines.append(str(index))
        lines.append(f"{_srt_time(start)} --> {_srt_time(end)}")
        lines.append(phrase['text'])
        lines.append('')
    path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')


def _srt_time(seconds):
    seconds = max(0.0, seconds)
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, msecs = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{msecs:03}"