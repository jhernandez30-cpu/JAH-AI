# Railway

Configuracion del servicio:

- Root Directory: `backend`
- Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Healthcheck: `/api/health`

Variables principales:

```env
ENVIRONMENT=production
FRONTEND_URL=https://TU-FRONTEND-VERCEL.vercel.app
CORS_ALLOWED_ORIGINS=https://TU-FRONTEND-VERCEL.vercel.app
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
```

`SUPABASE_SERVICE_ROLE_KEY` es opcional y solo debe existir en Railway, nunca en frontend.

Antes de configurar `SUPABASE_URL`, `SUPABASE_ANON_KEY` y `DATABASE_URL`, ejecuta `supabase/schema.sql` en Supabase SQL Editor. No uses la tabla demo `notes` como base de JAH AI.

Prueba:

```powershell
Invoke-RestMethod https://TU-SERVICIO-RAILWAY.up.railway.app/api/health
```
