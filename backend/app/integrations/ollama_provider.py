import httpx
from app.integrations.ai_provider import AIProvider, AIResponse

class OllamaProvider(AIProvider):
    def __init__(self, base_url: str, model: str = "llama3"):
        self.base_url, self.model = base_url.rstrip("/"), model

    def generate(self, prompt: str, **kwargs) -> AIResponse:
        with httpx.Client(base_url=self.base_url, timeout=120) as client:
            response = client.post("/api/generate", json={"model": self.model, "prompt": prompt, "stream": False, "options": {"num_predict": 2048}})
            response.raise_for_status()
            data = response.json()
        if not isinstance(data.get("response"), str) or not data["response"].strip():
            raise ValueError("Ollama returned empty output")
        return AIResponse(content=data["response"], tokens_used=data.get("eval_count", 0), model=self.model, provider="ollama", cost=0)

    def health_check(self):
        try:
            with httpx.Client(base_url=self.base_url, timeout=3) as client:
                client.get("/api/tags").raise_for_status()
            return True
        except httpx.HTTPError:
            return False
