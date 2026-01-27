from abc import ABC, abstractmethod
from typing import Optional, List, Any
from dotenv import load_dotenv
import os

load_dotenv()


class LLMProvider(ABC):
    
    @abstractmethod
    def get_chat_model(self, **kwargs) -> Any:
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        pass


class OpenAIProvider(LLMProvider):
    
    def __init__(self, model: str = None, temperature: float = 0.0):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.temperature = temperature
        self._api_key = os.getenv("OPENAI_API_KEY")
    
    @property
    def name(self) -> str:
        return "OpenAI"
    
    @property
    def is_available(self) -> bool:
        return bool(self._api_key)
    
    def get_chat_model(self, **kwargs) -> Any:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            api_key=self._api_key,
            **kwargs
        )


class GeminiProvider(LLMProvider):
    
    def __init__(self, model: str = None, temperature: float = 0.0):
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.temperature = temperature
        self._api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    
    @property
    def name(self) -> str:
        return "Google Gemini"
    
    @property
    def is_available(self) -> bool:
        return bool(self._api_key)
    
    def get_chat_model(self, **kwargs) -> Any:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=self.model,
            temperature=self.temperature,
            google_api_key=self._api_key,
            **kwargs
        )


class ClaudeProvider(LLMProvider):
    
    def __init__(self, model: str = None, temperature: float = 0.0):
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.temperature = temperature
        self._api_key = os.getenv("ANTHROPIC_API_KEY")
    
    @property
    def name(self) -> str:
        return "Anthropic Claude"
    
    @property
    def is_available(self) -> bool:
        return bool(self._api_key)
    
    def get_chat_model(self, **kwargs) -> Any:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=self.model,
            temperature=self.temperature,
            api_key=self._api_key,
            **kwargs
        )


class OllamaProvider(LLMProvider):
    
    def __init__(
        self, 
        model: str = None, 
        temperature: float = 0.0,
        base_url: Optional[str] = None
    ):
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.temperature = temperature
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    @property
    def name(self) -> str:
        return "Ollama"
    
    @property
    def is_available(self) -> bool:
        import requests
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_chat_model(self, **kwargs) -> Any:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=self.model,
            temperature=self.temperature,
            base_url=self.base_url,
            **kwargs
        )


class LLMProviderFactory:
    
    _providers = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "google": GeminiProvider,
        "claude": ClaudeProvider,
        "anthropic": ClaudeProvider,
        "ollama": OllamaProvider,
    }
    
    @classmethod
    def get_provider(cls, provider_name: str, **kwargs) -> LLMProvider:
        provider_name = provider_name.lower()
        if provider_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Unknown provider: {provider_name}. Available: {available}")
        
        return cls._providers[provider_name](**kwargs)
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        available = []
        for name, provider_cls in cls._providers.items():
            try:
                provider = provider_cls()
                if provider.is_available:
                    available.append(name)
            except Exception:
                pass
        return list(set(available))
    
    @classmethod
    def get_default_provider(cls) -> LLMProvider:
        priority = ["openai", "gemini", "claude", "ollama"]
        
        for provider_name in priority:
            try:
                provider = cls._providers[provider_name]()
                if provider.is_available:
                    print(f"✅ Using {provider.name} as LLM provider")
                    return provider
            except Exception:
                continue
        
        raise RuntimeError(
            "No LLM provider available! Please set one of:\n"
            "  - OPENAI_API_KEY for OpenAI\n"
            "  - GOOGLE_API_KEY or GEMINI_API_KEY for Gemini\n"
            "  - ANTHROPIC_API_KEY for Claude\n"
            "  - OLLAMA_BASE_URL for Ollama (or run Ollama locally)"
        )


def get_llm(provider_name: Optional[str] = None, **kwargs) -> Any:
    if provider_name:
        provider = LLMProviderFactory.get_provider(provider_name, **kwargs)
    else:
        provider = LLMProviderFactory.get_default_provider()
    return provider.get_chat_model()


def get_available_providers() -> List[str]:
    return LLMProviderFactory.get_available_providers()
