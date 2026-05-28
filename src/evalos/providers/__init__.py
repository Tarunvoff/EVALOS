from evalos.providers.base import BaseProvider
from evalos.providers.resilient import ResilientProvider

try:
	from evalos.providers.litellm import LiteLLMProvider
except ModuleNotFoundError:
	LiteLLMProvider = None  # type: ignore[assignment]

try:
	from evalos.providers.ollama import OllamaProvider
except ModuleNotFoundError:
	OllamaProvider = None  # type: ignore[assignment]

__all__ = ["BaseProvider", "ResilientProvider"]
if LiteLLMProvider is not None:
	__all__.append("LiteLLMProvider")
if OllamaProvider is not None:
	__all__.append("OllamaProvider")
