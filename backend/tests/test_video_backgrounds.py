import base64
from xml.etree import ElementTree

import pytest
from app.video_creator.backgrounds import illustration


@pytest.mark.parametrize('title,kind,topic', [
    ('Right to Education Act, 2009', 'indian-law', 'education'),
    ('Environment Protection Act', 'indian-law', 'environment'),
    ('Information Technology Act', 'indian-law', 'technology'),
    ('Consumer Protection Act', 'indian-law', 'consumer'),
    ('Apollo moon landing', 'history', 'space'),
    ('A naval voyage', 'history', 'maritime'),
    ('Unknown event', 'history', 'history'),
    ('Legal Services Authorities Act', 'indian-law', 'justice'),
])
def test_background_matches_topic_and_is_valid_local_svg(title, kind, topic):
    result = illustration({'title': title, 'text': ''}, kind, 0)
    assert result['topic'] == topic
    svg = ElementTree.fromstring(base64.b64decode(result['image'].split(',', 1)[1]))
    assert svg.attrib['viewBox'] == '0 0 1280 720'
    assert not list(svg.iter('{http://www.w3.org/2000/svg}image'))


def test_untrusted_source_text_is_not_embedded_in_svg():
    result = illustration({'text': '<script>alert(1)</script>'}, 'history', 0)
    assert b'<script' not in base64.b64decode(result['image'].split(',', 1)[1])
