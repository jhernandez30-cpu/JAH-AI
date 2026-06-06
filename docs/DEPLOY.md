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

Los secretos se configuran solo en Railway o Supabase. No deben estar en Git.
