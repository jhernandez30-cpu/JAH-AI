# Supabase

Configurar:

1. Crear proyecto Supabase.
2. Activar Auth con email/password.
3. Activar Google y Apple si se usaran.
4. Agregar redirect URL:

```text
https://TU-FRONTEND-VERCEL.vercel.app/asistente-programacion.html
```

5. Configurar en Railway:

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
DATABASE_URL=
SUPABASE_GOOGLE_ENABLED=true
SUPABASE_APPLE_ENABLED=true
```

Reglas:

- `SUPABASE_SERVICE_ROLE_KEY` solo backend.
- No poner service role ni API keys privadas en HTML, JS ni Vercel publico.
- `.env` real no se versiona.
