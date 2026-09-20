from app.config.settings import settings

def get_storage_provider():
    if settings.STORAGE_PROVIDER != "local":
        raise NotImplementedError("Storage adapter not implemented")
    from app.integrations.storage_provider import LocalStorageProvider
    return LocalStorageProvider(settings.STORAGE_PATH)

def get_ai_provider():
    if settings.AI_PROVIDER != "ollama":
        raise NotImplementedError("AI provider not implemented")
    from app.integrations.ollama_provider import OllamaProvider
    return OllamaProvider(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)

def get_payment_provider():
    raise NotImplementedError("Payment adapter not implemented")
