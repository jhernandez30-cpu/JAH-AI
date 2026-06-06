from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.notebooklm_service import NotebookLMService


def main() -> int:
    service = NotebookLMService(enabled=True)
    status = service.get_status(check_auth=False)
    print("NotebookLM instalado:", status["installed"])
    print("Perfil:", status["profile"])
    print("Notebook activo:", status["active_notebook_id"] or "(sin configurar)")

    notebooks = service.list_notebooks()
    if not notebooks.ok:
        print("No se pudieron listar notebooks:", notebooks.message)
        print("Fallback OK: la app puede seguir usando el cerebro local.")
        return 0

    print(f"Notebooks encontrados: {len(notebooks.data or [])}")
    active_id = service.get_active_notebook() or ((notebooks.data or [{}])[0].get("id") if notebooks.data else "")
    if not active_id:
        print("No hay notebook activo para preguntar.")
        return 0

    answer = service.ask("Resume el contenido principal en una frase.", active_id)
    if answer.ok:
        print("Respuesta NotebookLM:", answer.answer[:500])
    else:
        print("NotebookLM no respondio:", answer.message)
        print("Fallback OK: la app puede seguir usando el cerebro local.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

