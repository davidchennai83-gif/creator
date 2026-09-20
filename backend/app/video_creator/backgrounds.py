"""Original local topic illustrations; no stock API keys or network downloads."""
import base64
import re


# Rules are ordered from specific to broad. Images illustrate a topic, not an event photograph.
RULES = [
    ('education', r'education|educational|school|teacher|university'),
    ('environment', r'environment|forest|climate|wildlife|pollution'),
    ('technology', r'information technology|computer|internet|electronic|cyber|software'),
    ('health', r'mental health|disabilit|medical|hospital|medicine|health'),
    ('family', r'children|child|women|domestic|parents|senior citizen|family'),
    ('consumer', r'consumer|goods|trade|market|commerce'),
    ('housing', r'real estate|housing|building|residence'),
    ('space', r'space|lunar|moon|nasa|satellite|astronaut|rocket'),
    ('aviation', r'aircraft|aviation|flight|airplane|airport'),
    ('maritime', r'\b(?:ships?|shipping|shipwreck|warships?)\b|naval|navy|voyage|ocean|\bsail(?:s|ed|ing|or|ors)?\b'),
    ('conflict', r'\bwars?\b|warfare|battle|army|military|siege'),
    ('justice', r'act\b|law\b|court|right|constitution|independence|treaty'),
]

ART = {
    'education': '<path d="M180 160Q300 110 400 170Q500 110 620 160V460Q500 410 400 470Q300 410 180 460Z"/><path d="M400 170V470M220 210L350 230M220 275L350 295M450 230L580 210M450 295L580 275"/>',
    'environment': '<path d="M400 490V250M400 370Q200 360 210 140Q430 150 400 370ZM400 310Q610 300 590 100Q380 120 400 310Z"/><path d="M190 500Q400 450 610 500"/>',
    'technology': '<rect x="180" y="140" width="440" height="270" rx="20"/><path d="M340 410V470H270M460 410V470H530M290 220L240 275L290 330M510 220L560 275L510 330M435 200L365 350"/>',
    'health': '<path d="M400 460L220 290C110 160 290 80 400 210C510 80 690 160 580 290Z"/><path d="M400 240V370M335 305H465"/>',
    'family': '<circle cx="310" cy="190" r="55"/><circle cx="490" cy="190" r="55"/><circle cx="400" cy="320" r="42"/><path d="M210 440V350Q210 250 310 250M590 440V350Q590 250 490 250M325 490V435Q325 365 400 365Q475 365 475 435V490"/>',
    'consumer': '<path d="M200 160H245L290 365H560L610 220H260M315 270H560M335 315H535"/><circle cx="335" cy="430" r="28"/><circle cx="520" cy="430" r="28"/>',
    'housing': '<path d="M160 280L400 100L640 280M225 240V490H575V240M350 490V345H450V490"/><rect x="275" y="295" width="40" height="60"/><rect x="485" y="295" width="40" height="60"/>',
    'space': '<circle cx="400" cy="290" r="145"/><ellipse cx="400" cy="290" rx="290" ry="65" transform="rotate(-25 400 290)"/><circle cx="585" cy="100" r="20"/><path d="M200 95V145M175 120H225M580 440V490M555 465H605"/>',
    'aviation': '<path d="M400 100L440 270L650 370V420L435 360L425 460L480 500H320L375 460L365 360L150 420V370L360 270Z"/>',
    'maritime': '<path d="M170 390H630L550 490H250ZM400 390V100L580 340H400M365 150L210 340H365M170 530Q225 490 280 530T390 530T500 530T610 530"/>',
    'conflict': '<path d="M400 110L580 170V290Q580 420 400 500Q220 420 220 290V170ZM400 180V420M300 265H500"/>',
    'justice': '<path d="M400 110V460M300 490H500M210 210L590 160M245 205L170 350H320ZM555 165L480 310H630ZM170 350Q245 440 320 350M480 310Q555 400 630 310"/><circle cx="400" cy="110" r="22"/>',
    'history': '<path d="M180 210L400 90L620 210ZM190 470H610M160 510H640M235 250V435M345 250V435M455 250V435M565 250V435"/>',
}


def illustration(point, kind, index):
    text = f"{point.get('title', '')} {point.get('text', '')}".lower()
    topic = next((name for name, pattern in RULES if re.search(pattern, text)),
                 'justice' if kind == 'indian-law' else 'history')
    color = ['#5eead4', '#93c5fd', '#fcd34d', '#c4b5fd', '#fda4af'][index % 5]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
      <defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#071628"/><stop offset="1" stop-color="#254765"/></linearGradient>
      <radialGradient id="glow"><stop stop-color="{color}" stop-opacity=".3"/><stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient></defs>
      <rect width="1280" height="720" fill="url(#bg)"/>
      <circle cx="1030" cy="310" r="490" fill="url(#glow)"/>
      <g fill="none" stroke="{color}" stroke-opacity=".16" stroke-width="2"><circle cx="1040" cy="340" r="300"/><circle cx="1040" cy="340" r="340"/><path d="M0 650L1280 100M0 700L1280 150"/></g>
      <g transform="translate(450 20) scale(1.05)" fill="none" stroke="{color}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" opacity=".65">{ART[topic]}</g>
      <g fill="{color}" opacity=".45"><circle cx="80" cy="80" r="6"/><circle cx="1180" cy="620" r="8"/><circle cx="1150" cy="85" r="4"/></g>
    </svg>'''
    return {'topic': topic, 'image': 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()}
