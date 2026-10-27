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
    # How to Make Money icons
    'coin': '<circle cx="400" cy="290" r="175"/><circle cx="400" cy="290" r="125"/><path d="M330 215H470M330 265H470M345 215Q455 215 455 265Q455 320 345 320L465 405"/>',
    'play': '<rect x="170" y="150" width="460" height="300" rx="50"/><path d="M350 215V385L505 300ZM300 500H500"/>',
    'mic': '<path d="M340 140Q340 90 400 90Q460 90 460 140V270Q460 330 400 330Q340 330 340 270ZM270 240Q270 400 400 400Q530 400 530 240M400 400V480M320 495H480"/>',
    'camera': '<path d="M170 220H270L300 170H500L530 220H630V450H170Z"/><circle cx="400" cy="335" r="78"/><path d="M570 260H600"/>',
    'chart': '<path d="M180 110V480H640M250 480V370M340 480V300M430 480V340M520 480V220M230 310L340 230L430 270L600 130M545 130H600V185"/>',
    'food': '<circle cx="420" cy="320" r="150"/><circle cx="420" cy="320" r="95"/><path d="M170 120V240Q170 300 215 300Q260 300 260 240V120M215 120V500"/>',
    'craft': '<path d="M300 340L470 100M500 340L330 100"/><circle cx="285" cy="400" r="62"/><circle cx="515" cy="400" r="62"/>',
    'delivery': '<circle cx="250" cy="410" r="70"/><circle cx="560" cy="410" r="70"/><path d="M250 410L320 260H470L560 410M470 260L430 160H520M320 260L290 200H210M520 120H640V210H520Z"/>',
    'wrench': '<rect x="250" y="90" width="250" height="420" rx="40"/><path d="M340 140H410M340 470H410M540 150L420 290M560 130Q610 130 610 180L560 200L540 150Z"/>',
    'phone': '<rect x="260" y="90" width="280" height="430" rx="42"/><path d="M355 145H445M375 480H425M310 220H490M310 290H460M310 360H420"/>',
    'warning': '<path d="M400 100L640 500H160ZM400 250V385M400 440V446"/>',
    'wallet': '<path d="M170 210H590Q640 210 640 260V440Q640 490 590 490H220Q170 490 170 440ZM170 210L470 110H530V210"/><circle cx="565" cy="350" r="28"/>',
    'pen': '<path d="M200 490L235 375L520 90L610 180L325 465ZM470 140L560 230M200 490L325 465M350 510H610"/>',
    'laptop': '<path d="M230 140H570V380H230ZM150 435H650L610 380H190ZM300 210H500M300 260H460M300 310H400"/>',
    'news': '<path d="M160 170H600V480H160ZM600 230H690Q720 230 720 260V450Q720 480 690 480H600M220 240H540M220 300H540M220 360H470M220 420H540"/>',
    # Catalogue kinds (Thirukkural / Spoken English / Amazing Facts)
    'book': '<path d="M170 150Q300 105 400 165Q500 105 630 150V470Q500 415 400 475Q300 415 170 470Z"/><path d="M400 165V475M210 205L350 228M210 270L350 293M210 335L350 358M450 228L590 205M450 293L590 270M450 358L590 335"/>',
    'chat': '<path d="M170 170H620Q660 170 660 210V390Q660 430 620 430H360L250 500V430H210Q170 430 170 390ZM250 250H580M250 310H520M250 370H450"/>',
    'globe': '<circle cx="400" cy="300" r="200"/><ellipse cx="400" cy="300" rx="200" ry="78"/><ellipse cx="400" cy="300" rx="78" ry="200"/><path d="M200 300H600M225 210Q400 260 575 210M225 390Q400 340 575 390"/>',
}


def illustration(point, kind, index):
    from .theme import theme_for
    text = f"{point.get('title', '')} {point.get('text', '')}".lower()
    if point.get('topic') in ART:
        topic = point['topic']  # curated kinds name their own icon
    else:
        topic = next((name for name, pattern in RULES if re.search(pattern, text)),
                     {'indian-law': 'justice', 'make-money': 'coin',
                      'meesho': 'consumer'}.get(kind, 'history'))
    color = theme_for(kind)['accent']
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">
      <defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#071628"/><stop offset="1" stop-color="#254765"/></linearGradient>
      <radialGradient id="glow"><stop stop-color="{color}" stop-opacity=".34"/><stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient></defs>
      <rect width="1080" height="1920" fill="url(#bg)"/>
      <circle cx="540" cy="820" r="880" fill="url(#glow)"/>
      <g fill="none" stroke="{color}" stroke-opacity=".16" stroke-width="2"><circle cx="540" cy="820" r="560"/><circle cx="540" cy="820" r="640"/><path d="M0 1780L1080 480M0 1880L1080 580"/></g>
      <g transform="translate(140 640) scale(1.0)" fill="none" stroke="{color}" stroke-width="15" stroke-linecap="round" stroke-linejoin="round" opacity=".7">{ART[topic]}</g>
      <g fill="{color}" opacity=".45"><circle cx="90" cy="140" r="9"/><circle cx="990" cy="1760" r="12"/><circle cx="990" cy="160" r="6"/><circle cx="80" cy="1720" r="7"/></g>
    </svg>'''
    return {'topic': topic, 'image': 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()}
