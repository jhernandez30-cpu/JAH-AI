"""Provider-aware LLM orchestrator for JAH AI.

The orchestrator reads environment variables at call time so local tests and
Railway deployments report the real current provider state.
"""
from __future__ import annotations

import os
import time
from typing import Any

try:
    from openai import OpenAI
    _HAS_OPENAI = True
except Exception:
    OpenAI = None  # type: ignore[assignment]
    _HAS_OPENAI = False

try:
    import httpx
    _HAS_HTTPX = True
except Exception:
    httpx = None  # type: ignore[assignment]
    _HAS_HTTPX = False

try:
    from .anthropic_service import AnthropicService
    _HAS_ANTHROPIC_SERVICE = True
except Exception:
    AnthropicService = None  # type: ignore[assignment]
    _HAS_ANTHROPIC_SERVICE = False


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class LLMOrchestrator:
    def provider(self) -> str:
        configured = _env("MODEL_PROVIDER").lower()
        if configured:
            return configured
        if _env("OPENAI_API_KEY") and _HAS_OPENAI:
            return "openai"
        if _env("GEMINI_API_KEY") and _HAS_HTTPX:
            return "gemini"
        if _env("OLLAMA_BASE_URL") and _HAS_HTTPX:
            return "ollama"
        if _env("ANTHROPIC_API_KEY") and _HAS_ANTHROPIC_SERVICE:
            return "anthropic"
        return "none"

    def model_name(self) -> str:
        return _env("MODEL_NAME") or _env("TUTOR_IA_LLM_MODEL") or {
            "openai": "gpt-4o-mini",
            "gemini": "gemini-2.5-flash",
            "ollama": "llama3.2:1b",
            "anthropic": _env("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
        }.get(self.provider(), "")

    def is_configured(self) -> bool:
        provider = self.provider()
        if provider == "openai":
            return bool(_env("OPENAI_API_KEY") and _HAS_OPENAI)
        if provider == "gemini":
            return bool(_env("GEMINI_API_KEY") and _HAS_HTTPX)
        if provider == "ollama":
            return bool(_env("OLLAMA_BASE_URL") and _HAS_HTTPX)
        if provider == "anthropic":
            return bool(_env("ANTHROPIC_API_KEY") and _HAS_ANTHROPIC_SERVICE)
        return False

    def status(self) -> dict[str, Any]:
        provider = self.provider()
        return {
            "provider": provider,
            "configured": self.is_configured(),
            "model": self.model_name(),
            "available_sdks": {
                "openai": _HAS_OPENAI,
                "httpx": _HAS_HTTPX,
                "anthropic_service": _HAS_ANTHROPIC_SERVICE,
            },
            "error": None if self.is_configured() else "MODEL_PROVIDER_NOT_CONFIGURED",
        }

    def generate(self, message: str, context: str | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        provider = self.provider()
        if provider == "openai":
            return self._call_openai(message, context, options)
        if provider == "gemini":
            return self._call_gemini(message, context, options)
        if provider == "ollama":
            return self._call_ollama(message, context, options)
        if provider == "anthropic":
            return self._call_anthropic(message, context, options)
        return {
            "source": "none",
            "success": False,
            "answer": "No hay proveedor de modelo configurado en backend.",
            "error": "MODEL_PROVIDER_NOT_CONFIGURED",
            "latency_ms": 0,
            "metadata": {},
        }

    def _prompt_messages(self, message: str, context: str | None) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": "Eres JAH AI, asistente de programacion. Responde en espanol, con causa, solucion y validacion.",
            },
            {
                "role": "user",
                "content": f"Contexto:\n{context or ''}\n\nSolicitud:\n{message}",
            },
        ]

    def _call_openai(self, message: str, context: str | None, options: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        if not (_env("OPENAI_API_KEY") and _HAS_OPENAI):
            return {
                "source": "openai",
                "success": False,
                "answer": "",
                "error": "OPENAI_NOT_CONFIGURED",
                "latency_ms": 0,
            }
        try:
            client = OpenAI(api_key=_env("OPENAI_API_KEY"))  # type: ignore[operator]
            model = str(options.get("model") or self.model_name() or "gpt-4o-mini")
            response = client.chat.completions.create(
                model=model,
                messages=self._prompt_messages(message, context),
                max_tokens=int(options.get("max_tokens") or 900),
                temperature=float(options.get("temperature") or 0.2),
            )
            text = response.choices[0].message.content or ""
            return {
                "source": "openai",
                "success": bool(text),
                "answer": text,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "metadata": {"model": model},
            }
        except Exception as exc:
            return {
                "source": "openai",
                "success": False,
                "answer": "",
                "error": str(exc),
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }

    def _call_gemini(self, message: str, context: str | None, options: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        if not (_env("GEMINI_API_KEY") and _HAS_HTTPX):
            return {"source": "gemini", "success": False, "answer": "", "error": "GEMINI_NOT_CONFIGURED", "latency_ms": 0}
        model = str(options.get("model") or self.model_name() or "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [
                {"parts": [{"text": f"Contexto:\n{context or ''}\n\nSolicitud:\n{message}"}]}
            ],
            "generationConfig": {
                "temperature": float(options.get("temperature") or 0.2),
                "maxOutputTokens": int(options.get("max_tokens") or 900),
            },
        }
        try:
            response = httpx.post(  # type: ignore[union-attr]
                url,
                params={"key": _env("GEMINI_API_KEY")},
                json=payload,
                timeout=float(options.get("timeout") or 45),
            )
            response.raise_for_status()
            data = response.json()
            text = ""
            for candidate in data.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    text += part.get("text", "")
            return {
                "source": "gemini",
                "success": bool(text),
                "answer": text,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "metadata": {"model": model},
            }
        except Exception as exc:
            return {"source": "gemini", "success": False, "answer": "", "error": str(exc), "latency_ms": int((time.perf_counter() - started) * 1000)}

    def _call_ollama(self, message: str, context: str | None, options: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        base_url = _env("OLLAMA_BASE_URL").rstrip("/")
        if not (base_url and _HAS_HTTPX):
            return {"source": "ollama", "success": False, "answer": "", "error": "OLLAMA_NOT_CONFIGURED", "latency_ms": 0}
        model = str(options.get("model") or self.model_name() or "llama3.2:1b")
        try:
            response = httpx.post(  # type: ignore[union-attr]
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": f"Contexto:\n{context or ''}\n\nSolicitud:\n{message}",
                    "stream": False,
                    "options": {"temperature": float(options.get("temperature") or 0.2)},
                },
                timeout=float(options.get("timeout") or 60),
            )
            response.raise_for_status()
            data = response.json()
            text = data.get("response") or ""
            return {
                "source": "ollama",
                "success": bool(text),
                "answer": text,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "metadata": {"model": model},
            }
        except Exception as exc:
            return {"source": "ollama", "success": False, "answer": "", "error": str(exc), "latency_ms": int((time.perf_counter() - started) * 1000)}

    def _call_anthropic(self, message: str, context: str | None, options: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        if not (_env("ANTHROPIC_API_KEY") and _HAS_ANTHROPIC_SERVICE):
            return {"source": "anthropic", "success": False, "answer": "", "error": "ANTHROPIC_NOT_CONFIGURED", "latency_ms": 0}
        try:
            service = AnthropicService()  # type: ignore[operator]
            result = service.generate_answer(message, context=context, options=options)
            if isinstance(result, dict):
                return {"source": "anthropic", "success": bool(result.get("answer") or result.get("success")), **result}
            return {
                "source": "anthropic",
                "success": bool(result),
                "answer": str(result),
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
        except Exception as exc:
            return {"source": "anthropic", "success": False, "answer": "", "error": str(exc), "latency_ms": int((time.perf_counter() - started) * 1000)}


_orchestrator = LLMOrchestrator()


def get_orchestrator() -> LLMOrchestrator:
    return _orchestrator
