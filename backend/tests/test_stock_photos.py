import io
import json

import httpx
import pytest
from PIL import Image
from pydantic import SecretStr

from app.video_creator import stock_photos as stock


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setattr(stock.settings, 'STORAGE_PATH', str(tmp_path))
    monkeypatch.setattr(stock.settings, 'PEXELS_API_KEY', SecretStr('test-secret'))
    # Optional extras stay off unless a test asks for them, so a developer's
    # real backend/.env keys cannot change what these tests exercise.
    monkeypatch.setattr(stock.settings, 'PIXABAY_API_KEY', SecretStr(''))
    monkeypatch.setattr(stock.settings, 'UNSPLASH_ACCESS_KEY', SecretStr(''))
    monkeypatch.setattr(stock.settings, 'OPENVERSE_TOKEN', SecretStr(''))
    return tmp_path


def transport(monkeypatch, handler):
    client = httpx.Client
    monkeypatch.setattr(stock.httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))


def empty_commons():
    """Commons answers before any Pexels photo is needed."""
    return httpx.Response(200, json={'query': {'pages': {}}})


def empty_openverse():
    """Openverse is the keyless aggregator tried before Commons."""
    return httpx.Response(200, json={'results': []})


def test_photos_cached_credited_and_key_only_sent_to_api(configured, monkeypatch):
    output = io.BytesIO()
    Image.new('RGB', (1280, 720), '#305080').save(output, format='JPEG')
    requests = []
    # Freshness is covered elsewhere; this test is about caching and key safety.
    monkeypatch.setattr(stock.settings, 'STOCK_REUSE_DAYS', 0)

    def handle(request):
        requests.append(request)
        if request.url.host == 'api.pexels.com':
            assert request.headers['Authorization'] == 'test-secret'
            assert request.url.params['page'] in ('1', '2')
            return httpx.Response(200, json={'photos': [
                {'id': i, 'photographer': f'Artist {i}', 'url': f'https://www.pexels.com/photo/{i}/',
                 'alt': 'courthouse building',
                 'src': {'large2x': f'https://images.pexels.com/photos/{i}.jpg'}} for i in (1, 2)]})
        assert 'authorization' not in request.headers
        return httpx.Response(200, content=output.getvalue())

    transport(monkeypatch, handle)
    points = [{'title': 'Consumer Protection Act', 'photo_query': 'courthouse building'}] * 2
    result = stock.prepare_backgrounds(points, 'indian-law', configured, lambda _: None)
    assert all(b['provider'] == 'pexels' for b in result)
    credits = json.loads((configured / 'media-sources.json').read_text())
    assert [c['photo_id'] for c in credits] == [1, 2]
    assert len(requests) == 3
    assert 'test-secret' not in (configured / 'media-sources.json').read_text()
    stock.prepare_backgrounds(points, 'indian-law', configured, lambda _: None)
    assert len(requests) <= 4  # Search JSON and normalized images reused.


@pytest.mark.parametrize('status', [401, 403, 429, 500])
def test_api_failure_uses_illustration(configured, monkeypatch, status):
    def handle(request):
        if request.url.host == 'commons.wikimedia.org':
            return empty_commons()
        return httpx.Response(status, json={})

    transport(monkeypatch, handle)
    result = stock.prepare_backgrounds([{'title': 'Law Act'}], 'indian-law', configured, lambda _: None)
    assert result[0]['provider'] == 'illustration'
    credit = json.loads((configured / 'media-sources.json').read_text())[0]
    assert credit['fallback_reason']


def test_missing_pexels_key_still_uses_free_sources(configured, monkeypatch):
    """No Pexels key is not a dead end: Openverse and Commons need none."""
    monkeypatch.setattr(stock.settings, 'PEXELS_API_KEY', SecretStr(''))
    seen = []

    def handle(request):
        seen.append(request.url.host)
        assert request.url.host != 'api.pexels.com'
        return empty_openverse() if request.url.host == 'api.openverse.org' else empty_commons()

    transport(monkeypatch, handle)
    assert stock.prepare_backgrounds([{}], 'history', configured, lambda _: None)[0]['provider'] == 'illustration'
    assert seen == ['api.openverse.org', 'commons.wikimedia.org']


def test_sensitive_law_query_uses_places_not_portraits():
    assert stock.query_for({'title': 'Protection of Children from Sexual Offences Act'}, 'indian-law', 'family') == 'courthouse building'


