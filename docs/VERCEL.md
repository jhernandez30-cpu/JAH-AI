# Vercel

Configuracion del proyecto:

- Root Directory: `frontend`
- Framework Preset: Other / Static
- Build Command: vacio
- Output Directory: `.`

`frontend/vercel.json` reescribe `/` hacia `/asistente-programacion.html`.

La URL de backend se resuelve con `frontend/js/app-config.js`:

- Local: `http://127.0.0.1:8787`
- Produccion: meta tag `jah-api-base-url` o URL Railway configurada.

No coloques claves privadas en Vercel para este frontend estatico. Solo valores publicos, por ejemplo `SUPABASE_ANON_KEY` si se decide exponer Supabase Auth directo.
