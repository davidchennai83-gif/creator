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
    return tmp_path


def transport(monkeypatch, handler):
    client = httpx.Client
    monkeypatch.setattr(stock.httpx, 'Client', lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))


def test_photos_cached_credited_and_key_only_sent_to_api(configured, monkeypatch):
    output = io.BytesIO()
    Image.new('RGB', (1280, 720), '#305080').save(output, format='JPEG')
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.host == 'api.pexels.com':
            assert request.headers['Authorization'] == 'test-secret'
            return httpx.Response(200, json={'photos': [
                {'id': i, 'photographer': f'Artist {i}', 'url': f'https://www.pexels.com/photo/{i}/',
                 'src': {'large2x': f'https://images.pexels.com/photos/{i}.jpg'}} for i in (1, 2)]})
        assert 'authorization' not in request.headers
        return httpx.Response(200, content=output.getvalue())

    transport(monkeypatch, handle)
    points = [{'title': 'Consumer Protection Act'}] * 2
    result = stock.prepare_backgrounds(points, 'indian-law', configured, lambda _: None)
    assert all(b['provider'] == 'pexels' for b in result)
    credits = json.loads((configured / 'media-sources.json').read_text())
    assert [c['photo_id'] for c in credits] == [1, 2]
    assert len(requests) == 3
    assert 'test-secret' not in (configured / 'media-sources.json').read_text()
    stock.prepare_backgrounds(points, 'indian-law', configured, lambda _: None)
    assert len(requests) == 3  # Search and normalized images reused.


@pytest.mark.parametrize('status', [401, 403, 429, 500])
def test_api_failure_uses_illustration(configured, monkeypatch, status):
    transport(monkeypatch, lambda request: httpx.Response(status, json={}))
    result = stock.prepare_backgrounds([{'title': 'Law Act'}], 'indian-law', configured, lambda _: None)
    assert result[0]['provider'] == 'illustration'
    credit = json.loads((configured / 'media-sources.json').read_text())[0]
    assert credit['fallback_reason']


def test_missing_key_never_requests_network(configured, monkeypatch):
    monkeypatch.setattr(stock.settings, 'PEXELS_API_KEY', SecretStr(''))
    def fail(request):
        raise AssertionError('Unexpected network call')
    transport(monkeypatch, fail)
    assert stock.prepare_backgrounds([{}], 'history', configured, lambda _: None)[0]['provider'] == 'illustration'


def test_sensitive_law_query_uses_places_not_portraits():
    assert stock.query_for({'title': 'Protection of Children from Sexual Offences Act'}, 'indian-law', 'family') == 'courthouse building'


def test_untrusted_cdn_host_is_not_downloaded(configured, monkeypatch):
    def handle(request):
        assert request.url.host == 'api.pexels.com'
        return httpx.Response(200, json={'photos': [{'id': 1, 'src': {'large2x': 'http://127.0.0.1/private'}}]})
    transport(monkeypatch, handle)
    result = stock.prepare_backgrounds([{}], 'history', configured, lambda _: None)
    assert result[0]['provider'] == 'illustration'