def test_untrusted_cdn_host_is_not_downloaded(configured, monkeypatch):
    def handle(request):
        if request.url.host == 'commons.wikimedia.org':
            return empty_commons()
        if request.url.host == 'api.openverse.org':
            return empty_openverse()
        assert request.url.host == 'api.pexels.com'
        return httpx.Response(200, json={'photos': [{'id': 1, 'alt': 'courthouse building',
                                                     'src': {'large2x': 'http://127.0.0.1/private'}}]})
    transport(monkeypatch, handle)
    result = stock.prepare_backgrounds([{'title': 'Law Act', 'photo_query': 'courthouse building'}],
                                       'indian-law', configured, lambda _: None)
    assert result[0]['provider'] == 'illustration'


def vertical_jpeg():
    output = io.BytesIO()
    Image.new('RGB', (1080, 1920), '#204060').save(output, format='JPEG')
    return output.getvalue()


def test_pixabay_photo_is_used_when_pexels_has_nothing(configured, monkeypatch):
    from app.video_creator import fresh
    monkeypatch.setattr(stock.settings, 'PIXABAY_API_KEY', SecretStr('pb-key'))
    image = vertical_jpeg()

    def handle(request):
        if request.url.host == 'api.pexels.com':
            return httpx.Response(200, json={'photos': []})
        if request.url.host == 'pixabay.com':
            assert request.url.params['key'] == 'pb-key'
            return httpx.Response(200, json={'hits': [{
                'id': 51, 'user': 'PB Artist', 'tags': 'courthouse building',
                'pageURL': 'https://pixabay.com/photos/51/',
                'largeImageURL': 'https://cdn.pixabay.com/photo/51.jpg'}]})
        if request.url.host == 'cdn.pixabay.com':
            return httpx.Response(200, content=image)
        return empty_openverse()

    transport(monkeypatch, handle)
    points = [{'title': 'Consumer Protection Act', 'photo_query': 'courthouse building'}]
    result = stock.prepare_backgrounds(points, 'indian-law', configured, lambda _: None)
    assert result[0]['provider'] == 'pixabay'
    assert result[0]['source_name'] == 'Pixabay'
    credit = json.loads((configured / 'media-sources.json').read_text())[0]
    assert credit['photo_id'] == 'pixabay-51'
    assert 'Pixabay' in credit['license']
    assert 'pb-key' not in json.dumps(credit)
    assert 'pixabay-51' in fresh.recent('photo')


def test_unsplash_photo_is_used_when_pexels_and_pixabay_have_nothing(configured, monkeypatch):
    monkeypatch.setattr(stock.settings, 'UNSPLASH_ACCESS_KEY', SecretStr('u-key'))
    image = vertical_jpeg()

    def handle(request):
        if request.url.host == 'api.pexels.com':
            return httpx.Response(200, json={'photos': []})
        if request.url.host == 'api.unsplash.com':
            return httpx.Response(200, json={'results': [{
                'id': 'u1', 'alt_description': 'courthouse building',
                'user': {'name': 'US Artist'},
                'links': {'html': 'https://unsplash.com/photos/u1'},
                'urls': {'regular': 'https://images.unsplash.com/photo-u1.jpg'}}]})
        if request.url.host == 'images.unsplash.com':
            return httpx.Response(200, content=image)
        return empty_openverse()

    transport(monkeypatch, handle)
    result = stock.prepare_backgrounds(
        [{'title': 'Consumer Protection Act', 'photo_query': 'courthouse building'}],
        'indian-law', configured, lambda _: None)
    assert result[0]['provider'] == 'unsplash'
    credit = json.loads((configured / 'media-sources.json').read_text())[0]
    assert credit['photo_id'] == 'unsplash-u1'


def test_openverse_photo_is_used_without_any_key(configured, monkeypatch):
    import app.store
    monkeypatch.setattr(app.store, '_is_public_http_url',
                        lambda url: url.startswith('https://images.example.org/'))
    image = vertical_jpeg()

    def handle(request):
        if request.url.host == 'api.pexels.com':
            return httpx.Response(200, json={'photos': []})
        if request.url.host == 'api.openverse.org':
            return httpx.Response(200, json={'results': [{
                'id': 'ov1', 'license': 'cc0', 'license_version': '1.0',
                'creator': 'OV Artist', 'title': 'courthouse building',
                'url': 'https://images.example.org/courthouse.jpg',
                'foreign_landing_url': 'https://example.org/courthouse'}]})
        if request.url.host == 'images.example.org':
            return httpx.Response(200, content=image)
        raise AssertionError(f'unexpected host {request.url.host}')

    transport(monkeypatch, handle)
    result = stock.prepare_backgrounds(
        [{'title': 'Consumer Protection Act', 'photo_query': 'courthouse building'}],
        'indian-law', configured, lambda _: None)
    assert result[0]['provider'] == 'openverse'
    credit = json.loads((configured / 'media-sources.json').read_text())[0]
    assert credit['photo_id'] == 'openverse-ov1'
    assert credit['license'] == 'CC0 1.0'
