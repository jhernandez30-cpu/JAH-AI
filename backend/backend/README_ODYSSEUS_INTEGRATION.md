Resumen de integración Odysseus y LLM Orquestador

Cambios realizados:
- services/file_service.py: ahora guarda uploads dentro de backend/uploads por defecto, valida extensiones, rechaza contenido con claves privadas o señales de secretos y permite ZIPs.
- services/file_service.py: funciones nuevas inspect_zip_contents y extract_zip_to_dir para inspeccionar y extraer ZIPs de forma segura (prevención Zip Slip).
- services/llm_orchestrator.py: nuevo servicio que selecciona proveedor de LLM según MODEL_PROVIDER y variables de entorno. Soporta OpenAI (si SDK presente), Ollama (si langchain_ollama disponible) y Anthropic (si servicio presente). Gemini es placeholder.
- main.py: endpoints /api/odysseus/analyze, /api/odysseus/code, /api/odysseus/debug, /api/odysseus/plan añadidos; estos usan llm_orchestrator y validan que los uploads referenciados estén dentro del directorio de uploads.
- Seguridad: no se accede a rutas de usuario del host ni a archivos fuera del directorio de uploads configurado; no se exponen claves al frontend.

Pendientes / Notas operativas:
- La integración con Gemini no está implementada y requiere un cliente oficial o API HTTP.
- OpenAI: requiere instalar paquete openai en el entorno y configurar OPENAI_API_KEY. Las llamadas se realizan desde backend y la clave no se expone.
- Ollama: uso mediante langchain_ollama si está instalado. En Railway probablemente no habrá Ollama local; usar modelo remoto mediante OpenAI u otro proveedor.
- tutor_ia: el proyecto ya tenía código que asume uso de Ollama/local models. Mantuvimos compatibilidad y añadimos orquestador que puede delegar si procede.
- Tests: no se ejecutaron tests automatizados en CI dentro de este entorno. Ejecuta pytest o simplemente prueba endpoints en entorno local.
- Validaciones extra: considera añadir escaneo antivirus o validaciones adicionales según políticas de seguridad de tu infra.

Cómo usar:
- Subir archivos via POST /api/upload (multipart/form-data, field `file`). Respuesta incluye `path` con ubicación en servidor (dentro de backend/uploads).
- Listar archivos: GET /api/files (requiere autenticación).
- Inspeccionar ZIP: llamar a services.file_service.inspect_zip_contents con path o exponer endpoint adicional si lo deseas.
- Analizar usando Odysseus endpoints: POST /api/odysseus/analyze con JSON {"message":"...","upload_path":"uploads/mi.zip"}.

Variables de entorno sugeridas:
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o-mini
OPENAI_API_KEY=
GEMINI_API_KEY=
OLLAMA_BASE_URL=

Consideraciones finales:
- No se ha cambiado la UI principal. Frontend puede usar los endpoints nuevos sin exponer claves.
- Asegura que la variable TUTOR_IA_UPLOAD_DIR apunte a una carpeta controlada en el contenedor, o usa el default backend/uploads.
- Evitar usar rutas absolutas del host (C:\Users, /home/...) en producción; el servidor ahora usa rutas internas.
