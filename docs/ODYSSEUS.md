# Odysseus En JAH AI

La integracion visible en la interfaz se llama `Herramientas avanzadas`. El nombre visual del producto sigue siendo `JAH AI`.

Componentes:

- `backend/backend/odysseus/`: adaptador seguro usado por FastAPI.
- `backend/odysseus-src/`: fuente de referencia del proyecto Odysseus.
- `frontend/js/odysseus.js`: cliente browser para endpoints seguros.

Controles de seguridad:

- `safe_mode=true`.
- Upload centralizado en `/api/upload` y `/api/odysseus/files/upload`.
- Rutas relativas; no se devuelven rutas absolutas del sistema.
- Path traversal bloqueado.
- `.env`, claves privadas y patrones de secretos bloqueados en uploads.
- ZIP se inspecciona y extrae dentro de `backend/uploads`.
- Herramientas peligrosas no se ejecutan.

Endpoints:

```text
GET  /api/odysseus/status
POST /api/odysseus/analyze
POST /api/odysseus/code
POST /api/odysseus/debug
POST /api/odysseus/plan
POST /api/odysseus/files/upload
GET  /api/odysseus/files/list
POST /api/odysseus/files/search
POST /api/odysseus/files/read
POST /api/odysseus/tools/run
```
