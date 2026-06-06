// Safe Odysseus adapter for the JAH AI programming assistant.
(function (global) {
  const UPLOAD_META_KEY = 'jah_ai_uploaded_files_meta';
  const OFFLINE_UPLOAD_KEY = 'odysseus_offline_uploads';

  function apiBase() {
    if (typeof global.APP_CONFIG?.resolveApiBaseUrl === 'function') {
      return global.APP_CONFIG.resolveApiBaseUrl();
    }
    return String(global.APP_CONFIG?.API_BASE_URL || global.TUTOR_IA_BRIDGE_URL || '').trim().replace(/\/$/, '');
  }

  function authHeaders(extra = {}) {
    const auth = global.JAHAuth && typeof global.JAHAuth.getAuthHeaders === 'function'
      ? global.JAHAuth.getAuthHeaders()
      : {};
    return { ...auth, ...extra };
  }

  function readJson(value, fallback) {
    try {
      return JSON.parse(value || '');
    } catch (_) {
      return fallback;
    }
  }

  function readUploadMeta() {
    const items = readJson(localStorage.getItem(UPLOAD_META_KEY), []);
    return Array.isArray(items) ? items : [];
  }

  function writeUploadMeta(items) {
    localStorage.setItem(UPLOAD_META_KEY, JSON.stringify(items.slice(-80)));
  }

  function cacheUploadMeta(file, response) {
    const files = Array.isArray(response?.files) ? response.files : [response].filter(Boolean);
    const items = readUploadMeta();
    files.forEach(item => {
      const relativePath = item.relative_path || item.path || '';
      if (!relativePath) return;
      items.push({
        name: item.name || item.filename || file?.name || 'archivo',
        relative_path: relativePath,
        path: relativePath,
        size: item.size || file?.size || 0,
        content_type: item.content_type || file?.type || '',
        uploaded_at: new Date().toISOString()
      });
    });
    writeUploadMeta(items);
  }

  async function fetchJson(path, options = {}, timeoutMs = 45000) {
    const base = apiBase();
    if (!base) return { ok: false, error: 'API_BASE_URL_NOT_CONFIGURED' };
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(`${base}${path}`, {
        ...options,
        headers: authHeaders(options.headers || {}),
        signal: controller.signal
      });
      const data = await response.json().catch(() => ({}));
      return { ...data, ok: data.ok !== false && response.ok, http_status: response.status };
    } catch (error) {
      return { ok: false, error: error.message || String(error) };
    } finally {
      clearTimeout(timeout);
    }
  }

  async function status() {
    const result = await fetchJson('/api/odysseus/status', { method: 'GET' }, 12000);
    if (result.ok) {
      localStorage.setItem('odysseus_last_status', JSON.stringify(result));
      return result;
    }
    const cached = readJson(localStorage.getItem('odysseus_last_status'), null);
    return cached || result;
  }

  async function upload(file, sessionId) {
    const base = apiBase();
    if (!base) return { ok: false, error: 'API_BASE_URL_NOT_CONFIGURED' };
    const formData = new FormData();
    formData.append('file', file, file.name);
    const headers = {};
    if (sessionId) headers['X-Session-Id'] = sessionId;
    try {
      const response = await fetch(`${base}/api/upload`, {
        method: 'POST',
        headers: authHeaders(headers),
        body: formData
      });
      const data = await response.json().catch(() => ({}));
      const result = { ...data, ok: data.ok !== false && response.ok, http_status: response.status };
      if (result.ok) cacheUploadMeta(file, result);
      return result;
    } catch (error) {
      const uploads = readJson(localStorage.getItem(OFFLINE_UPLOAD_KEY), []);
      uploads.push({ filename: file.name, size: file.size, timestamp: Date.now() });
      localStorage.setItem(OFFLINE_UPLOAD_KEY, JSON.stringify(uploads.slice(-40)));
      return { ok: false, error: error.message || String(error), stored: true };
    }
  }

  async function action(endpoint, payload) {
    const result = await fetchJson(`/api/odysseus/${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {})
    }, 60000);
    if (result.ok) {
      localStorage.setItem('odysseus_last_action', JSON.stringify({ endpoint, payload, result, ts: Date.now() }));
      return result;
    }
    const cached = readJson(localStorage.getItem('odysseus_last_action'), null);
    return cached?.endpoint === endpoint ? cached.result : result;
  }

  function analyze(payload) { return action('analyze', payload); }
  function code(payload) { return action('code', payload); }
  function debug(payload) { return action('debug', payload); }
  function plan(payload) { return action('plan', payload); }

  async function files_list(sessionId) {
    const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
    const result = await fetchJson(`/api/odysseus/files/list${qs}`, { method: 'GET' }, 20000);
    if (result.ok && Array.isArray(result.files)) {
      const merged = [...readUploadMeta(), ...result.files].filter(item => item && (item.relative_path || item.path));
      writeUploadMeta(merged);
    }
    return result.ok ? result : { ...result, files: readUploadMeta() };
  }

  async function files_search(query) {
    const result = await fetchJson('/api/odysseus/files/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query || '' })
    }, 20000);
    if (result.ok) return result;
    const q = String(query || '').toLowerCase();
    const files = readUploadMeta().filter(file => (
      String(file.name || '').toLowerCase().includes(q) ||
      String(file.relative_path || file.path || '').toLowerCase().includes(q)
    ));
    return { ...result, files };
  }

  function files_read(path, maxChars) {
    return fetchJson('/api/odysseus/files/read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, max_chars: maxChars || 12000 })
    }, 20000);
  }

  function tools_run(tool, args) {
    return fetchJson('/api/odysseus/tools/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool, args: args || {} })
    }, 30000);
  }

  global.odysseus = {
    status,
    upload,
    analyze,
    code,
    debug,
    plan,
    files_list,
    files_search,
    files_read,
    tools_run,
    readUploadMeta
  };
})(window);
