# Backend JAH AI

API FastAPI para JAH AI. Expone chat, autenticacion, historial, carga segura de archivos e integracion Odysseus.

## Arranque local

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8787
```

## Railway

Railway debe ejecutar este directorio como proyecto backend.

- Build: Nixpacks.
- Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- Healthcheck: `/api/health`.
- Archivo principal: `railway.toml`.
- Variables: usar `.env.example` como plantilla y completar valores reales en Railway.

## Variables obligatorias en produccion

- `ENVIRONMENT=production`
- `PORT`
- `FRONTEND_URL`
- `CORS_ALLOWED_ORIGINS`
- `TUTOR_IA_JWT_SECRET`
- `DATABASE_URL` o variables Supabase equivalentes, si se usa persistencia remota.
- Al menos un proveedor LLM configurado, por ejemplo `GEMINI_API_KEY` o `OPENAI_API_KEY`.

## Odysseus

El adaptador propio vive en `backend/odysseus` y usa `odysseus-src` como fuente integrada. La API queda bajo `/api/odysseus/*`.

Los uploads y vectores se crean en runtime. No se versionan en Git.
