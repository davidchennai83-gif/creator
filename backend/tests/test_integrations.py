import pytest
import httpx
from app.integrations.storage_provider import LocalStorageProvider
from app.integrations.social_provider import YouTubeProvider, MetaProvider, TikTokProvider
from app.integrations.ollama_provider import OllamaProvider
from app.workers.base import celery_app, publish_post

def test_storage_round_trip_and_no_overwrite(tmp_path):
    storage=LocalStorageProvider(tmp_path)
    key=storage.store(b'first','same.txt')
    other=storage.store(b'second','same.txt')
    assert key!=other
    assert storage.retrieve(key)==b'first'
    assert storage.delete(key)
    assert not storage.exists(key)

@pytest.mark.parametrize('key',['../outside','..\\outside','C:/secret','/secret','.',''])
def test_storage_rejects_escape(tmp_path,key):
    with pytest.raises(ValueError):
        LocalStorageProvider(tmp_path).retrieve(key)

@pytest.mark.parametrize('provider',[YouTubeProvider,MetaProvider,TikTokProvider])
def test_social_cannot_fake_publish(provider):
    with pytest.raises(NotImplementedError):
        provider().publish({})

def test_worker_task_fails_instead_of_succeeding():
    with pytest.raises(NotImplementedError):
        publish_post.run('content','youtube','account',{})
    route=celery_app.amqp.router.route({},'app.workers.base.publish_post',args=(),kwargs={})
    assert route['queue'].name=='publishing_queue'
    assert celery_app.conf.task_acks_late
    assert celery_app.conf.accept_content==['json']

def test_ollama_http_failure_is_unhealthy(monkeypatch):
    def failure(*args,**kwargs):
        return httpx.Response(503,request=httpx.Request('GET','http://localhost/api/tags'))
    monkeypatch.setattr(httpx.Client,'get',failure)
    assert not OllamaProvider('http://localhost').health_check()
