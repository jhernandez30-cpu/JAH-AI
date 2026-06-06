"""Adapter package for integrating Odysseus features into the jah-ai-bridge backend.
This package implements a safe router that exposes a limited subset of Odysseus
functionality via /api/odysseus/* while keeping the main UI intact.
"""

__all__ = ["router", "service", "schemas", "security", "storage"]
