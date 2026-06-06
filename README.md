# JAH AI

JAH AI es un asistente de programacion con frontend estatico, backend FastAPI, autenticacion Supabase opcional e integracion segura de herramientas avanzadas basadas en Odysseus.

## Estructura

```text
JAH AI/
├── frontend/
│   ├── index.html
│   ├── asistente-programacion.html
│   ├── css/
│   ├── js/
│   ├── assets/brand/
│   ├── manifest.webmanifest
│   └── vercel.json
├── backend/
│   ├── backend/
│   │   ├── main.py
│   │   ├── odysseus/
│   │   ├── rag/
│   │   └── services/
│   ├── odysseus-src/
│   ├── requirements.txt
│   ├── railway.toml
│   ├── Procfile
│   └── .env.example
├── docs/
├── README.md
└── .gitignore
```

## Identidad

- Nombre visual: `JAH AI`.
- Logo oficial: `frontend/assets/brand/jah-ai-logo.png`.
- Logo optimizado para la interfaz clara: `frontend/assets/brand/jah-ai-logo-transparent.png`.
- La integracion Odysseus se muestra como `Herramientas avanzadas`; no reemplaza la identidad JAH AI.

## Frontend Local

```powershell
cd frontend
python -m http.server 5500 --bind 127.0.0.1
```

Abrir:

```text
http://127.0.0.1:5500/asistente-programacion.html
```

`frontend/index.html` redirige a `asistente-programacion.html`.

## Backend Local

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8787
```

Pruebas rapidas:

```powershell
Invoke-RestMethod http://127.0.0.1:8787/api/health
$body = @{ message = "prueba"; use_rag = $false } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8787/api/chat -Method Post -Body $body -ContentType "application/json"
```

## Vercel

- Root Directory: `frontend`
- Framework Preset: Other / Static
- Build Command: vacio
- Output Directory: `.`

Ver [docs/VERCEL.md](docs/VERCEL.md).

## Railway

- Root Directory: `backend`
- Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Healthcheck: `/api/health`

Ver [docs/RAILWAY.md](docs/RAILWAY.md).

## Variables Railway

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
DATABASE_URL=
SUPABASE_GOOGLE_ENABLED=true
SUPABASE_APPLE_ENABLED=true
OWNER_EMAIL=josuea.hernandezg@gmail.com
ADMIN_EMAILS=josuea.hernandezg@gmail.com
FRONTEND_URL=https://TU-FRONTEND-VERCEL.vercel.app
CORS_ALLOWED_ORIGINS=https://TU-FRONTEND-VERCEL.vercel.app
MODEL_PROVIDER=
MODEL_NAME=
OPENAI_API_KEY=
GEMINI_API_KEY=
OLLAMA_BASE_URL=
```

Opcional backend solamente:

```env
SUPABASE_SERVICE_ROLE_KEY=
```

No subir `.env` real ni secretos.

## Supabase

Ver [docs/SUPABASE.md](docs/SUPABASE.md).

## Endpoints

```text
GET  /api/health
POST /api/chat
GET  /api/history
POST /api/history
GET  /api/projects
POST /api/projects
GET  /api/spaces
POST /api/spaces
POST /api/upload
GET  /api/odysseus/status
POST /api/odysseus/analyze
POST /api/odysseus/code
POST /api/odysseus/debug
POST /api/odysseus/plan
GET  /api/odysseus/files/list
POST /api/odysseus/files/search
POST /api/odysseus/files/read
```

## Odysseus

Ver [docs/ODYSSEUS.md](docs/ODYSSEUS.md).

## Pruebas

Frontend:

```powershell
cd frontend
npm install
npm run test:ui
```

Backend:

```powershell
cd backend
python -m compileall backend
```

Smoke de endpoints:

```powershell
Invoke-RestMethod http://127.0.0.1:8787/api/health
Invoke-RestMethod http://127.0.0.1:8787/api/odysseus/status
```

## Pendientes Externos

- URL final de Vercel.
- URL final de Railway si cambia.
- Credenciales Supabase reales.
- `DATABASE_URL` real.
- Configuracion Google/Apple OAuth.
- Proveedor IA final si se usara una API externa.
