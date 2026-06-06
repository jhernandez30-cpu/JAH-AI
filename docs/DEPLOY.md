# Deploy JAH AI

JAH AI se despliega como dos servicios separados:

- Frontend estatico en Vercel con root `frontend`.
- Backend FastAPI en Railway con root `backend`.

## Validacion previa

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8787

cd ..\frontend
npm run test:ui
```

## Orden recomendado

1. Publicar el repositorio limpio en GitHub.
2. Crear el servicio backend en Railway.
3. Configurar variables Railway.
4. Validar `/api/health`.
5. Crear el proyecto frontend en Vercel.
6. Configurar la URL publica Railway en `frontend/asistente-programacion.html` y `frontend/js/app-config.js`.
7. Validar login, chat, upload y herramientas avanzadas.

## URLs de produccion actuales

- Frontend Vercel: `https://jah-ai.vercel.app`
- Backend Railway: `https://jah-ai-bridge-production.up.railway.app`

## Configuracion critica

Vercel debe tener `Root Directory` en `frontend`, `Framework Preset` en `Other`, `Build Command` vacio y `Output Directory` en `.`. Railway debe tener `Root Directory` en `backend` y arrancar con `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.

En Railway configura:

```env
FRONTEND_URL=https://jah-ai.vercel.app
CORS_ALLOWED_ORIGINS=https://jah-ai.vercel.app
```

Despues de cambiar variables externas, redeploya Railway y valida el preflight CORS desde el origen Vercel.

Los secretos se configuran solo en Railway o Supabase. No deben estar en Git.
