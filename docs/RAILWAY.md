# Railway

Configuracion del servicio:

- Root Directory: `backend`
- Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Healthcheck: `/api/health`

Variables principales:

```env
ENVIRONMENT=production
FRONTEND_URL=https://jah-ai.vercel.app
CORS_ALLOWED_ORIGINS=https://jah-ai.vercel.app
SUPABASE_URL=
SUPABASE_ANON_KEY=
DATABASE_URL=
SUPABASE_GOOGLE_ENABLED=true
SUPABASE_APPLE_ENABLED=true
OWNER_EMAIL=josuea.hernandezg@gmail.com
ADMIN_EMAILS=josuea.hernandezg@gmail.com
TUTOR_IA_JWT_SECRET=
MODEL_PROVIDER=
MODEL_NAME=
OPENAI_API_KEY=
GEMINI_API_KEY=
OLLAMA_BASE_URL=
AI_GATEWAY_API_KEY=
AI_GATEWAY_BASE_URL=https://ai-gateway.vercel.sh/v1
```

`SUPABASE_SERVICE_ROLE_KEY` es opcional y solo debe existir en Railway, nunca en frontend.

Antes de configurar `SUPABASE_URL`, `SUPABASE_ANON_KEY` y `DATABASE_URL`, ejecuta `supabase/schema.sql` en Supabase SQL Editor. No uses la tabla demo `notes` como base de JAH AI.

Prueba:

```powershell
Invoke-RestMethod https://jah-ai-bridge-production.up.railway.app/api/health
curl.exe -i -X OPTIONS "https://jah-ai-bridge-production.up.railway.app/api/health" -H "Origin: https://jah-ai.vercel.app" -H "Access-Control-Request-Method: GET"
```

El preflight debe responder `access-control-allow-origin: https://jah-ai.vercel.app`. Si devuelve `Disallowed CORS origin`, el servicio desplegado no tiene `FRONTEND_URL`/`CORS_ALLOWED_ORIGINS` correctos o Railway esta ejecutando una version anterior.
