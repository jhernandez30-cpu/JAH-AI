# Vercel

Configuracion del proyecto:

- Root Directory: `frontend`
- Framework Preset: Other / Static
- Build Command: vacio
- Output Directory: `.`
- URL final validada: `https://jah-ai.vercel.app`

`frontend/vercel.json` reescribe `/` hacia `/asistente-programacion.html`.

La URL de backend se resuelve con `frontend/js/app-config.js`:

- Local: `http://127.0.0.1:8787`
- Produccion: `https://jah-ai-bridge-production.up.railway.app`

Si Vercel muestra `404: NOT_FOUND`, revisa primero que el proyecto de Git tenga `Root Directory` en `frontend`. El deploy manual desde `frontend/` puede funcionar aunque el proyecto conectado al repositorio este apuntando a `.`; en ese caso los redeploys desde Git pueden no encontrar `index.html`.

No coloques claves privadas en Vercel para este frontend estatico. Solo valores publicos, por ejemplo `SUPABASE_ANON_KEY` si se decide exponer Supabase Auth directo.
