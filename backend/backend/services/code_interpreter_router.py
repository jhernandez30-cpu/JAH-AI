from __future__ import annotations

import re
from typing import Any

from services.conversation_resolver import normalize_text


CODE_BLOCK_RE = re.compile(r"```(?P<language>[\w#+.-]*)\s*\n(?P<code>.*?)(?:\n```|$)", re.DOTALL)


LANGUAGE_HINTS = [
    ("python", r"\b(def |import |from .* import|print\(|self\.|__name__|pip |pytest|python)\b"),
    ("csharp", r"\b(using System|namespace |public class|private |static void Main|Console\.WriteLine|c#|csharp)\b"),
    ("sql", r"\b(SELECT |CREATE TABLE|INSERT INTO|UPDATE |DELETE FROM|FOREIGN KEY|PRIMARY KEY|JOIN |sql)\b"),
    ("html", r"(<html|<div|<body|<head|<!doctype html|</\w+>)"),
    ("css", r"\b(display:\s|grid-template|font-size:|background:|color:|\.css)\b"),
    ("javascript", r"\b(function |const |let |var |=>|console\.log|document\.|javascript|typescript)\b"),
    ("json", r"^\s*[\{\[][\s\S]*[\}\]]\s*$"),
    ("yaml", r"^\s*[\w-]+:\s+.+"),
    ("bash", r"\b(#!/bin/bash|sudo |apt |grep |chmod |curl |bash)\b"),
    ("powershell", r"\b(Get-ChildItem|Set-Item|Write-Host|PowerShell|\$env:)\b"),
]


def extract_code_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for match in CODE_BLOCK_RE.finditer(str(text or "")):
        language = (match.group("language") or "").strip().lower()
        code = (match.group("code") or "").strip()
        if code:
            blocks.append({"language": language or detect_code_language(code), "code": code})
    return blocks


def detect_code_language(text: str) -> str:
    raw = str(text or "")
    for language, pattern in LANGUAGE_HINTS:
        if re.search(pattern, raw, re.IGNORECASE | re.MULTILINE):
            return language
    return ""


def analyze_code_request(message: str) -> dict[str, Any]:
    blocks = extract_code_blocks(message)
    code_text = "\n\n".join(block["code"] for block in blocks)
    language = blocks[0]["language"] if blocks else detect_code_language(message)
    normalized = normalize_text(message)

    action = "analysis"
    if re.search(r"\b(explica|explicame|que hace|como funciona)\b", normalized):
        action = "explain"
    elif re.search(r"\b(corrige|arregla|error|debug|traceback|por que falla|no funciona)\b", normalized):
        action = "debug"
    elif re.search(r"\b(revisa|review|mejora|optimiza|hazlo mas seguro|vulnerabilidad)\b", normalized):
        action = "review"

    return {
        "has_code": bool(blocks or code_text or language),
        "language": language,
        "action": action,
        "code_blocks": blocks,
        "code": code_text,
    }
