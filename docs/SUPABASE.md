# Supabase

JAH AI no usa la tabla demo `notes` como estructura principal. La base real del proyecto esta en `supabase/schema.sql`.

## Ejecutar Schema

1. Entra a Supabase y abre el proyecto de JAH AI.
2. Ve a `SQL Editor`.
3. Crea una consulta nueva.
4. Copia completo el contenido de `supabase/schema.sql`.
5. Ejecuta la consulta.
6. Confirma que se crearon estas tablas: `profiles`, `spaces`, `projects`, `chats`, `messages`, `uploaded_files`, `user_settings`.
7. En `Authentication > Policies`, confirma que RLS esta activo en todas las tablas anteriores.
8. Confirma que existen politicas por usuario basadas en `auth.uid()`.

El schema tambien crea `public.set_updated_at()`, `public.handle_new_user()`, el trigger `on_auth_user_created` y los indices utiles para JAH AI.

## Variables Para Railway

Copia estos valores reales desde Supabase y pegalos en Railway, nunca en el repo:

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
DATABASE_URL=
SUPABASE_GOOGLE_ENABLED=true
SUPABASE_APPLE_ENABLED=true
```

Variables adicionales de backend:

```env
ENVIRONMENT=production
FRONTEND_URL=https://jah-ai.vercel.app
CORS_ALLOWED_ORIGINS=https://jah-ai.vercel.app
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

`SUPABASE_SERVICE_ROLE_KEY` es opcional y solo puede existir en Railway/backend. No debe ponerse en Vercel, HTML ni JavaScript.

## Auth Redirect URLs

En Supabase ve a `Authentication > URL Configuration`.

Configura `Site URL`:

```text
https://jah-ai.vercel.app
```

Agrega en `Redirect URLs`:

```text
https://jah-ai.vercel.app
https://jah-ai.vercel.app/asistente-programacion.html
```

## Google Provider

Activalo solo si se usara login con Google:

1. Crea o abre un proyecto en Google Cloud.
2. Configura OAuth consent screen.
3. Crea credenciales OAuth 2.0 Web Client.
4. Copia el Client ID y Client Secret en Supabase Auth Provider Google.
5. Copia el Redirect URI que Supabase muestra para Google y registralo en Google Cloud.
6. Deja `SUPABASE_GOOGLE_ENABLED=true` en Railway si el provider queda activo.

## Apple Provider

Activalo solo si se usara login con Apple:

1. Usa Apple Developer Account.
2. Configura Services ID / Client ID.
3. Configura Team ID.
4. Configura Key ID.
5. Carga la Private Key en Supabase Auth Provider Apple.
6. Copia el Redirect URI que Supabase muestra para Apple y registralo en Apple Developer.
7. Deja `SUPABASE_APPLE_ENABLED=true` en Railway si el provider queda activo.

## Redeploy Backend

Despues de cambiar variables en Railway, haz redeploy del servicio `jah-ai-bridge`.

Valida:

```powershell
Invoke-RestMethod https://jah-ai-bridge-production.up.railway.app/api/health
```

Esperado:

- Si falta Supabase: `supabase` debe mostrar `not_configured`.
- Si `SUPABASE_URL` y `SUPABASE_ANON_KEY` existen: `supabase` debe mostrar `configured`.
- Si `DATABASE_URL` existe y el driver esta disponible: `database` debe mostrar `connected`.

## Reglas

- No subir `.env`.
- No subir secretos reales.
- No usar `SUPABASE_SERVICE_ROLE_KEY` en frontend.
- No usar la tabla demo `notes` como base de JAH AI.
- No borrar tablas existentes de produccion sin autorizacion.
