from __future__ import annotations

import os
import time
from typing import Any


DEFAULT_MODEL = "claude-3-5-sonnet-latest"

try:
    from anthropic import Anthropic

    _HAS_ANTHROPIC = True
except Exception:
    Anthropic = None
    _HAS_ANTHROPIC = False


class AnthropicService:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
        self.timeout = timeout or int(os.getenv("BRAIN_TIMEOUT_SECONDS", "120"))
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.api_key and _HAS_ANTHROPIC)

    def generate_answer(
        self,
        message: str,
        context: str | None = None,
        system_prompt: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        if not self.api_key:
            return self._unavailable(started, "ANTHROPIC_API_KEY no configurado.")
        if not _HAS_ANTHROPIC:
            return self._unavailable(started, "Paquete anthropic no instalado.")

        options = options or {}
        max_tokens = int(options.get("max_tokens") or (4000 if options.get("deep_thinking") else 3000))
        temperature = float(options.get("temperature") or 0.2)
        system_prompt = system_prompt or self._default_system_prompt(options)
        user_content = self._build_user_content(message, context)

        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            answer = self._extract_text(response)
            return {
                "source": "anthropic",
                "success": bool(answer),
                "answer": answer,
                "content": answer,
                "confidence": 0.9 if answer else 0.0,
                "latency_ms": self._latency(started),
                "error": None if answer else "Anthropic no devolvio texto.",
                "metadata": {"model": self.model},
            }
        except Exception as exc:
            return self._unavailable(started, f"Anthropic no disponible: {exc}")

    def synthesize_response(
        self,
        message: str,
        context: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.generate_answer(
            message,
            context=context,
            system_prompt=self._default_system_prompt(options or {}),
            options=options,
        )

    def _get_client(self):
        if self._client is None:
            self._client = Anthropic(api_key=self.api_key, timeout=self.timeout)
        return self._client

    def _default_system_prompt(self, options: dict[str, Any]) -> str:
        if options.get("deep_thinking"):
            detail = "Da una respuesta completa, con pasos claros, criterios y validacion."
        else:
            detail = "Da una respuesta breve, directa y accionable."
        return (
            "Eres un asistente senior de programacion en espanol. "
            "Tu prioridad es crear, analizar, explicar, corregir y mejorar soluciones tecnicas de software. "
            "Dominas Python, C#, SQL, bases de datos, APIs, backend, frontend, ciberseguridad defensiva, Streamlit, Flask, FastAPI, Power BI y n8n. "
            "Las solicitudes normales de programacion, bases de datos, ciberseguridad defensiva, aprendizaje y proyectos academicos son permitidas. "
            "Si el usuario pide codigo, SQL o una estructura, entrega una solucion completa y ejecutable. "
            "Si una fuente del Cerebro Unificado no devuelve informacion util, no inventes un rechazo; usa conocimiento general tecnico y responde con una solucion profesional. "
            "Usa el contexto local como material interno, no como texto para copiar. "
            "Entrega una sola respuesta final profesional, sin listar respuestas por modulo. "
            "Si falta informacion, dilo en una frase y da el siguiente paso minimo. "
            f"{detail}"
        )

    @staticmethod
    def _build_user_content(message: str, context: str | None) -> str:
        context = str(context or "").strip()
        if not context:
            context = "No hay contexto local disponible."
        return f"Contexto disponible:\n{context}\n\nPregunta del usuario:\n{message}\n\nRespuesta final:"

    @staticmethod
    def _extract_text(response: Any) -> str:
        parts: list[str] = []
        for block in getattr(response, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
        return "\n".join(parts).strip()

    def _unavailable(self, started: float, error: str) -> dict[str, Any]:
        return {
            "source": "anthropic",
            "success": False,
            "answer": "",
            "content": "",
            "confidence": 0.0,
            "latency_ms": self._latency(started),
            "error": error,
            "metadata": {"model": self.model, "configured": bool(self.api_key)},
        }

    @staticmethod
    def _latency(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
