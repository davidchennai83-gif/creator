import io

import httpx
import pytest
from PIL import Image
from pydantic import SecretStr

from app.config.settings import settings
from app.video_creator import openverse, pixabay, stock_image, unsplash


@pytest.fixture(autouse=True)
def storage(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'STORAGE_PATH', str(tmp_path))
    monkeypatch.setattr(settings, 'PIXABAY_API_KEY', SecretStr(''))
    monkeypatch.setattr(settings, 'UNSPLASH_ACCESS_KEY', SecretStr(''))
    monkeypatch.setattr(settings, 'OPENVERSE_TOKEN', SecretStr(''))
    return tmp_path


def jpeg(width=1080, height=1920, colour='#204060'):
    output = io.BytesIO()
    Image.new('RGB', (width, height), colour).save(output, format='JPEG')
    return output.getvalue()


def pixabay_video(video_id=7, duration=20, tags='shared meal bread', width=1080, height=1920):
    return {
        'id': video_id, 'duration': duration, 'user': 'PB Filmer', 'tags': tags,
        'pageURL': f'https://pixabay.com/videos/id-{video_id}/',
        'videos': {'large': {'url': f'https://cdn.pixabay.com/video/{video_id}.mp4',
                             'width': width, 'height': height}},
    }


def test_pixabay_video_is_normalised_and_relevance_checked():
    hits = [pixabay_video(1, tags='cat playing'), pixabay_video(2)]
    video, file = pixabay.pick_video(hits, 10.0, set(), 'shared meal')
    assert video['id'] == 'pixabay-2'
    assert video['provider'] == 'pixabay' and video['source_name'] == 'Pixabay'
    assert file['link'] == 'https://cdn.pixabay.com/video/2.mp4'
    assert video['video_files'][0]['link'] == file['link']


def test_pixabay_video_skips_used_landscape_and_short_clips():
    hits = [pixabay_video(1), pixabay_video(2, width=1920, height=1080),
            pixabay_video(3, duration=3), pixabay_video(4)]
    assert pixabay.pick_video(hits, 10.0, {'pixabay-1'}, 'shared meal')[0]['id'] == 'pixabay-4'


def test_pixabay_photo_needs_a_matching_tag():
    hits = [{'id': 5, 'tags': 'cat', 'pageURL': 'https://pixabay.com/photos/5/'},
            {'id': 6, 'tags': 'courthouse building',
             'pageURL': 'https://pixabay.com/photos/6/'}]
    assert pixabay.pick_photo(hits, set(), 'courthouse building')['id'] == 6
    assert pixabay.pick_photo(hits, {'pixabay-6'}, 'courthouse building') is None


def test_pixabay_search_is_skipped_without_a_key():
    def fail(request):
        raise AssertionError('no request without a key')

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        assert pixabay.videos(client, 'shared meal') == []
        assert pixabay.photos(client, 'shared meal') == []


def test_pixabay_search_sends_its_key_and_caches(monkeypatch):
    monkeypatch.setattr(settings, 'PIXABAY_API_KEY', SecretStr('pb-key'))
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == 'pixabay.com'
        assert request.url.path == '/api/videos/'
        assert request.url.params['key'] == 'pb-key'
        assert request.url.params['orientation'] == 'vertical'
        return httpx.Response(200, json={'hits': [pixabay_video()]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert len(pixabay.videos(client, 'shared meal')) == 1
        assert len(pixabay.videos(client, 'shared meal')) == 1
    assert len(calls) == 1


def test_unsplash_sends_client_id_and_caches(monkeypatch):
    monkeypatch.setattr(settings, 'UNSPLASH_ACCESS_KEY', SecretStr('u-key'))
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == 'api.unsplash.com'
        assert request.headers['Authorization'] == 'Client-ID u-key'
        return httpx.Response(200, json={'results': [
            {'id': 'abc', 'alt_description': 'courthouse building at dusk',
             'user': {'name': 'Unsplash Artist'},
             'links': {'html': 'https://unsplash.com/photos/abc'},
             'urls': {'regular': 'https://images.unsplash.com/photo-abc.jpg'}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        results = unsplash.search(client, 'courthouse building')
        unsplash.search(client, 'courthouse building')
    assert len(calls) == 1
    photo = unsplash.pick_photo(results, set(), 'courthouse building')
    assert unsplash.photo_credit(photo)['id'] == 'unsplash-abc'
    assert unsplash.photo_link(photo).startswith('https://images.unsplash.com/')


def test_openverse_works_without_a_token_and_drops_sharealike(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == 'api.openverse.org'
        assert 'authorization' not in request.headers
        assert request.url.params['license_type'] == 'commercial,modification'
        return httpx.Response(200, json={'results': [
            {'id': 'a', 'license': 'by', 'creator': 'A', 'url': 'https://example.org/a.jpg'},
            {'id': 'b', 'license': 'by-sa', 'creator': 'B', 'url': 'https://example.org/b.jpg'},
            {'id': 'c', 'license': 'cc0', 'creator': 'C', 'url': 'https://example.org/c.jpg'},
        ]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        images = openverse.search(client, 'shared meal')
    assert [item['id'] for item in images] == ['a', 'c']
    assert len(calls) == 1


def test_openverse_token_only_adds_authorisation(monkeypatch):
    monkeypatch.setattr(settings, 'OPENVERSE_TOKEN', SecretStr('ov-token'))

    def handler(request):
        assert request.headers['Authorization'] == 'Bearer ov-token'
        return httpx.Response(200, json={'results': []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert openverse.search(client, 'shared meal') == []


def test_image_download_refuses_other_hosts_and_oversized_files():
    def fail(request):
        raise AssertionError('untrusted host must never be fetched')

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(ValueError):
            stock_image.download(client, 'http://cdn.pixabay.com/photo.jpg',
                                 ('cdn.pixabay.com',))
        with pytest.raises(ValueError):
            stock_image.download(client, 'https://127.0.0.1/photo.jpg',
                                 ('cdn.pixabay.com',))

    def big(request):
        return httpx.Response(200, content=b'\0' * 8_000)

    with httpx.Client(transport=httpx.MockTransport(big)) as client:
        with pytest.raises(ValueError):
            stock_image.download(client, 'https://cdn.pixabay.com/photo.jpg',
                                 ('cdn.pixabay.com',), limit_mb=0.001)


def test_portrait_frame_is_exactly_the_output_size():
    with Image.open(io.BytesIO(stock_image.portrait(jpeg(1920, 1080)))) as frame:
        assert frame.size == (1080, 1920)
