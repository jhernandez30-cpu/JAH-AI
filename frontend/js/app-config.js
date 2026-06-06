(() => {
  const LOCAL_API_BASE_URL = 'http://127.0.0.1:8787';
  const RAILWAY_API_BASE_URL = 'https://jah-ai-bridge-production.up.railway.app';
  const RAILWAY_PLACEHOLDER = 'https://TU-SERVICIO-RAILWAY.up.railway.app';

  const meta = name => (
    document.querySelector(`meta[name="${name}"]`)?.getAttribute('content') || ''
  ).trim();

  const isLocal =
    location.protocol === 'file:' ||
    location.hostname === 'localhost' ||
    location.hostname === '127.0.0.1';

  const configuredApiBaseUrl =
    window.NEXT_PUBLIC_API_BASE_URL ||
    meta('jah-api-base-url') ||
    RAILWAY_API_BASE_URL ||
    RAILWAY_PLACEHOLDER;

  const productionApiBaseUrl = String(configuredApiBaseUrl).replace(/\/$/, '');
  const apiBaseUrl = isLocal ? LOCAL_API_BASE_URL : productionApiBaseUrl;

  window.APP_CONFIG = {
    ...(window.APP_CONFIG || {}),
    RUN_MODE: isLocal ? 'local' : 'production',
    IS_LOCAL: isLocal,
    LOCAL_API_BASE_URL,
    PRODUCTION_API_BASE_URL: productionApiBaseUrl,
    API_BASE_URL: apiBaseUrl,
    SUPABASE_URL: meta('supabase-url'),
    SUPABASE_ANON_KEY: meta('supabase-anon-key'),
    SUPABASE_GOOGLE_ENABLED: meta('supabase-google-enabled') === 'true',
    SUPABASE_APPLE_ENABLED: meta('supabase-apple-enabled') === 'true',
    DEBUG_APP_FLOW: meta('jah-debug-app-flow') === 'true',
    resolveApiBaseUrl() {
      const explicit = String(window.NEXT_PUBLIC_API_BASE_URL || '').trim().replace(/\/$/, '');
      if (explicit && !isLocal) return explicit;
      return this.API_BASE_URL;
    }
  };

  window.TUTOR_IA_BRIDGE_URL = window.APP_CONFIG.resolveApiBaseUrl();
  window.TUTOR_IA_ENDPOINTS = [`${window.TUTOR_IA_BRIDGE_URL}/api/chat`];
})();
