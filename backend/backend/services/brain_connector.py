from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from typing import Any

from services.anthropic_service import AnthropicService
from services.bridge_api_client import BridgeAPIClient
from services.conversation_context import resolve_user_request
from services.technical_intent_router import detect_technical_intent
from services.local_brain_service import LocalBrainService
from services.safety_filter import classify_safety, is_safe_programming_request, safe_refusal_only_if_really_needed
from services.technical_generators import generate_technical_answer, should_use_technical_generator
from services.technical_templates import fallback_programming_answer


LOGGER = logging.getLogger(__name__)

DEFAULT_OPTIONS = {
    "local_first": True,
    "fast_mode": True,
    "bridge_api": True,
    "anthropic": True,
    "deep_thinking": False,
    "mode": "local-first",
}
SOURCE_PRIORITY = {
    "local_brain": 100,
    "bridge_api": 80,
    "anthropic": 70,
    "fallback": 10,
}


class BrainConnector:
    def __init__(
        self,
        *,
        brain_root: str | Path | None = None,
        bridge_api_url: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logger or LOGGER
        self.local_brain = LocalBrainService(brain_root)
        self.bridge_api = BridgeAPIClient(base_url=bridge_api_url)
        self.anthropic = AnthropicService()
        self.max_context_chars = int(os.getenv("MAX_CONTEXT_CHARS", "12000"))
        self.brain_timeout = int(os.getenv("BRAIN_TIMEOUT_SECONDS", "120"))
        self.bridge_timeout = int(os.getenv("BRIDGE_TIMEOUT_SECONDS", "120"))
        self._answer_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._cache_ttl = int(os.getenv("BRAIN_CACHE_SECONDS", "45"))

    def answer(self, message: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        original_message = str(message or "").strip()
        message = original_message
        resolved_options = self._resolve_options(options)
        history = self._history_from_options(resolved_options)
        errors: list[str] = []

        if not message:
            return {
                "success": False,
                "answer": "Escribe una pregunta para que pueda ayudarte.",
                "sources_used": ["fallback"],
                "mode": "local-first",
                "errors": ["Mensaje vacio."],
            }

        intent = detect_technical_intent(message, history)
        resolved_message = intent.get("resolved_request") or resolve_user_request(message, history)
        safety = classify_safety(resolved_message, intent, history)
        resolved_options = self._technical_generation_options(resolved_options, intent)

        self.logger.info(
            "BrainConnector diagnostic original=%r resolved=%r intent=%s safety=%s",
            original_message,
            resolved_message,
            intent,
            safety,
        )

        if intent.get("needs_clarification"):
            answer = "\u00bfTe refieres a la base de datos, una pagina, un CRUD u otra estructura?"
            return self._final_response(
                started,
                answer,
                resolved_options,
                intent,
                safety,
                [self._source_result("conversation_resolver", True, answer, 0.8, 0, None)],
                [],
                original_message,
                resolved_message,
            )

        if not safety.get("allowed", True):
            answer = safe_refusal_only_if_really_needed(str(safety.get("reason") or "harmful_or_illegal_request"))
            return self._final_response(
                started,
                answer,
                resolved_options,
                intent,
                safety,
                [self._source_result("safety_filter", True, answer, 0.9, 0, None)],
                [],
                original_message,
                resolved_message,
            )

        if should_use_technical_generator(intent):
            answer = generate_technical_answer(resolved_message, intent)
            source_name = self._technical_source_name(intent)
            response = self._final_response(
                started,
                answer,
                resolved_options,
                intent,
                safety,
                [self._source_result(source_name, True, answer, 0.95, 0, None)],
                [],
                original_message,
                resolved_message,
            )
            self._answer_cache[self._cache_key(resolved_message, resolved_options)] = (time.monotonic(), response)
            return response

        cache_key = self._cache_key(resolved_message, resolved_options)
        cached = self._answer_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < self._cache_ttl:
            result = dict(cached[1])
            result["cached"] = True
            return result

        results = self.collect_context(resolved_message, resolved_options)
        context = self.merge_contexts(results)
        for item in results:
            if item.get("error"):
                errors.append(str(item["error"]))

        try:
            answer = self.synthesize_answer(
                resolved_message,
                context,
                {**resolved_options, "_results": results},
            )
        except Exception as exc:
            self.logger.warning("BrainConnector synthesis failed: %s", exc)
            errors.append(str(exc))
            answer = self.fallback_answer(resolved_message, intent)

        if self._looks_like_false_safety_refusal(answer) and is_safe_programming_request(resolved_message, intent):
            self.logger.info("BrainConnector replaced false safety refusal with programming fallback.")
            answer = fallback_programming_answer(resolved_message, intent)
            results.append(self._source_result("fallback_programming_answer", True, answer, 0.85, 0, None))

        if not answer:
            answer = self.fallback_answer(resolved_message, intent)
            results.append(self._source_result("fallback", True, answer, 0.2, 0, None))

        sources_used = [item["source"] for item in results if item.get("success")]
        if not sources_used:
            sources_used = ["fallback"]
            results.append(self._source_result("fallback", True, answer, 0.2, 0, None))

        response = self._final_response(
            started,
            answer,
            resolved_options,
            intent,
            safety,
            results,
            errors,
            original_message,
            resolved_message,
            sources_used=sources_used,
        )
        self._answer_cache[cache_key] = (time.monotonic(), response)
        return response

    def collect_context(self, message: str, options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        options = self._resolve_options(options)
        results: list[dict[str, Any]] = []

        if options.get("local_first", True):
            results.append(
                self._run_with_timeout(
                    lambda: self.query_local_brain(message),
                    source="local_brain",
                    timeout=self.brain_timeout,
                )
            )

        if options.get("bridge_api", True):
            local_context = [item for item in results if item.get("source") == "local_brain"]
            results.append(
                self._run_with_timeout(
                    lambda: self.query_bridge_api(message, local_context, options),
                    source="bridge_api",
                    timeout=self.bridge_timeout,
                )
            )

        if not options.get("local_first", True):
            results.append(
                self._run_with_timeout(
                    lambda: self.query_local_brain(message),
                    source="local_brain",
                    timeout=self.brain_timeout,
                )
            )

        return results

    def query_local_brain(self, message: str) -> dict[str, Any]:
        try:
            return self.local_brain.search_local_context(message)
        except Exception as exc:
            return self._source_result("local_brain", False, "", 0.0, 0, str(exc))

    def query_bridge_api(
        self,
        message: str,
        context: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context_text = self.merge_contexts(context or [])
        try:
            result = self.bridge_api.ask(message, context=context_text, options=options or {})
            return self._normalize_source_result("bridge_api", result)
        except Exception as exc:
            return self._source_result("bridge_api", False, "", 0.0, 0, str(exc))

    def query_anthropic(
        self,
        message: str,
        context: list[dict[str, Any]] | str | None = None,
    ) -> dict[str, Any]:
        context_text = context if isinstance(context, str) else self.merge_contexts(context or [])
        try:
            result = self.anthropic.synthesize_response(message, context_text)
            return self._normalize_source_result("anthropic", result)
        except Exception as exc:
            return self._source_result("anthropic", False, "", 0.0, 0, str(exc))

    def merge_contexts(self, results: list[dict[str, Any]]) -> str:
        ordered = sorted(
            results or [],
            key=lambda item: (SOURCE_PRIORITY.get(str(item.get("source")), 0), float(item.get("confidence") or 0)),
            reverse=True,
        )
        seen: set[str] = set()
        chunks: list[str] = []
        used_chars = 0
        for item in ordered:
            if not item.get("success"):
                continue
            content = str(item.get("content") or item.get("answer") or "").strip()
            if not content:
                continue
            key = self._dedupe_key(content)
            if key in seen:
                continue
            seen.add(key)
            source = str(item.get("source") or "fuente")
            block = f"[{source}]\n{content}"
            remaining = self.max_context_chars - used_chars
            if remaining <= 0:
                break
            if len(block) > remaining:
                block = block[: max(0, remaining - 3)].rstrip() + "..."
            chunks.append(block)
            used_chars += len(block)
        return "\n\n".join(chunks)

    def synthesize_answer(self, message: str, context: str, options: dict[str, Any] | None = None) -> str:
        options = self._resolve_options(options)
        results = options.get("_results", [])
        bridge_result = self._first_success(results, "bridge_api")
        bridge_answer = str((bridge_result or {}).get("answer") or (bridge_result or {}).get("content") or "").strip()

        use_anthropic = bool(options.get("anthropic", True) and self.anthropic.is_configured())
        bridge_already_claude = self._bridge_mentions_anthropic(bridge_result)
        should_call_anthropic = use_anthropic and not bridge_already_claude and (
            options.get("deep_thinking") or not bridge_answer or options.get("anthropic_synthesis")
        )

        if should_call_anthropic:
            anthropic_result = self.anthropic.synthesize_response(message, context, options=options)
            normalized = self._normalize_source_result("anthropic", anthropic_result)
            if isinstance(results, list):
                results.append(normalized)
            if normalized.get("success") and normalized.get("content"):
                return str(normalized["content"]).strip()

        if bridge_answer:
            return bridge_answer

        if context:
            return self._local_context_answer(context)

        return self.fallback_answer(message)

    def fallback_answer(self, message: str, intent: dict[str, Any] | None = None) -> str:
        intent = intent or detect_technical_intent(message)
        if is_safe_programming_request(message, intent):
            return fallback_programming_answer(message, intent)
        return (
            "Puedo ayudarte, pero ahora no tengo una fuente de sintesis avanzada disponible. "
            f"Para esta consulta de tipo {intent.get('intent', 'general_question')}, verifica que la Bridge API/Ollama este activa o configura Anthropic; "
            "mientras tanto puedo trabajar con el contexto local y darte el siguiente paso si pegas el codigo, error o requisito clave."
        )

    def health_check(self, force_bridge: bool = True) -> dict[str, Any]:
        local = self.local_brain.health_check()
        bridge_ok = self.bridge_api.health_check(force=force_bridge)
        anthropic_ok = self.anthropic.is_configured()
        return {
            "success": True,
            "mode": "local-first",
            "local_brain": {
                "connected": bool(local.get("success")),
                "root": str(self.local_brain.get_root()),
                "sources_found": local.get("metadata", {}).get("sources_found", 0),
                "error": local.get("error"),
            },
            "bridge_api": {
                "connected": bridge_ok,
                "url": self.bridge_api.base_url,
            },
            "anthropic": {
                "configured": anthropic_ok,
                "model": self.anthropic.model,
            },
        }

    def get_status(self) -> dict[str, Any]:
        return self.health_check(force_bridge=False)

    def _resolve_options(self, options: dict[str, Any] | None) -> dict[str, Any]:
        resolved = {**DEFAULT_OPTIONS, **(options or {})}
        if resolved.get("deep_thinking"):
            resolved["fast_mode"] = False
        resolved["mode"] = "local-first"
        return resolved

    @staticmethod
    def _history_from_options(options: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("history", "chat_history", "memory", "messages"):
            value = options.get(key)
            if isinstance(value, list):
                return value
        return []

    @staticmethod
    def _technical_generation_options(options: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
        if not (intent.get("requires_code") or intent.get("requires_schema")):
            return options
        adjusted = dict(options)
        adjusted.setdefault("max_tokens", 3500)
        adjusted.setdefault("max_output_tokens", 3500)
        adjusted.setdefault("max_new_tokens", 3500)
        adjusted.setdefault("num_predict", 4096)
        adjusted.setdefault("temperature", 0.25)
        adjusted.setdefault("top_p", 0.9)
        if adjusted.get("response_profile") == "web_fast":
            adjusted["response_profile"] = "balanced"
        return adjusted

    @staticmethod
    def _technical_source_name(intent: dict[str, Any]) -> str:
        intent_name = str(intent.get("resolved_intent") or intent.get("intent") or "")
        if intent_name in {"database_design", "sql", "sql_generation", "er_model"}:
            return "database_generator"
        if intent_name in {"code_debugging", "code_review", "code_explanation"}:
            return "code_interpreter_router"
        return "technical_generators"

    def _run_with_timeout(self, fn, *, source: str, timeout: int) -> dict[str, Any]:
        started = time.perf_counter()
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fn)
        try:
            result = future.result(timeout=timeout)
            return self._normalize_source_result(source, result)
        except TimeoutError:
            return self._source_result(
                source,
                False,
                "",
                0.0,
                int((time.perf_counter() - started) * 1000),
                f"{source} excedio {timeout}s.",
            )
        except Exception as exc:
            return self._source_result(
                source,
                False,
                "",
                0.0,
                int((time.perf_counter() - started) * 1000),
                str(exc),
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _normalize_source_result(self, source: str, result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            return self._source_result(source, bool(result), str(result or ""), 0.4, 0, None)

        content = str(result.get("content") or result.get("answer") or "").strip()
        success = bool(result.get("success", bool(content)))
        return {
            "source": result.get("source") or source,
            "success": success,
            "content": content,
            "answer": str(result.get("answer") or content),
            "confidence": float(result.get("confidence", 0.6 if success else 0.0) or 0.0),
            "latency_ms": int(result.get("latency_ms", 0) or 0),
            "error": result.get("error"),
            "metadata": result.get("metadata", {}) or {},
            "raw": result.get("raw"),
            "sources": result.get("sources", []),
        }

    @staticmethod
    def _source_result(
        source: str,
        success: bool,
        content: str,
        confidence: float,
        latency_ms: int,
        error: str | None,
    ) -> dict[str, Any]:
        return {
            "source": source,
            "success": success,
            "content": content,
            "answer": content,
            "confidence": confidence,
            "latency_ms": latency_ms,
            "error": error,
            "metadata": {},
            "sources": [],
        }

    @staticmethod
    def _first_success(results: list[dict[str, Any]], source: str) -> dict[str, Any] | None:
        for item in results or []:
            if item.get("source") == source and item.get("success"):
                return item
        return None

    @staticmethod
    def _bridge_mentions_anthropic(result: dict[str, Any] | None) -> bool:
        if not result:
            return False
        text = " ".join(
            str(part)
            for part in [
                result.get("model"),
                result.get("mode"),
                result.get("metadata"),
                result.get("raw"),
            ]
        ).lower()
        return "anthropic" in text or "claude" in text

    def _local_context_answer(self, context: str) -> str:
        snippet = re.sub(r"\s+", " ", context).strip()
        if len(snippet) > 700:
            snippet = snippet[:697].rstrip() + "..."
        return (
            "Encontre contexto relevante en tu cerebro local. "
            "La Bridge API o Anthropic no devolvieron una sintesis final, asi que te dejo la base util para continuar: "
            f"{snippet}"
        )

    def _final_response(
        self,
        started: float,
        answer: str,
        options: dict[str, Any],
        intent: dict[str, Any],
        safety: dict[str, Any],
        results: list[dict[str, Any]],
        errors: list[str],
        original_message: str,
        resolved_message: str,
        *,
        sources_used: list[str] | None = None,
    ) -> dict[str, Any]:
        used = sources_used or [item["source"] for item in results if item.get("success")]
        if not used:
            used = ["fallback"]
        return {
            "success": True,
            "answer": answer,
            "sources_used": self._dedupe_list(used),
            "mode": options.get("mode", "local-first"),
            "intent": intent,
            "safety": safety,
            "original_message": original_message,
            "resolved_message": resolved_message,
            "errors": errors,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "source_results": results,
            "sources": self._docs_from_results(results),
            "cached": False,
        }

    @staticmethod
    def _looks_like_false_safety_refusal(answer: str) -> bool:
        text = str(answer or "").lower()
        if "no puedo" not in text:
            return False
        return bool(
            re.search(
                r"(menores|ilegal|ilegales|inapropiad|no puedo crear ni compartir|contenido que promueva)",
                text,
            )
        )

    @staticmethod
    def _docs_from_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for item in results or []:
            source = item.get("source")
            if source == "local_brain":
                for file_info in item.get("metadata", {}).get("files", [])[:8]:
                    docs.append(
                        {
                            "text": "",
                            "metadata": {
                                "source": file_info.get("relative_path", "local_brain"),
                                "title": file_info.get("relative_path", "local_brain"),
                                "type": "local_brain",
                            },
                        }
                    )
            for raw_source in item.get("sources", []) or []:
                if isinstance(raw_source, dict):
                    metadata = raw_source.get("metadata", raw_source)
                    docs.append(
                        {
                            "text": raw_source.get("snippet", raw_source.get("text", "")),
                            "metadata": {
                                "source": metadata.get("source", source),
                                "title": metadata.get("title", metadata.get("source", source)),
                                "type": metadata.get("type", source),
                            },
                        }
                    )
        return docs

    def _cache_key(self, message: str, options: dict[str, Any]) -> str:
        safe_options = {
            key: options.get(key)
            for key in [
                "fast_mode",
                "deep_thinking",
                "bridge_api",
                "anthropic",
                "selected_sources",
                "model",
                "notebookLM",
                "notebooklm_enabled",
            ]
        }
        raw = f"{message}|{safe_options}"
        return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _dedupe_key(text: str) -> str:
        return re.sub(r"\W+", " ", str(text or "").lower()).strip()[:220]

    @staticmethod
    def _dedupe_list(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value not in seen:
                result.append(value)
                seen.add(value)
        return result
