const STORAGE_KEY = 'tutorIaChatHistory';
const ACTIVE_CHAT_KEY = 'tutorIaActiveChatId';
const SESSION_KEY = 'jah_ai_session_id';
const TUTOR_IA_ENABLED_KEY = 'tutorIaEnabled';
const JAH_AI_CHATS_KEY = 'jah_ai_chats';
const JAH_AI_CURRENT_CHAT_KEY = 'jah_ai_current_chat';
const JAH_AI_SPACES_KEY = 'jah_ai_spaces';
const JAH_AI_PROJECTS_KEY = 'jah_ai_projects';
const JAH_AI_SETTINGS_KEY = 'jah_ai_settings';
const JAH_AI_UPLOADED_FILES_META_KEY = 'jah_ai_uploaded_files_meta';
const DEFAULT_MODE = 'Cerebro Unificado';
const PROJECT_PATH = window.TUTOR_IA_PROJECT_PATH || '';
const BRAIN_ROOT = window.TUTOR_IA_BRAIN_ROOT || '';
function getBridgeUrl() {
  if (typeof window.APP_CONFIG?.resolveApiBaseUrl === 'function') {
    return window.APP_CONFIG.resolveApiBaseUrl();
  }
  return String(
    window.APP_CONFIG?.API_BASE_URL
    || window.TUTOR_IA_BRIDGE_URL
    || window.APP_CONFIG?.LOCAL_API_BASE_URL
    || ''
  ).trim().replace(/\/$/, '');
}

function isLocalBridgeMode() {
  return String(window.APP_CONFIG?.RUN_MODE || '').toLowerCase() === 'local';
}

function getChatEndpoint() {
  const bridgeUrl = getBridgeUrl();
  return bridgeUrl ? `${bridgeUrl}/api/chat` : '';
}

function getUploadEndpoint() {
  const bridgeUrl = getBridgeUrl();
  return bridgeUrl ? `${bridgeUrl}/api/upload` : '';
}

function getJarvisMarkStatusEndpoint() {
  const bridgeUrl = getBridgeUrl();
  return bridgeUrl ? `${bridgeUrl}/api/jarvis/mark/status` : '';
}

function getJarvisMarkLaunchEndpoint() {
  const bridgeUrl = getBridgeUrl();
  return bridgeUrl ? `${bridgeUrl}/api/jarvis/mark/launch` : '';
}

function getDefaultEndpoints() {
  const bridgeUrl = getBridgeUrl();
  return bridgeUrl ? [`${bridgeUrl}/api/chat`] : [];
}
const CHAT_TIMEOUT_MS = 120000;
const CLIENT_CONTEXT_TURNS = 6;
const CLIENT_CONTEXT_MAX_CHARS = 2400;
const JARVIS_READ_RESPONSES = window.JARVIS_READ_RESPONSES === undefined
  ? true
  : window.JARVIS_READ_RESPONSES === true || window.JARVIS_READ_RESPONSES === 'true';
const ALLOWED_FILE_EXTENSIONS = new Set([
  'png', 'jpg', 'jpeg', 'webp', 'pdf', 'docx', 'txt', 'md', 'csv', 'json', 'zip',
  'py', 'js', 'jsx', 'ts', 'tsx', 'html', 'css', 'scss', 'sql', 'cs', 'java',
  'go', 'rs', 'php', 'rb', 'swift', 'kt', 'sh', 'ps1', 'yml', 'yaml', 'toml'
]);

document.addEventListener('DOMContentLoaded', () => {
  const appSplash = document.getElementById('appSplash');
  const chatMain = document.querySelector('.chat-main');
  const coachMessages = document.getElementById('coachMessages');
  const emptyChatState = document.getElementById('emptyChatState');
  const coachForm = document.getElementById('coachForm');
  const coachInput = document.getElementById('coachInput');
  const brainStatus = document.getElementById('brainStatus');
  const brainStatusText = document.getElementById('brainStatusText');
  const adminOnlyElements = document.querySelectorAll('[data-admin-only]');
  const quickContextCard = document.querySelector('.quick-context-card');
  const newChatBtn = document.getElementById('newChatBtn');
  const openSearchBtn = document.getElementById('openSearchBtn');
  const chatHistoryList = document.getElementById('chatHistoryList');
  const activeChatLabel = document.getElementById('activeChatLabel');
  const clearHistoryBtn = document.getElementById('clearHistoryBtn');
  const openSidebarBtn = document.getElementById('openSidebarBtn');
  const closeSidebarBtn = document.getElementById('closeSidebarBtn');
  const chatSidebar = document.getElementById('chatSidebar');
  const sidebarBackdrop = document.getElementById('sidebarBackdrop');
  const tutorIABtn = document.getElementById('tutorIABtn');
  const smartSearchBtn = document.getElementById('smartSearchBtn');
  const fileInput = document.getElementById('fileInput');
  const attachmentPreview = document.getElementById('attachmentPreview');
  const sendButton = coachForm ? coachForm.querySelector('.send-orb') : null;
  const jarvisVoiceBtn = document.getElementById('jarvisVoiceBtn');
  const jarvisStatus = document.getElementById('jarvisStatus');
  const assistantPanelOverlay = document.getElementById('assistantPanelOverlay');
  const assistantPanel = document.getElementById('assistantPanel');
  const assistantPanelKicker = document.getElementById('assistantPanelKicker');
  const assistantPanelTitle = document.getElementById('assistantPanelTitle');
  const assistantPanelDescription = document.getElementById('assistantPanelDescription');
  const assistantPanelContent = document.getElementById('assistantPanelContent');
  const closeAssistantPanelBtn = document.getElementById('closeAssistantPanelBtn');
  const sidebarActionButtons = document.querySelectorAll('[data-action]');

  function hideAppSplash() {
    if (!appSplash) return;
    appSplash.classList.add('is-hidden');
    appSplash.remove();
  }

  window.addEventListener('load', hideAppSplash, { once: true });
  window.setTimeout(hideAppSplash, 1200);

  function getEndpointCandidates() {
    return normalizeEndpoints(window.TUTOR_IA_ENDPOINTS || getDefaultEndpoints());
  }

  let activeTutorEndpoint = '';
  let adminSystemStatusVisible = false;
  let tutorIAEnabled = readTutorIaPreference(true);
  let tutorConnectionStatus = 'UNKNOWN';
  let tutorConnectionLabel = 'Sin verificar';
  let smartSearchEnabled = false;
  let deepThinkingEnabled = false;
  let selectedFiles = [];
  let isSubmitting = false;
  let jarvisSupported = false;
  let jarvisAssistant = null;
  let chats = [];
  let activeChatId = '';
  let currentSessionId = '';
  let activeStorageScope = '';
  let activeHistoryQuery = '';
  let activePanelType = '';
  let lastSystemHealth = null;
  let backendHistoryCache = [];
  let spaces = [];
  let projects = [];
  let assistantSettings = {};
  let activeSpaceId = '';
  let activeProjectId = '';
  let authChecked = false;
  let appInitialized = false;
  let historyLoaded = false;
  let isHydrating = true;

  const DISCOVER_PROMPTS = [
    {
      title: 'Revisar un bug',
      description: 'Analiza un error, causa probable y pasos concretos.',
      prompt: 'Revisa este error como ingeniero senior. Dame causa real, archivos probables, solucion y pruebas: '
    },
    {
      title: 'Optimizar codigo',
      description: 'Encuentra mejoras sin cambiar el comportamiento.',
      prompt: 'Optimiza este codigo sin romper compatibilidad. Explica riesgos y pruebas necesarias: '
    },
    {
      title: 'Crear pruebas',
      description: 'Pide casos de prueba enfocados en riesgo real.',
      prompt: 'Crea pruebas para esta funcion. Incluye casos borde, errores esperados y datos de ejemplo: '
    },
    {
      title: 'Explicar arquitectura',
      description: 'Resume dependencias, flujo y puntos fragiles.',
      prompt: 'Explicame la arquitectura de este modulo y donde conviene modificarlo sin romper nada: '
    }
  ];

  window.tutorIAEnabled = tutorIAEnabled;
  window.smartSearchEnabled = smartSearchEnabled;
  window.deepThinkingEnabled = deepThinkingEnabled;

  function normalizeEndpoints(endpoints) {
    return [...new Set(endpoints.filter(Boolean).map(endpoint => endpoint.replace(/\/$/, '')))];
  }

  function endpointBaseUrl(endpoint) {
    try {
      const url = new URL(endpoint);
      return `${url.protocol}//${url.hostname}${url.port ? `:${url.port}` : ''}`;
    } catch (error) {
      return getBridgeUrl();
    }
  }

  function endpointHealthUrls(endpoint) {
    const base = endpointBaseUrl(endpoint);
    return [
      `${base}/health`,
      `${base}/status`,
      `${base}/api/health`,
      `${base}/api/status`,
      `${base}/api/unified-brain/health`,
      `${base}/api/unified-brain/status`
    ];
  }

  function ragHealthUrl() {
    return `${getBridgeUrl()}/api/health`;
  }

  function adminStatusUrl() {
    return `${getBridgeUrl()}/api/admin/system-status`;
  }

  function endpointHostKey(endpoint) {
    try {
      const url = new URL(endpoint);
      return `${url.protocol}//${url.hostname}${url.port ? `:${url.port}` : ''}`;
    } catch (error) {
      return endpoint;
    }
  }

  function normalizeHealthPayload(data) {
    const brain = data && typeof data.brain === 'object' ? data.brain : {};
    const models = data && typeof data.models === 'object' ? data.models : {};
    const model = data.model || brain.active_model || models.active_model || '';
    const fragments = Number(data.fragments || brain.local_sources || brain.fragments || 0);
    const obsidian = data.obsidian && typeof data.obsidian === 'object' ? data.obsidian : {};
    const agency = data.agency && typeof data.agency === 'object' ? data.agency : {};
    const jarvis = data.jarvis && typeof data.jarvis === 'object' ? data.jarvis : {};
    const anthropic = data.anthropic || brain.anthropic || {};
    const anthropicConfigured = Boolean(
      anthropic.configured ||
      anthropic.connected ||
      anthropic.available ||
      data.anthropic_configured
    );

    return {
      ok: Boolean(data.ok || data.success || Object.keys(brain).length),
      fragments,
      obsidianNotes: Number(obsidian.notes || brain.obsidian_notes || 0),
      agencyAgents: Number(agency.count || brain.agency_specialists || 0),
      jarvisProfiles: Number(jarvis.detected_profiles || brain.detected_profiles || 0),
      tutorConnected: Boolean(data.tutor_ia_connected || brain.openjarvis || fragments),
      model,
      root: data.tutor_ia_root || data.root_dir || brain.root || '',
      mode: brain.mode || data.mode || 'local-first',
      anthropicConfigured
    };
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function createId() {
    return `chat-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function createSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function createChat() {
    const createdAt = nowIso();
    const sessionId = createSessionId();
    return {
      id: createId(),
      sessionId,
      title: 'Nuevo chat',
      createdAt,
      updatedAt: createdAt,
      messages: []
    };
  }

  function normalizeChatRecord(chat) {
    const createdAt = chat.createdAt || chat.created_at || nowIso();
    const updatedAt = chat.updatedAt || chat.updated_at || createdAt;
    return {
      ...chat,
      id: chat.id || createId(),
      sessionId: chat.sessionId || chat.session_id || createSessionId(),
      title: chat.title || 'Nuevo chat',
      createdAt,
      updatedAt,
      messages: Array.isArray(chat.messages) ? chat.messages : []
    };
  }

  function ensureChatSessionId(chat) {
    if (!chat) return loadOrCreateSessionId();
    if (!chat.sessionId && chat.session_id) chat.sessionId = chat.session_id;
    if (!chat.sessionId) chat.sessionId = createSessionId();
    return chat.sessionId;
  }

  function flowLog(event, detail = {}) {
    if (!window.APP_CONFIG?.DEBUG_APP_FLOW) return;
    console.debug('[JAH AI flow]', event, {
      authChecked,
      appInitialized,
      historyLoaded,
      isHydrating,
      activeStorageScope,
      ...detail
    });
  }

  function getAuthStorageScope() {
    const context = getAuthContext();
    const user = context.user || {};
    const rawKey = user.id || user.email || '';
    if (!context.loggedIn || !rawKey) return 'guest';
    return `user:${String(rawKey).trim().toLowerCase()}`;
  }

  function scopedStorageKey(base, scope = activeStorageScope) {
    return scope && scope !== 'guest'
      ? `${base}:${scope}`
      : base;
  }

  function readStorageValue(key, fallback = '') {
    try {
      return localStorage.getItem(key) || fallback;
    } catch (error) {
      return fallback;
    }
  }

  function writeStorageValue(key, value) {
    try {
      localStorage.setItem(key, value);
      return true;
    } catch (error) {
      return false;
    }
  }

  function readJsonValue(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch (error) {
      return fallback;
    }
  }

  function writeJsonValue(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (error) {
      return false;
    }
  }

  function normalizeUploadedFileMeta(item) {
    if (!item) return null;
    const relativePath = item.relative_path || item.path || '';
    if (!relativePath) return null;
    return {
      name: item.name || item.filename || item.original_filename || relativePath.split('/').pop() || 'archivo',
      relative_path: relativePath,
      path: relativePath,
      size: Number(item.size || item.file_size || 0),
      content_type: item.content_type || item.file_type || '',
      uploaded_at: item.uploaded_at || item.created_at || nowIso()
    };
  }

  function readUploadedFileMeta() {
    const parsed = readJsonValue(JAH_AI_UPLOADED_FILES_META_KEY, []);
    return Array.isArray(parsed) ? parsed.map(normalizeUploadedFileMeta).filter(Boolean) : [];
  }

  function writeUploadedFileMeta(items) {
    const deduped = [];
    const seen = new Set();
    (items || []).map(normalizeUploadedFileMeta).filter(Boolean).forEach(item => {
      const key = item.relative_path;
      if (seen.has(key)) return;
      seen.add(key);
      deduped.push(item);
    });
    writeJsonValue(JAH_AI_UPLOADED_FILES_META_KEY, deduped.slice(-80));
    return deduped;
  }

  function mergeUploadedFileMeta(items) {
    return writeUploadedFileMeta([...readUploadedFileMeta(), ...(items || [])]);
  }

  function loadLocalCollection(key) {
    const parsed = readJsonValue(key, []);
    return Array.isArray(parsed) ? parsed.filter(item => item && item.id) : [];
  }

  function loadAssistantSettings() {
    const parsed = readJsonValue(JAH_AI_SETTINGS_KEY, {});
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  }

  function persistAssistantSettings(patch = {}) {
    assistantSettings = {
      ...assistantSettings,
      ...patch,
      updatedAt: nowIso()
    };
    writeJsonValue(JAH_AI_SETTINGS_KEY, assistantSettings);
    return assistantSettings;
  }

  function mirrorChatStorage() {
    if (shouldPersistChatHistory()) {
      writeJsonValue(JAH_AI_CHATS_KEY, chats);
    }
    writeStorageValue(JAH_AI_CURRENT_CHAT_KEY, activeChatId);
  }

  function persistSpaces() {
    writeJsonValue(JAH_AI_SPACES_KEY, spaces);
  }

  function persistProjects() {
    writeJsonValue(JAH_AI_PROJECTS_KEY, projects);
  }

  function readTutorIaPreference(fallback = true) {
    try {
      const stored = localStorage.getItem(TUTOR_IA_ENABLED_KEY);
      if (stored === 'true') return true;
      if (stored === 'false') return false;
    } catch (error) {
      return fallback;
    }
    return fallback;
  }

  function hasTutorIaPreference() {
    try {
      const stored = localStorage.getItem(TUTOR_IA_ENABLED_KEY);
      return stored === 'true' || stored === 'false';
    } catch (error) {
      return false;
    }
  }

  function persistTutorIaPreference(enabled) {
    return writeStorageValue(TUTOR_IA_ENABLED_KEY, String(Boolean(enabled)));
  }

  function loadChats() {
    try {
      const scopedKey = scopedStorageKey(STORAGE_KEY);
      const scopedMirrorKey = scopedStorageKey(JAH_AI_CHATS_KEY);
      let raw = readStorageValue(scopedKey);
      if (!raw) raw = readStorageValue(scopedMirrorKey);
      if (!raw) {
        raw = readStorageValue(STORAGE_KEY) || readStorageValue(JAH_AI_CHATS_KEY) || '[]';
        if (activeStorageScope && activeStorageScope !== 'guest' && raw !== '[]') {
          writeStorageValue(scopedKey, raw);
          writeStorageValue(scopedMirrorKey, raw);
        }
      }
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed)
        ? parsed.filter(chat => chat && chat.id).map(normalizeChatRecord)
        : [];
    } catch (error) {
      return [];
    }
  }

  function loadActiveChatId() {
    try {
      const scopedKey = scopedStorageKey(ACTIVE_CHAT_KEY);
      const scopedMirrorKey = scopedStorageKey(JAH_AI_CURRENT_CHAT_KEY);
      let value = readStorageValue(scopedKey);
      if (!value) value = readStorageValue(scopedMirrorKey);
      if (!value) {
        value = readStorageValue(ACTIVE_CHAT_KEY) || readStorageValue(JAH_AI_CURRENT_CHAT_KEY) || '';
        if (activeStorageScope && activeStorageScope !== 'guest' && value) {
          writeStorageValue(scopedKey, value);
          writeStorageValue(scopedMirrorKey, value);
        }
      }
      return value;
    } catch (error) {
      return '';
    }
  }

  function loadOrCreateSessionId() {
    try {
      const sessionKey = scopedStorageKey(SESSION_KEY);
      const scopedExisting = readStorageValue(sessionKey);
      const existing = scopedExisting || readStorageValue(SESSION_KEY);
      if (!scopedExisting && existing && activeStorageScope && activeStorageScope !== 'guest') {
        writeStorageValue(sessionKey, existing);
      }
      if (existing) return existing;
      const nextId = window.crypto && typeof window.crypto.randomUUID === 'function'
        ? window.crypto.randomUUID()
        : createId();
      writeStorageValue(sessionKey, nextId);
      return nextId;
    } catch (error) {
      return createId();
    }
  }

  function persist() {
    try {
      if (!shouldPersistChatHistory()) {
        localStorage.removeItem(scopedStorageKey(STORAGE_KEY));
        localStorage.removeItem(scopedStorageKey(JAH_AI_CHATS_KEY));
        writeStorageValue(scopedStorageKey(ACTIVE_CHAT_KEY), activeChatId);
        writeStorageValue(scopedStorageKey(JAH_AI_CURRENT_CHAT_KEY), activeChatId);
        writeStorageValue(JAH_AI_CURRENT_CHAT_KEY, activeChatId);
        return;
      }
      const serializedChats = JSON.stringify(chats);
      writeStorageValue(scopedStorageKey(STORAGE_KEY), serializedChats);
      writeStorageValue(scopedStorageKey(JAH_AI_CHATS_KEY), serializedChats);
      writeStorageValue(scopedStorageKey(ACTIVE_CHAT_KEY), activeChatId);
      writeStorageValue(scopedStorageKey(JAH_AI_CURRENT_CHAT_KEY), activeChatId);
      mirrorChatStorage();
    } catch (error) {
      setBrainStatus('error', 'No se pudo guardar historial');
    }
  }

  function persistActiveChat() {
    try {
      writeStorageValue(scopedStorageKey(ACTIVE_CHAT_KEY), activeChatId);
      writeStorageValue(scopedStorageKey(JAH_AI_CURRENT_CHAT_KEY), activeChatId);
      writeStorageValue(JAH_AI_CURRENT_CHAT_KEY, activeChatId);
    } catch (error) {
      return false;
    }
    return true;
  }

  function getAuthContext() {
    if (!window.JAHAuth || typeof window.JAHAuth.getContext !== 'function') {
      return { loggedIn: false, user: null, preferences: {} };
    }
    return window.JAHAuth.getContext();
  }

  function getAuthPreferences() {
    const context = getAuthContext();
    return context.preferences || {};
  }

  function shouldPersistChatHistory() {
    const preferences = getAuthPreferences();
    return preferences.chat_history_enabled !== false;
  }

  function initializeChatState(reason = 'initial') {
    const nextScope = getAuthStorageScope();
    if (historyLoaded && nextScope === activeStorageScope) {
      flowLog('history-skip', { reason, nextScope });
      return;
    }

    activeStorageScope = nextScope;
    chats = loadChats();
    activeChatId = loadActiveChatId();
    currentSessionId = loadOrCreateSessionId();
    spaces = loadLocalCollection(JAH_AI_SPACES_KEY);
    projects = loadLocalCollection(JAH_AI_PROJECTS_KEY);
    assistantSettings = loadAssistantSettings();
    activeSpaceId = assistantSettings.active_space_id || '';
    activeProjectId = assistantSettings.active_project_id || '';

    if (!chats.length) {
      const initialChat = createChat();
      chats = [initialChat];
      activeChatId = initialChat.id;
      currentSessionId = ensureChatSessionId(initialChat);
      persist();
    }

    if (!chats.some(chat => chat.id === activeChatId)) {
      activeChatId = chats[0].id;
      persistActiveChat();
    }

    currentSessionId = ensureChatSessionId(getActiveChat());
    writeStorageValue(scopedStorageKey(SESSION_KEY), currentSessionId);
    sortChats();
    historyLoaded = true;
    flowLog('history-loaded', {
      reason,
      chatCount: chats.length,
      activeChatId
    });
  }

  function completeAppHydration(reason = 'auth-ready') {
    authChecked = true;
    initializeChatState(reason);
    appInitialized = true;
    isHydrating = false;
    renderChat();
    refreshAdminTechnicalState();
    flowLog('app-ready', { reason });
  }

  function waitForAuthBeforeRender() {
    const authApi = window.JAHAuth;
    if (!authApi || typeof authApi.isReady !== 'function') {
      completeAppHydration('auth-api-unavailable');
      return;
    }
    if (authApi.isReady()) {
      completeAppHydration('auth-already-ready');
      return;
    }
    window.addEventListener('jah-auth-ready', () => {
      completeAppHydration('auth-ready-event');
    }, { once: true });
  }

  function syncAssistantPreferences(patch) {
    if (!window.JAHAuth || typeof window.JAHAuth.savePreferences !== 'function') return;
    window.JAHAuth.savePreferences(patch).catch(() => {
      setBrainStatus('offline', 'Preferencias guardadas localmente');
    });
  }

  function getActiveChat() {
    return chats.find(chat => chat.id === activeChatId) || chats[0];
  }

  function activateChat(chatId, options = {}) {
    const nextChat = chats.find(chat => chat.id === chatId);
    if (!nextChat) return false;
    activeChatId = nextChat.id;
    currentSessionId = ensureChatSessionId(nextChat);
    writeStorageValue(scopedStorageKey(SESSION_KEY), currentSessionId);
    persistActiveChat();
    if (options.persist !== false) persist();
    if (options.render !== false && appInitialized) renderChat();
    return true;
  }

  function setBrainStatus(state, text) {
    if (!brainStatus || !brainStatusText) return;
    brainStatus.dataset.state = state;
    brainStatusText.textContent = text;
  }

  function tutorConnectionStateLabel(status = tutorConnectionStatus) {
    const normalized = String(status || 'UNKNOWN').toUpperCase();
    if (normalized === 'CONNECTED') return 'Conectado';
    if (normalized === 'CHECKING') return 'Comprobando conexion';
    if (normalized === 'RECOVERING') return 'Recuperando conexion';
    if (normalized === 'BACKEND_UNAVAILABLE') return 'Backend tutor_ia no disponible';
    if (normalized === 'DISCONNECTED') return 'Backend tutor_ia no disponible';
    if (normalized === 'DEGRADED') return 'Backend activo parcialmente';
    return 'Sin verificar';
  }

  function tutorConnectionUiState(status = tutorConnectionStatus) {
    const normalized = String(status || 'UNKNOWN').toUpperCase();
    if (!tutorIAEnabled) return 'offline';
    if (normalized === 'CONNECTED') return 'ready';
    if (normalized === 'CHECKING' || normalized === 'RECOVERING' || normalized === 'UNKNOWN') return 'checking';
    if (normalized === 'DEGRADED') return 'warning';
    return 'error';
  }

  function deriveTutorStatusFromHealth(data = {}) {
    const explicit = String(data.tutor_ia_status || data.tutor_status || '').toUpperCase();
    if (explicit) return explicit;
    const fragments = Number(data.fragments || data.brain?.fragments || 0);
    const bridgeOk = Boolean(data.ok || data.success || data.status === 'ok');
    if (!bridgeOk) return 'BACKEND_UNAVAILABLE';
    if (fragments > 0 || data.tutor_ia_connected === true) return 'CONNECTED';
    if (data.brain_error) return 'DEGRADED';
    return 'DEGRADED';
  }

  function updateTutorButtonState() {
    if (!tutorIABtn) return;
    tutorIABtn.classList.toggle('is-active', tutorIAEnabled);
    tutorIABtn.setAttribute('aria-pressed', String(tutorIAEnabled));
    tutorIABtn.dataset.preference = tutorIAEnabled ? 'enabled' : 'disabled';
    tutorIABtn.dataset.connection = tutorConnectionStatus;
    tutorIABtn.title = tutorIAEnabled
      ? `Pensamiento profundo: Activado · ${tutorConnectionLabel}`
      : 'Pensamiento profundo: Desactivado';
  }

  function renderTutorTechnicalStatus() {
    updateTutorButtonState();
    if (!tutorIAEnabled) {
      setBrainStatus('offline', 'Pensamiento profundo: Desactivado');
      return;
    }
    setBrainStatus(
      tutorConnectionUiState(),
      `Pensamiento profundo: Activado · ${tutorConnectionLabel}`
    );
  }

  function setTutorConnectionStatus(status, label = '') {
    tutorConnectionStatus = String(status || 'UNKNOWN').toUpperCase();
    tutorConnectionLabel = label || tutorConnectionStateLabel(tutorConnectionStatus);
    renderTutorTechnicalStatus();
  }

  function isAdminUser() {
    const authContext = getAuthContext();
    return Boolean(
      authContext.isAdmin
      || authContext.user?.is_admin === true
      || authContext.user?.isAdmin === true
    );
  }

  function setAdminTechnicalVisibility(visible) {
    adminSystemStatusVisible = Boolean(visible);
    adminOnlyElements.forEach(element => {
      element.hidden = !adminSystemStatusVisible;
      if (element === quickContextCard) {
        element.setAttribute('aria-hidden', String(!adminSystemStatusVisible));
      }
    });
    renderTutorTechnicalStatus();
  }

  function refreshAdminTechnicalState() {
    const visible = isAdminUser();
    setAdminTechnicalVisibility(visible);
    if (tutorIAEnabled) detectTutorBrain();
  }

  async function fetchWithTimeout(url, options = {}, timeoutMs = 12000) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...options, signal: controller.signal });
    } finally {
      window.clearTimeout(timeout);
    }
  }

  async function detectTutorBrain() {
    if (!tutorIAEnabled) {
      setTutorConnectionStatus('UNKNOWN', 'Desactivado');
      return;
    }

    const bridgeUrl = getBridgeUrl();
    const endpointCandidates = getEndpointCandidates();
    if (!bridgeUrl) {
      setTutorConnectionStatus('BACKEND_UNAVAILABLE', 'URL del backend no configurada');
      return;
    }
    if (!endpointCandidates.length) {
      setTutorConnectionStatus('BACKEND_UNAVAILABLE', 'Endpoint de chat no configurado');
      return;
    }

    setTutorConnectionStatus('CHECKING', 'Comprobando conexion');

    try {
      const response = await fetchWithTimeout(ragHealthUrl(), { method: 'GET' }, 5000);
      if (!response.ok) {
        setTutorConnectionStatus('BACKEND_UNAVAILABLE', 'El backend tutor_ia no está disponible. Revisa Railway o la URL del servicio.');
        return;
      }

      const data = await response.json();
      activeTutorEndpoint = endpointCandidates[0] || getChatEndpoint();
      let tutorStatus = deriveTutorStatusFromHealth(data);
      let label = tutorConnectionStateLabel(tutorStatus);

      const authHeaders = window.JAHAuth && typeof window.JAHAuth.getAuthHeaders === 'function'
        ? window.JAHAuth.getAuthHeaders()
        : {};
      if (adminSystemStatusVisible && authHeaders.Authorization) {
        try {
          const adminResponse = await fetchWithTimeout(adminStatusUrl(), {
            method: 'GET',
            headers: authHeaders
          }, 5000);
          if (adminResponse.status === 401 || adminResponse.status === 403) {
            setAdminTechnicalVisibility(false);
            return;
          }
          if (adminResponse.ok) {
            const adminData = await adminResponse.json();
            tutorStatus = String(adminData.tutor_ia_status || adminData.tutor_status || tutorStatus).toUpperCase();
            label = tutorConnectionStateLabel(tutorStatus);
          }
        } catch (error) {
          // Mantener el resultado del health publico.
        }
      }

      setTutorConnectionStatus(tutorStatus, label);
    } catch (error) {
      setTutorConnectionStatus('BACKEND_UNAVAILABLE', 'El backend tutor_ia no está disponible. Revisa Railway o la URL del servicio.');
    }
  }

  function buildChatFormData(question, chatId, source = 'typed_chat') {
    const authContext = getAuthContext();
    const preferences = authContext.preferences || {};
    const formData = new FormData();
    formData.append('message', question);
    formData.append('question', question);
    formData.append('mode', DEFAULT_MODE);
    formData.append('tutorIA', String(tutorIAEnabled));
    formData.append('smartSearch', String(smartSearchEnabled));
    formData.append('session_id', chatId);
    formData.append('chat_id', chatId);
    formData.append('client_context_summary', buildClientContextSummary(getActiveChat()));
    formData.append('client', 'abraham-programming-assistant');
    formData.append('source', source);
    formData.append('input_source', source);
    if (authContext.user) {
      formData.append('user_id', String(authContext.user.id || ''));
      formData.append('user_email', authContext.user.email || '');
      formData.append('user_name', authContext.user.name || '');
    }
    if (Object.keys(preferences).length) {
      formData.append('user_preferences', JSON.stringify(preferences));
      formData.append('response_style', preferences.response_style || '');
      formData.append('assistant_preference', preferences.assistant_preference || '');
      formData.append('visible_name', preferences.visible_name || '');
      formData.append('direct_answers', String(Boolean(preferences.direct_answers)));
      formData.append('chat_history_enabled', String(preferences.chat_history_enabled !== false));
    }
    formData.append('response_profile', 'web_fast');
    formData.append('local_first', String(isLocalBridgeMode()));
    formData.append('fast_mode', String(!deepThinkingEnabled));
    formData.append('deep_thinking', String(deepThinkingEnabled));
    formData.append('bridge_api', 'true');
    formData.append('bridge_api_url', getBridgeUrl());
    formData.append('anthropic', 'true');
    if (BRAIN_ROOT) {
      formData.append('brain_root', BRAIN_ROOT);
    }
    formData.append('include_obsidian', String(tutorIAEnabled));
    formData.append('agency_enabled', String(tutorIAEnabled));
    formData.append('jarvis_profile', 'unified');
    formData.append('k', '4');
    formData.append('top_k', '1');
    formData.append('obsidian_top_k', '1');
    formData.append('show_sources', 'false');
    if (PROJECT_PATH) {
      formData.append('project_path', PROJECT_PATH);
      formData.append('workspace_path', PROJECT_PATH);
    }
    selectedFiles.forEach(file => formData.append('files', file, file.name));
    return formData;
  }

  function compactForContext(text, maxChars = 360) {
    const clean = String(text || '').replace(/\s+/g, ' ').trim();
    return clean.length > maxChars ? `${clean.slice(0, maxChars - 1).trim()}...` : clean;
  }

  function buildClientContextSummary(chat) {
    if (!chat || !Array.isArray(chat.messages) || !chat.messages.length) return '';
    const completedMessages = chat.messages
      .filter(message => message && !message.loading && message.content)
      .slice(-CLIENT_CONTEXT_TURNS * 2);
    const lines = completedMessages.map(message => {
      const role = message.role === 'user' ? 'Usuario' : 'JAH AI';
      return `${role}: ${compactForContext(message.content, message.role === 'user' ? 260 : 420)}`;
    });
    return compactForContext(lines.join('\n'), CLIENT_CONTEXT_MAX_CHARS);
  }

  async function verifyBackendHealth() {
    if (!getBridgeUrl()) return false;
    try {
      const response = await fetchWithTimeout(ragHealthUrl(), { method: 'GET' }, 4500);
      if (!response.ok) return false;
      const data = await response.json();
      return Boolean(data.ok || data.success);
    } catch (error) {
      return false;
    }
  }

  function backendConnectionError() {
    const target = getBridgeUrl() || 'API_BASE_URL';
    const error = new Error(`El backend tutor_ia no está disponible. Revisa Railway o la URL del servicio: ${target}.`);
    error.code = 'BACKEND_CONNECTION';
    return error;
  }

  function chatLoadingText() {
    if (smartSearchEnabled) return 'Buscando información actualizada...';
    if (tutorIAEnabled || deepThinkingEnabled) return 'Consultando cerebro tutor_ia...';
    return 'Pensando...';
  }

  function buildChatPayload(question, chatId, source = 'typed_chat') {
    const authContext = getAuthContext();
    const preferences = authContext.preferences || {};
    const chat = getActiveChat();
    return {
      message: question,
      question,
      mode: DEFAULT_MODE,
      use_rag: Boolean(tutorIAEnabled),
      use_web: Boolean(smartSearchEnabled),
      smartSearch: Boolean(smartSearchEnabled),
      smart_search: Boolean(smartSearchEnabled),
      deep_thinking: Boolean(tutorIAEnabled || deepThinkingEnabled),
      use_jarvis: source === 'jarvis_voice',
      session_id: currentSessionId || chatId,
      chat_id: chatId,
      client: 'abraham-programming-assistant',
      source,
      input_source: source,
      response_profile: tutorIAEnabled || deepThinkingEnabled ? 'balanced' : 'web_fast',
      local_first: isLocalBridgeMode(),
      fast_mode: !(tutorIAEnabled || deepThinkingEnabled),
      bridge_api: true,
      bridge_api_url: getBridgeUrl(),
      anthropic: true,
      brain_root: BRAIN_ROOT,
      project_path: PROJECT_PATH,
      workspace_path: PROJECT_PATH,
      user_id: authContext.user ? String(authContext.user.id || '') : '',
      user_email: authContext.user ? authContext.user.email || '' : '',
      user_name: authContext.user ? authContext.user.name || '' : '',
      user_preferences: preferences,
      client_context_summary: buildClientContextSummary(chat),
      response_style: preferences.response_style || '',
      assistant_preference: preferences.assistant_preference || '',
      visible_name: preferences.visible_name || '',
      direct_answers: Boolean(preferences.direct_answers),
      chat_history_enabled: preferences.chat_history_enabled !== false,
      show_sources: Boolean(tutorIAEnabled),
      k: 4,
      top_k: 3,
      obsidian_top_k: 2,
      include_obsidian: Boolean(tutorIAEnabled),
      agency_enabled: Boolean(tutorIAEnabled),
      jarvis_profile: 'unified'
    };
  }

  async function askBackendChat(question, chatId, source = 'typed_chat') {
    setBrainStatus('checking', chatLoadingText());
    const healthy = await verifyBackendHealth();
    if (!healthy) {
      setBrainStatus('error', 'Backend tutor_ia no disponible');
      throw backendConnectionError();
    }

    const authHeaders = window.JAHAuth && typeof window.JAHAuth.getAuthHeaders === 'function'
      ? window.JAHAuth.getAuthHeaders()
      : {};
    const response = await fetchWithTimeout(getChatEndpoint(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders
      },
      body: JSON.stringify(buildChatPayload(question, chatId, source))
    }, CHAT_TIMEOUT_MS);

    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      data = {};
    }

    if (!response.ok) {
      throw new Error(data.detail || data.error || `HTTP ${response.status}`);
    }
    if (data && data.ok === false) {
      throw new Error(data.error || data.answer || 'El cerebro tutor_ia respondió con error.');
    }

    const sourcesCount = Array.isArray(data.sources) ? data.sources.length : 0;
    setBrainStatus('ready', sourcesCount ? `Respuesta recibida - ${sourcesCount} fuentes` : 'Respuesta recibida');
    return {
      ...data,
      show_sources: sourcesCount > 0,
      brain_parts: data.brain_parts || (tutorIAEnabled ? ['tutor_ia'] : ['chat']),
      usedTutorIA: true
    };
  }

  async function askTutorBrain(question, chatId, source = 'typed_chat') {
    return askBackendChat(question, chatId, source);
  }

  function escapeHtml(text) {
    return String(text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatPlainText(text) {
    const escaped = escapeHtml(text);
    const withLinks = escaped.replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener">$1</a>'
    );
    return withLinks.replace(/\n/g, '<br>');
  }

  function renderCodeBlock(fenceContent) {
    let code = String(fenceContent || '').replace(/^\n/, '').replace(/\n$/, '');
    let language = 'codigo';
    const firstBreak = code.indexOf('\n');

    if (firstBreak > -1) {
      const firstLine = code.slice(0, firstBreak).trim();
      if (/^[a-zA-Z0-9_#+.-]{1,24}$/.test(firstLine)) {
        language = firstLine;
        code = code.slice(firstBreak + 1);
      }
    }

    return `
      <div class="code-block">
        <div class="code-header">
          <span>${escapeHtml(language)}</span>
          <button class="copy-code-btn" type="button">Copiar</button>
        </div>
        <pre><code>${escapeHtml(code)}</code></pre>
      </div>
    `;
  }

  function formatAssistantText(text) {
    const raw = String(text || '');
    const fencePattern = /```([\s\S]*?)```/g;
    let html = '';
    let lastIndex = 0;
    let match = fencePattern.exec(raw);

    while (match) {
      html += formatPlainText(raw.slice(lastIndex, match.index));
      html += renderCodeBlock(match[1]);
      lastIndex = match.index + match[0].length;
      match = fencePattern.exec(raw);
    }

    html += formatPlainText(raw.slice(lastIndex));
    return html;
  }

  function sourceTitle(source) {
    const metadata = source && source.metadata ? source.metadata : {};
    return source.title || source.file || metadata.title || metadata.source || source.url || '';
  }

  function sourceChunk(source) {
    return source.chunk || source.snippet || source.text || '';
  }

  function sourceScore(source) {
    const value = source.score ?? source.relevance ?? '';
    if (value === '' || value === null || value === undefined) return '';
    const number = Number(value);
    if (Number.isNaN(number)) return String(value);
    return number <= 1 ? number.toFixed(2) : String(number);
  }

  function renderSourceSummary(sources, showSources = false) {
    if (!showSources) return '';
    const cleanSources = (sources || [])
      .filter(Boolean)
      .slice(0, 4);
    if (!cleanSources.length) return '';

    const sourceItems = cleanSources.map(source => {
      const title = sourceTitle(source) || 'Documento';
      const chunk = sourceChunk(source);
      const score = sourceScore(source);
      const url = source.url || (source.metadata && source.metadata.url) || '';
      return `
        <li class="message-source-item">
          <strong>${escapeHtml(title)}</strong>
          ${score ? `<span>Relevancia: ${escapeHtml(score)}</span>` : ''}
          ${url ? `<span>${escapeHtml(url)}</span>` : ''}
          ${chunk ? `<p>${escapeHtml(chunk)}</p>` : ''}
        </li>
      `;
    }).join('');

    return `
      <div class="message-sources">
        <strong>Fuentes usadas:</strong>
        <ul class="message-source-list">${sourceItems}</ul>
      </div>
    `;
  }

  function fileMeta(file) {
    return {
      name: file.name,
      size: file.size,
      type: file.type || 'archivo'
    };
  }

  function renderUploadedFileSummary(files) {
    if (!Array.isArray(files) || !files.length) return '';
    const names = files
      .map(file => file && file.name ? file.name : '')
      .filter(Boolean)
      .slice(0, 5);
    if (!names.length) return '';
    return `<div class="message-sources"><strong>Adjuntos:</strong> ${names.map(escapeHtml).join(' - ')}</div>`;
  }

  function titleFromQuestion(question) {
    const clean = String(question || '').replace(/\s+/g, ' ').trim();
    if (!clean) return 'Nuevo chat';
    return clean.length > 42 ? `${clean.slice(0, 41).trim()}...` : clean;
  }

  function formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat('es-NI', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  }

  function addMessageToChat(chatId, message) {
    const chat = chats.find(item => item.id === chatId);
    if (!chat) return;
    chat.messages.push({
      id: createId(),
      createdAt: nowIso(),
      ...message
    });
    chat.updatedAt = nowIso();
    if (chat.title === 'Nuevo chat' && message.role === 'user') {
      chat.title = titleFromQuestion(message.content);
    }
    sortChats();
    persist();
  }

  function updateMessageInChat(chatId, messageId, patch) {
    const chat = chats.find(item => item.id === chatId);
    if (!chat) return;
    const message = chat.messages.find(item => item.id === messageId);
    if (!message) return;
    Object.assign(message, patch);
    chat.updatedAt = nowIso();
    sortChats();
    persist();
  }

  function sortChats() {
    chats.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
  }

  function renderChat() {
    if (isHydrating || !historyLoaded) {
      flowLog('render-deferred');
      return;
    }
    const chat = getActiveChat();
    if (!chat) return;

    activeChatLabel.textContent = chat.title || 'Nuevo chat';
    coachMessages.innerHTML = '';
    chatMain.classList.toggle('is-empty', !chat.messages.length);

    if (!chat.messages.length) {
      coachMessages.appendChild(emptyChatState);
    } else {
      chat.messages.forEach(message => {
        coachMessages.appendChild(createMessageElement(message));
      });
    }

    coachMessages.scrollTop = coachMessages.scrollHeight;
    renderHistory();
  }

  function createMessageElement(message) {
    const row = document.createElement('div');
    row.className = `message-row ${message.role === 'user' ? 'user' : 'assistant'}`;
    row.dataset.messageId = message.id;

    const bubble = document.createElement('div');
    bubble.className = `message-bubble${message.loading ? ' loading' : ''}`;
    bubble.innerHTML = [
      formatAssistantText(message.content),
      renderUploadedFileSummary(message.uploadedFiles),
      renderSourceSummary(message.sources, message.showSources)
    ].join('');
    row.appendChild(bubble);
    return row;
  }

  function updateRenderedMessage(messageId, content, options = {}) {
    const row = coachMessages.querySelector(`[data-message-id="${messageId}"]`);
    if (!row) return;
    const bubble = row.querySelector('.message-bubble');
    if (!bubble) return;
    bubble.classList.toggle('loading', Boolean(options.loading));
    bubble.innerHTML = [
      formatAssistantText(content),
      renderUploadedFileSummary(options.uploadedFiles),
      renderSourceSummary(options.sources, options.showSources)
    ].join('');
    coachMessages.scrollTop = coachMessages.scrollHeight;
  }

  function setActiveSidebarAction(action) {
    const panelActions = new Set([
      'search',
      'system-status',
      'history',
      'discover',
      'spaces',
      'projects',
      'security',
      'odysseus',
      'more'
    ]);
    sidebarActionButtons.forEach(button => {
      const isActive = panelActions.has(action) && button.dataset.action === action;
      button.classList.toggle('is-active', isActive);
      if (isActive) {
        button.setAttribute('aria-current', 'page');
      } else {
        button.removeAttribute('aria-current');
      }
    });
  }

  function ensureButtonAccessibility(root = document) {
    const buttons = root.matches && root.matches('button')
      ? [root, ...root.querySelectorAll('button')]
      : [...root.querySelectorAll('button')];
    buttons.forEach(button => {
      const label = (button.getAttribute('aria-label') || button.textContent || button.title || '').trim().replace(/\s+/g, ' ');
      if (label && !button.getAttribute('aria-label')) button.setAttribute('aria-label', label);
      if (label && !button.getAttribute('title')) button.setAttribute('title', label);
    });
  }

  function renderHistory() {
    const query = activeHistoryQuery.trim().toLowerCase();
    const filtered = chats.filter(chat => {
      const haystack = [
        chat.title,
        ...chat.messages.map(message => message.content)
      ].join(' ').toLowerCase();
      return !query || haystack.includes(query);
    });

    chatHistoryList.innerHTML = '';
    if (!filtered.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-history';
      empty.textContent = query ? 'No encontre chats con esa busqueda.' : 'Tus chats apareceran aqui.';
      chatHistoryList.appendChild(empty);
      return;
    }

    filtered.forEach(chat => {
      const item = document.createElement('button');
      item.className = `history-item${chat.id === activeChatId ? ' active' : ''}`;
      item.type = 'button';
      item.innerHTML = `
        <span class="history-copy">
          <span class="history-title">${escapeHtml(chat.title || 'Nuevo chat')}</span>
          <span class="history-date">${escapeHtml(formatDate(chat.updatedAt))}</span>
        </span>
        <span class="delete-chat-btn" role="button" aria-label="Eliminar chat">
          <i class="fas fa-trash" aria-hidden="true"></i>
        </span>
      `;

      item.addEventListener('click', event => {
        if (event.target.closest('.delete-chat-btn')) {
          deleteChat(chat.id);
          return;
        }
        activateChat(chat.id);
        closeSidebar();
      });

      chatHistoryList.appendChild(item);
    });
  }

  function startNewChat() {
    const chat = createChat();
    chats.unshift(chat);
    activeChatId = chat.id;
    currentSessionId = ensureChatSessionId(chat);
    writeStorageValue(scopedStorageKey(SESSION_KEY), currentSessionId);
    persist();
    renderChat();
    closeSidebar();
    closePanel();
    coachInput.focus();
  }

  function deleteChat(chatId, options = {}) {
    if (options.confirmDelete !== false && !window.confirm('Eliminar esta conversacion del historial local?')) {
      return false;
    }
    chats = chats.filter(chat => chat.id !== chatId);
    if (!chats.length) {
      chats = [createChat()];
    }
    if (!chats.some(chat => chat.id === activeChatId)) {
      activeChatId = chats[0].id;
    }
    currentSessionId = ensureChatSessionId(getActiveChat());
    persist();
    renderChat();
    if (activePanelType === 'history') renderHistoryPanel();
    return true;
  }

  function clearHistory() {
    if (!window.confirm('Limpiar todo el historial local? Esta accion no borra datos del backend.')) {
      return false;
    }
    chats = [createChat()];
    activeChatId = chats[0].id;
    currentSessionId = ensureChatSessionId(chats[0]);
    persist();
    renderChat();
    coachInput.focus();
    if (activePanelType === 'history') renderHistoryPanel();
    return true;
  }

  function clearCurrentChat() {
    const chat = getActiveChat();
    if (!chat) return false;
    if (!window.confirm('Limpiar solo la conversacion actual? El historial anterior se conserva.')) {
      return false;
    }
    chat.title = 'Nuevo chat';
    chat.messages = [];
    chat.updatedAt = nowIso();
    persist();
    renderChat();
    openPanel('more', { notice: 'Chat actual limpiado. El historial anterior se conserva.' });
    coachInput.focus();
    return true;
  }

  function getAuthHeaders() {
    return window.JAHAuth && typeof window.JAHAuth.getAuthHeaders === 'function'
      ? window.JAHAuth.getAuthHeaders()
      : {};
  }

  async function apiFetchJson(path, options = {}, timeoutMs = 6500) {
    const bridgeUrl = getBridgeUrl();
    if (!bridgeUrl) {
      const error = new Error('API_BASE_URL no configurada');
      error.code = 'API_BASE_URL_MISSING';
      throw error;
    }
    const headers = {
      ...(options.headers || {}),
      ...getAuthHeaders()
    };
    const response = await fetchWithTimeout(`${bridgeUrl}${path}`, {
      ...options,
      headers
    }, timeoutMs);
    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      data = {};
    }
    return { response, data };
  }

  function panelMeta(type) {
    const metas = {
      search: ['Buscar', 'Conversaciones, historial, proyectos, espacios y contenido del asistente.'],
      'system-status': ['Estado del sistema', 'Consulta real a /api/health del backend configurado.'],
      history: ['Historial', 'Conversaciones anteriores con backend cuando este disponible y localStorage como respaldo.'],
      discover: ['Descubrir', 'Prompts sugeridos, capacidades y accesos rapidos.'],
      spaces: ['Espacios', 'Areas de trabajo locales listas para sincronizar con Supabase o PostgreSQL.'],
      projects: ['Proyectos', 'Organizacion de proyectos con persistencia local temporal.'],
      security: ['Seguridad', 'Autenticacion, backend, Supabase Auth y base de datos sin exponer tokens.'],
      odysseus: ['Herramientas avanzadas', 'Archivos, analisis, codigo, debug y plan integrados en JAH AI.'],
      more: ['Mas opciones', 'Configuracion, exportacion, ayuda y acciones de mantenimiento.'],
      settings: ['Configuracion', 'Preferencias locales del asistente.'],
      help: ['Ayuda', 'Acciones disponibles del asistente.'],
      about: ['Acerca del asistente', 'Version web del asistente de programacion JAH AI.']
    };
    const [title, description] = metas[type] || ['Panel', ''];
    return { title, description };
  }

  function openPanel(type, options = {}) {
    if (!assistantPanelOverlay || !assistantPanelContent) return;
    activePanelType = type;
    const meta = panelMeta(type);
    assistantPanelKicker.textContent = 'JAH AI';
    assistantPanelTitle.textContent = meta.title;
    assistantPanelDescription.textContent = meta.description;
    assistantPanelOverlay.hidden = false;
    document.body.classList.add('assistant-panel-open');
    setActiveSidebarAction(type);

    if (['system-status', 'security', 'history', 'spaces', 'projects', 'odysseus'].includes(type)) {
      assistantPanelContent.innerHTML = renderPanelLoading('Consultando backend...');
    }

    if (type === 'search') renderSearchPanel(options.query || activeHistoryQuery);
    if (type === 'history') renderHistoryPanel();
    if (type === 'discover') renderDiscoverPanel();
    if (type === 'spaces') renderSpacesPanel(options.notice || '');
    if (type === 'projects') renderProjectsPanel(options.notice || '');
    if (type === 'odysseus') renderOdysseusPanel(options);
    if (type === 'more') renderMorePanel(options.notice || '');
    if (type === 'settings') renderSettingsPanel(options.notice || '');
    if (type === 'help') renderHelpPanel();
    if (type === 'about') renderAboutPanel();
    if (type === 'system-status') renderSystemStatusPanel(true);
    if (type === 'security') renderSecurityPanel(true);
  }

  function closePanel() {
    if (!assistantPanelOverlay) return;
    assistantPanelOverlay.hidden = true;
    document.body.classList.remove('assistant-panel-open');
    activePanelType = '';
    setActiveSidebarAction('');
  }

  function renderPanelLoading(text) {
    return `<div class="assistant-panel-empty"><i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i><span>${escapeHtml(text)}</span></div>`;
  }

  function renderPanelNotice(text, tone = 'info') {
    if (!text) return '';
    return `<div class="assistant-panel-notice ${escapeHtml(tone)}">${escapeHtml(text)}</div>`;
  }

  function renderPanelEmpty(text) {
    return `<div class="assistant-panel-empty">${escapeHtml(text)}</div>`;
  }

  function renderStatusBadge(ok, goodText, badText, pendingText = '') {
    if (ok === 'warn') {
      return `<span class="assistant-status-badge warn">${escapeHtml(badText)}</span>`;
    }
    if (ok === null || ok === undefined) {
      return `<span class="assistant-status-badge pending">${escapeHtml(pendingText || 'Sin verificar')}</span>`;
    }
    return ok
      ? `<span class="assistant-status-badge ok">${escapeHtml(goodText)}</span>`
      : `<span class="assistant-status-badge bad">${escapeHtml(badText)}</span>`;
  }

  function normalizeSystemHealth(data = {}, response = null) {
    const tutorStatus = deriveTutorStatusFromHealth(data);
    const tutorLabel = String(data.tutor_ia || data.tutor || '').toLowerCase();
    const backendActive = Boolean(response && response.ok && data.ok !== false);
    const supabaseConfigured = Boolean(
      data.supabase_auth_configured
      || data.supabase_configured
      || data.supabase_enabled
      || data.supabase?.configured
      || data.auth?.supabase_configured
    );
    const databaseConnected = Boolean(
      data.database_connected
      || data.postgres_connected
      || data.database?.connected
      || data.postgres?.connected
      || String(data.database || '').toLowerCase() === 'connected'
    );
    const databaseConfigured = Boolean(
      databaseConnected
      || data.postgres_configured
      || data.database_configured
      || data.database?.configured
      || data.postgres?.configured
    );
    const odysseusStatus = data.odysseus_status && typeof data.odysseus_status === 'object' ? data.odysseus_status : {};
    const llmStatus = data.llm && typeof data.llm === 'object' ? data.llm : odysseusStatus.llm || {};
    return {
      ok: backendActive,
      backendActive,
      tutorReady: tutorStatus === 'CONNECTED' || data.tutor_ia_connected === true || tutorLabel === 'ready',
      tutorStatus,
      odysseusReady: data.odysseus === 'ready' || odysseusStatus.odysseus === 'ready',
      odysseusSafeMode: odysseusStatus.safe_mode !== false,
      llmConfigured: Boolean(llmStatus.configured),
      llmProvider: llmStatus.provider || 'none',
      supabaseConfigured,
      databaseConnected,
      databaseConfigured,
      httpStatus: response ? response.status : 0,
      apiBaseUrl: getBridgeUrl() || 'API_BASE_URL no configurada',
      raw: data
    };
  }

  async function loadSystemStatus() {
    const bridgeUrl = getBridgeUrl();
    if (!bridgeUrl) {
      lastSystemHealth = {
        ok: false,
        backendActive: false,
        tutorReady: false,
        tutorStatus: 'BACKEND_UNAVAILABLE',
        supabaseConfigured: false,
        databaseConnected: false,
        databaseConfigured: false,
        httpStatus: 0,
        apiBaseUrl: 'API_BASE_URL no configurada',
        errorType: 'config',
        message: 'API_BASE_URL no configurada'
      };
      setBrainStatus('error', 'Backend no configurado');
      return lastSystemHealth;
    }

    setBrainStatus('checking', 'Consultando /api/health...');
    try {
      const response = await fetchWithTimeout(`${bridgeUrl}/api/health`, {
        method: 'GET',
        headers: getAuthHeaders()
      }, 6500);
      const data = await response.json().catch(() => ({}));
      lastSystemHealth = normalizeSystemHealth(data, response);
      if (lastSystemHealth.backendActive) {
        setTutorConnectionStatus(lastSystemHealth.tutorStatus, tutorConnectionStateLabel(lastSystemHealth.tutorStatus));
      } else {
        setBrainStatus('error', 'Backend no disponible');
      }
      return lastSystemHealth;
    } catch (error) {
      const isCorsOrConnection = error instanceof TypeError || String(error.message || '').includes('Failed to fetch');
      lastSystemHealth = {
        ok: false,
        backendActive: false,
        tutorReady: false,
        tutorStatus: 'BACKEND_UNAVAILABLE',
        supabaseConfigured: false,
        databaseConnected: false,
        databaseConfigured: false,
        httpStatus: 0,
        apiBaseUrl: bridgeUrl,
        errorType: isCorsOrConnection ? 'cors_or_connection' : 'connection',
        message: isCorsOrConnection ? 'Error CORS o conexion rechazada' : (error.message || 'Error de conexion')
      };
      setBrainStatus('error', 'Backend no disponible');
      return lastSystemHealth;
    }
  }

  function renderSystemStatus(status) {
    const raw = status.raw || {};
    return `
      <div class="assistant-status-grid">
        <div class="assistant-status-item">
          <span>Backend</span>
          ${renderStatusBadge(status.backendActive, 'Activo', 'No disponible')}
        </div>
        <div class="assistant-status-item">
          <span>tutor_ia</span>
          ${renderStatusBadge(status.tutorReady ? true : status.backendActive ? 'warn' : false, 'Listo', tutorConnectionStateLabel(status.tutorStatus))}
        </div>
        <div class="assistant-status-item">
          <span>Motor avanzado</span>
          ${renderStatusBadge(status.odysseusReady ? true : status.backendActive ? 'warn' : false, 'Listo', 'No disponible')}
        </div>
        <div class="assistant-status-item">
          <span>LLM</span>
          ${renderStatusBadge(status.llmConfigured ? true : 'warn', status.llmProvider || 'Configurado', 'No configurado')}
        </div>
        <div class="assistant-status-item">
          <span>Supabase Auth</span>
          ${renderStatusBadge(status.supabaseConfigured ? true : 'warn', 'Configurado', 'No configurado')}
        </div>
        <div class="assistant-status-item">
          <span>Base de datos</span>
          ${renderStatusBadge(status.databaseConnected ? true : 'warn', 'Conectada', status.databaseConfigured ? 'Configurada sin conexion' : 'No configurada')}
        </div>
      </div>
      <div class="assistant-panel-card">
        <strong>Endpoint consultado</strong>
        <p>${escapeHtml(status.apiBaseUrl)}/api/health</p>
        <p>HTTP: ${escapeHtml(String(status.httpStatus || 'sin respuesta'))}</p>
        ${status.message ? `<p>${escapeHtml(status.message)}</p>` : ''}
      </div>
      <div class="assistant-panel-card">
        <strong>Detalle no sensible</strong>
        <p>Estado tutor_ia: ${escapeHtml(status.tutorStatus || 'Sin verificar')}</p>
        <p>Historial backend: ${raw.history_path ? 'Configurado' : 'Sin dato publico'}</p>
      </div>
    `;
  }

  async function renderSystemStatusPanel(refresh = false) {
    const status = refresh || !lastSystemHealth ? await loadSystemStatus() : lastSystemHealth;
    if (activePanelType !== 'system-status') return;
    assistantPanelContent.innerHTML = `
      ${renderSystemStatus(status)}
      <div class="assistant-panel-actions">
        <button type="button" class="assistant-panel-btn primary" data-panel-action="reload-status">
          <i class="fas fa-rotate" aria-hidden="true"></i><span>Recargar estado</span>
        </button>
      </div>
    `;
  }

  async function loadChatHistory() {
    const result = {
      source: 'localStorage',
      chats,
      backendChats: [],
      notice: 'Usando historial local temporal.'
    };

    if (!getBridgeUrl()) {
      result.notice = 'Backend no configurado. Usando localStorage.';
      return result;
    }

    try {
      const listResult = await apiFetchJson('/api/history', { method: 'GET' }, 4500);
      if (listResult.response.ok) {
        const backendList = Array.isArray(listResult.data)
          ? listResult.data
          : listResult.data.chats || listResult.data.history || [];
        result.backendChats = backendList.map(normalizeBackendHistoryChat).filter(Boolean);
        result.source = 'backend';
        result.notice = result.backendChats.length
          ? 'Historial cargado desde backend.'
          : 'Backend disponible, pero no devolvio conversaciones.';
        return result;
      }
      console.info('[JAH AI] GET /api/history no disponible; usando fallback localStorage.');
    } catch (error) {
      console.info('[JAH AI] No se pudo cargar GET /api/history; usando localStorage.', error.message || error);
    }

    if (currentSessionId) {
      try {
        const sessionResult = await apiFetchJson(`/api/history/${encodeURIComponent(currentSessionId)}`, { method: 'GET' }, 4500);
        if (sessionResult.response.ok) {
          const backendChat = normalizeBackendHistoryChat(sessionResult.data);
          result.backendChats = backendChat ? [backendChat] : [];
          result.notice = result.backendChats.length
            ? 'Backend disponible para la sesion actual; la lista completa usa localStorage.'
            : 'Backend disponible, sin historial para la sesion actual.';
          return result;
        }
      } catch (error) {
        console.info('[JAH AI] No se pudo cargar /api/history/{session_id}; usando localStorage.', error.message || error);
      }
    }

    return result;
  }

  function normalizeBackendHistoryChat(data) {
    if (!data) return null;
    const sessionId = data.session_id || data.sessionId || data.id || currentSessionId;
    const rawHistory = Array.isArray(data.history)
      ? data.history
      : Array.isArray(data.messages)
        ? data.messages
        : [];
    const messages = [];
    rawHistory.forEach(turn => {
      if (turn.role && turn.content) {
        messages.push({
          id: turn.id || createId(),
          role: turn.role,
          content: turn.content,
          createdAt: turn.created_at || turn.createdAt || nowIso()
        });
        return;
      }
      const userText = turn.user_message || turn.question || turn.input || '';
      const assistantText = turn.ai_response || turn.answer || turn.response || '';
      if (userText) {
        messages.push({ id: createId(), role: 'user', content: userText, createdAt: turn.created_at || nowIso() });
      }
      if (assistantText) {
        messages.push({ id: createId(), role: 'assistant', content: assistantText, createdAt: turn.created_at || nowIso() });
      }
    });
    return {
      id: data.id || `backend-${sessionId}`,
      sessionId,
      title: data.title || 'Historial backend actual',
      createdAt: data.created_at || nowIso(),
      updatedAt: data.updated_at || nowIso(),
      messages
    };
  }

  function renderSearchPanel(query = '') {
    activeHistoryQuery = query || '';
    const cleanQuery = activeHistoryQuery.trim().toLowerCase();
    const results = [];

    chats.forEach(chat => {
      const content = [chat.title, ...chat.messages.map(message => message.content)].join(' ');
      if (!cleanQuery || content.toLowerCase().includes(cleanQuery)) {
        results.push({
          type: 'Conversacion',
          title: chat.title || 'Nuevo chat',
          description: `${chat.messages.length} mensajes - ${formatDate(chat.updatedAt)}`,
          action: 'select-chat',
          id: chat.id
        });
      }
    });

    projects.forEach(project => {
      const content = [project.name, project.description].join(' ');
      if (!cleanQuery || content.toLowerCase().includes(cleanQuery)) {
        results.push({
          type: 'Proyecto',
          title: project.name,
          description: project.description || 'Proyecto local',
          action: 'select-project',
          id: project.id
        });
      }
    });

    spaces.forEach(space => {
      const content = [space.name, space.description].join(' ');
      if (!cleanQuery || content.toLowerCase().includes(cleanQuery)) {
        results.push({
          type: 'Espacio',
          title: space.name,
          description: space.description || 'Espacio local',
          action: 'select-space',
          id: space.id
        });
      }
    });

    readUploadedFileMeta().forEach(file => {
      const content = [file.name, file.relative_path, file.content_type].join(' ');
      if (!cleanQuery || content.toLowerCase().includes(cleanQuery)) {
        results.push({
          type: 'Archivo',
          title: file.name,
          description: `${file.relative_path} - ${fileSizeLabel(file.size)}`,
          action: 'odysseus-read-file',
          id: file.relative_path
        });
      }
    });

    DISCOVER_PROMPTS.forEach(item => {
      const content = [item.title, item.description, item.prompt].join(' ');
      if (!cleanQuery || content.toLowerCase().includes(cleanQuery)) {
        results.push({
          type: 'Prompt',
          title: item.title,
          description: item.description,
          action: 'insert-prompt',
          prompt: item.prompt
        });
      }
    });

    assistantPanelContent.innerHTML = `
      <label class="assistant-panel-search">
        <i class="fas fa-search" aria-hidden="true"></i>
        <input id="assistantPanelSearchInput" type="search" value="${escapeHtml(activeHistoryQuery)}" placeholder="Buscar conversaciones, historial, proyectos, espacios..." autocomplete="off">
      </label>
      <div class="assistant-panel-list">
        ${results.length ? results.map(renderPanelResult).join('') : renderPanelEmpty('No hay resultados para esa busqueda.')}
      </div>
    `;
    const input = document.getElementById('assistantPanelSearchInput');
    if (input) {
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
      input.addEventListener('input', event => renderSearchPanel(event.target.value));
    }
    renderHistory();
  }

  function renderPanelResult(item) {
    const attrs = [
      `data-panel-action="${escapeHtml(item.action)}"`
    ];
    if (item.id) attrs.push(`data-id="${escapeHtml(item.id)}"`);
    if (item.prompt) attrs.push(`data-prompt="${escapeHtml(item.prompt)}"`);
    return `
      <button type="button" class="assistant-panel-item" ${attrs.join(' ')}>
        <span class="assistant-panel-item-kicker">${escapeHtml(item.type)}</span>
        <strong>${escapeHtml(item.title)}</strong>
        <span>${escapeHtml(item.description || '')}</span>
      </button>
    `;
  }

  async function renderHistoryPanel() {
    const history = await loadChatHistory();
    if (activePanelType !== 'history') return;
    backendHistoryCache = history.backendChats;
    const backendItems = history.backendChats.length
      ? `
        <div class="assistant-panel-section-title">Backend</div>
        <div class="assistant-panel-list">
          ${history.backendChats.map(chat => renderPanelResult({
            type: 'Backend',
            title: chat.title,
            description: `${chat.messages.length} mensajes - sesion ${chat.sessionId || 'sin id'}`,
            action: 'restore-backend-chat',
            id: chat.id
          })).join('')}
        </div>
      `
      : '';
    assistantPanelContent.innerHTML = `
      ${renderPanelNotice(history.notice)}
      ${backendItems}
      <div class="assistant-panel-section-title">Local</div>
      <div class="assistant-panel-list">
        ${chats.length ? chats.map(chat => renderPanelResult({
          type: chat.id === activeChatId ? 'Actual' : 'Conversacion',
          title: chat.title || 'Nuevo chat',
          description: `${chat.messages.length} mensajes - ${formatDate(chat.updatedAt)}`,
          action: 'select-chat',
          id: chat.id
        })).join('') : renderPanelEmpty('No hay historial todavia.')}
      </div>
      <div class="assistant-panel-actions">
        <button type="button" class="assistant-panel-btn primary" data-panel-action="new-chat">
          <i class="fas fa-plus" aria-hidden="true"></i><span>Nuevo chat</span>
        </button>
        <button type="button" class="assistant-panel-btn danger" data-panel-action="clear-history">
          <i class="fas fa-trash" aria-hidden="true"></i><span>Limpiar historial local</span>
        </button>
      </div>
    `;
  }

  function renderDiscoverPanel() {
    assistantPanelContent.innerHTML = `
      <div class="assistant-panel-grid">
        ${DISCOVER_PROMPTS.map(item => `
          <article class="assistant-panel-card">
            <strong>${escapeHtml(item.title)}</strong>
            <p>${escapeHtml(item.description)}</p>
            <button type="button" class="assistant-panel-btn" data-panel-action="insert-prompt" data-prompt="${escapeHtml(item.prompt)}">
              <i class="fas fa-arrow-right" aria-hidden="true"></i><span>Usar prompt</span>
            </button>
          </article>
        `).join('')}
      </div>
      <div class="assistant-panel-section-title">Accesos rapidos</div>
      <div class="assistant-panel-actions">
        <button type="button" class="assistant-panel-btn" data-panel-action="open-panel" data-target-panel="system-status">
          <i class="fas fa-heart-pulse" aria-hidden="true"></i><span>Ver backend</span>
        </button>
        <button type="button" class="assistant-panel-btn" data-panel-action="open-panel" data-target-panel="projects">
          <i class="fas fa-code" aria-hidden="true"></i><span>Abrir proyectos</span>
        </button>
        <button type="button" class="assistant-panel-btn" data-panel-action="open-panel" data-target-panel="spaces">
          <i class="fas fa-grip" aria-hidden="true"></i><span>Abrir espacios</span>
        </button>
        <button type="button" class="assistant-panel-btn" data-panel-action="open-panel" data-target-panel="odysseus">
          <i class="fas fa-toolbox" aria-hidden="true"></i><span>Herramientas</span>
        </button>
      </div>
    `;
  }

  function fileSizeLabel(size) {
    const value = Number(size || 0);
    if (!value) return 'Sin tamano';
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }

  function odysseusUnavailablePanel(error = '') {
    return `
      ${renderPanelNotice(error || 'Las herramientas avanzadas no estan disponibles desde este frontend.', 'warning')}
      <div class="assistant-panel-actions">
        <button type="button" class="assistant-panel-btn primary" data-panel-action="reload-odysseus">
          <i class="fas fa-rotate" aria-hidden="true"></i><span>Reintentar</span>
        </button>
      </div>
    `;
  }

  async function loadOdysseusFiles() {
    const cached = readUploadedFileMeta();
    if (!window.odysseus || typeof window.odysseus.files_list !== 'function') {
      return { ok: false, files: cached, error: 'Motor de herramientas avanzadas no cargado.' };
    }
    const result = await window.odysseus.files_list();
    if (Array.isArray(result.files)) {
      mergeUploadedFileMeta(result.files);
    }
    return { ...result, files: Array.isArray(result.files) ? result.files : cached };
  }

  async function renderOdysseusPanel(options = {}) {
    if (activePanelType !== 'odysseus') return;
    assistantPanelContent.innerHTML = renderPanelLoading('Consultando herramientas avanzadas...');
    if (!window.odysseus || typeof window.odysseus.status !== 'function') {
      assistantPanelContent.innerHTML = odysseusUnavailablePanel('El motor de herramientas avanzadas no esta cargado.');
      return;
    }

    const [status, filesResult] = await Promise.all([
      window.odysseus.status(),
      loadOdysseusFiles()
    ]);
    if (activePanelType !== 'odysseus') return;

    const files = (filesResult.files || []).map(normalizeUploadedFileMeta).filter(Boolean);
    const llm = status.llm || {};
    const selectedPath = options.path || files[0]?.relative_path || '';
    const fileList = files.length
      ? files.slice(0, 12).map(file => `
        <article class="assistant-panel-workspace">
          <div>
            <span class="assistant-panel-item-kicker">${escapeHtml(file.content_type || 'Archivo')}</span>
            <strong>${escapeHtml(file.name)}</strong>
            <p>${escapeHtml(file.relative_path)} - ${escapeHtml(fileSizeLabel(file.size))}</p>
          </div>
          <div class="assistant-panel-actions compact">
            <button type="button" class="assistant-panel-btn" data-panel-action="odysseus-read-file" data-path="${escapeHtml(file.relative_path)}">
              <i class="fas fa-file-lines" aria-hidden="true"></i><span>Leer</span>
            </button>
            <button type="button" class="assistant-panel-btn" data-panel-action="odysseus-analyze-file" data-path="${escapeHtml(file.relative_path)}">
              <i class="fas fa-magnifying-glass-chart" aria-hidden="true"></i><span>Analizar</span>
            </button>
          </div>
        </article>
      `).join('')
      : renderPanelEmpty('No hay archivos subidos todavia.');

    assistantPanelContent.innerHTML = `
      ${renderPanelNotice(options.notice || '')}
      <div class="assistant-status-grid">
        <div class="assistant-status-item">
          <span>Motor avanzado</span>
          ${renderStatusBadge(status.odysseus === 'ready', 'Listo', status.error || 'No disponible')}
        </div>
        <div class="assistant-status-item">
          <span>Safe mode</span>
          ${renderStatusBadge(status.safe_mode !== false, 'Activo', 'Inactivo')}
        </div>
        <div class="assistant-status-item">
          <span>LLM</span>
          ${renderStatusBadge(llm.configured ? true : 'warn', llm.provider || 'Configurado', 'No configurado')}
        </div>
        <div class="assistant-status-item">
          <span>Archivos</span>
          ${renderStatusBadge(files.length ? true : 'warn', String(files.length), 'Sin archivos')}
        </div>
      </div>
      <div class="assistant-panel-actions">
        <button type="button" class="assistant-panel-btn primary" data-panel-action="odysseus-analyze-file" data-path="${escapeHtml(selectedPath)}">
          <i class="fas fa-magnifying-glass-chart" aria-hidden="true"></i><span>Analizar</span>
        </button>
        <button type="button" class="assistant-panel-btn" data-panel-action="odysseus-code-file" data-path="${escapeHtml(selectedPath)}">
          <i class="fas fa-code" aria-hidden="true"></i><span>Codigo</span>
        </button>
        <button type="button" class="assistant-panel-btn" data-panel-action="odysseus-debug-file" data-path="${escapeHtml(selectedPath)}">
          <i class="fas fa-stethoscope" aria-hidden="true"></i><span>Debug</span>
        </button>
        <button type="button" class="assistant-panel-btn" data-panel-action="odysseus-plan-file" data-path="${escapeHtml(selectedPath)}">
          <i class="fas fa-list-check" aria-hidden="true"></i><span>Plan</span>
        </button>
        <button type="button" class="assistant-panel-btn" data-panel-action="odysseus-search-files">
          <i class="fas fa-search" aria-hidden="true"></i><span>Buscar</span>
        </button>
        <button type="button" class="assistant-panel-btn" data-panel-action="reload-odysseus">
          <i class="fas fa-rotate" aria-hidden="true"></i><span>Recargar</span>
        </button>
      </div>
      <div class="assistant-panel-section-title">Archivos subidos</div>
      <div class="assistant-panel-list">${fileList}</div>
    `;
  }

  function odysseusResultText(action, result) {
    if (!result || result.ok === false) {
      return `JAH AI no pudo ejecutar ${action}. ${result?.error || result?.detail || 'Sin detalle.'}`;
    }
    const payload = result.result || result;
    const summary = payload.summary || payload.llm_result?.answer || payload.message || '';
    const findings = Array.isArray(payload.findings) && payload.findings.length
      ? `\n\nHallazgos:\n${payload.findings.map(item => `- ${item.message || item.type || item.file}`).join('\n')}`
      : '';
    const llmNote = payload.llm?.configured === false
      ? `\n\nLLM: ${payload.llm.message || 'Proveedor no configurado; se uso analisis estatico seguro.'}`
      : '';
    return `${summary || `JAH AI ejecuto ${action}.`}${findings}${llmNote}`;
  }

  async function runOdysseusFileAction(action, path = '') {
    if (!window.odysseus) return openPanel('odysseus', { notice: 'El motor de herramientas avanzadas no esta cargado.' });
    const method = {
      analyze: 'analyze',
      code: 'code',
      debug: 'debug',
      plan: 'plan'
    }[action] || 'analyze';
    const message = coachInput.value.trim() || `Ejecuta ${action} con el contexto disponible.`;
    const result = await window.odysseus[method]({
      message,
      upload_path: path || undefined,
      options: { use_llm: true }
    });
    addMessageToChat(activeChatId, {
      role: 'assistant',
      content: odysseusResultText(action, result)
    });
    renderChat();
    setBrainStatus(result.ok === false ? 'error' : 'ready', result.ok === false ? 'Herramienta fallo' : 'Herramienta lista');
    openPanel('odysseus', { notice: result.ok === false ? 'La accion fallo.' : 'Accion ejecutada.', path });
  }

  async function readOdysseusFile(path) {
    if (!path || !window.odysseus) return;
    const result = await window.odysseus.files_read(path, 12000);
    const content = result.content || result.message || result.error || '';
    addMessageToChat(activeChatId, {
      role: 'assistant',
      content: `Lectura segura de ${path}:\n\n${content.slice(0, 6000)}`
    });
    renderChat();
    closePanel();
  }

  async function searchOdysseusFiles() {
    if (!window.odysseus) return;
    const query = coachInput.value.trim();
    const result = await window.odysseus.files_search(query);
    const files = Array.isArray(result.files) ? result.files : [];
    mergeUploadedFileMeta(files);
    addMessageToChat(activeChatId, {
      role: 'assistant',
      content: files.length
        ? `Resultados de JAH AI para "${query || 'todos'}":\n${files.slice(0, 12).map(file => `- ${file.relative_path || file.path || file.name}`).join('\n')}`
        : `JAH AI no encontro archivos para "${query || 'todos'}".`
    });
    renderChat();
    openPanel('odysseus', { notice: 'Busqueda ejecutada.' });
  }

  async function loadBackendCollection(kind) {
    if (!getBridgeUrl()) {
      return { items: [], notice: 'Backend no configurado. Usando localStorage.' };
    }
    try {
      const result = await apiFetchJson(`/api/${kind}`, { method: 'GET' }, 4500);
      if (!result.response.ok) {
        console.info(`[JAH AI] GET /api/${kind} no disponible; usando localStorage temporalmente.`);
        return { items: [], notice: `Endpoint /api/${kind} no disponible. Usando localStorage temporal.` };
      }
      const items = Array.isArray(result.data) ? result.data : result.data[kind] || result.data.items || [];
      return { items: Array.isArray(items) ? items : [], notice: `Datos de ${kind} cargados desde backend.` };
    } catch (error) {
      console.info(`[JAH AI] No se pudo cargar /api/${kind}; usando localStorage.`, error.message || error);
      return { items: [], notice: `No se pudo cargar /api/${kind}. Usando localStorage temporal.` };
    }
  }

  async function saveBackendCollectionItem(kind, item) {
    if (!getBridgeUrl()) {
      console.info(`[JAH AI] API_BASE_URL no configurada; ${kind} guardado solo en localStorage.`);
      return false;
    }
    try {
      const result = await apiFetchJson(`/api/${kind}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item)
      }, 4500);
      if (!result.response.ok) {
        console.info(`[JAH AI] POST /api/${kind} no disponible; ${kind} guardado en localStorage.`);
        return false;
      }
      return true;
    } catch (error) {
      console.info(`[JAH AI] Error en POST /api/${kind}; ${kind} guardado en localStorage.`, error.message || error);
      return false;
    }
  }

  async function renderSpacesPanel(notice = '') {
    const backend = await loadBackendCollection('spaces');
    if (backend.items.length) {
      spaces = mergeCollection(spaces, backend.items.map(normalizeWorkspaceItem));
      persistSpaces();
    }
    if (activePanelType !== 'spaces') return;
    assistantPanelContent.innerHTML = `
      ${renderPanelNotice(notice || backend.notice)}
      <form class="assistant-panel-form" data-panel-form="create-space">
        <label>
          <span>Nombre del espacio</span>
          <input name="name" type="text" placeholder="Ej: Clientes, Universidad, Backend" required>
        </label>
        <label>
          <span>Descripcion</span>
          <textarea name="description" rows="2" placeholder="Para que usaras este espacio"></textarea>
        </label>
        <button type="submit" class="assistant-panel-btn primary">
          <i class="fas fa-plus" aria-hidden="true"></i><span>Crear espacio</span>
        </button>
      </form>
      <div class="assistant-panel-list">
        ${spaces.length ? spaces.map(space => renderWorkspaceItem(space, 'space')).join('') : renderPanelEmpty('No hay espacios creados.')}
      </div>
    `;
  }

  async function renderProjectsPanel(notice = '') {
    const backend = await loadBackendCollection('projects');
    if (backend.items.length) {
      projects = mergeCollection(projects, backend.items.map(normalizeWorkspaceItem));
      persistProjects();
    }
    if (activePanelType !== 'projects') return;
    assistantPanelContent.innerHTML = `
      ${renderPanelNotice(notice || backend.notice)}
      <form class="assistant-panel-form" data-panel-form="create-project">
        <label>
          <span>Nombre del proyecto</span>
          <input name="name" type="text" placeholder="Ej: Portfolio, API, App movil" required>
        </label>
        <label>
          <span>Descripcion</span>
          <textarea name="description" rows="2" placeholder="Objetivo o stack principal"></textarea>
        </label>
        <button type="submit" class="assistant-panel-btn primary">
          <i class="fas fa-plus" aria-hidden="true"></i><span>Crear proyecto</span>
        </button>
      </form>
      <div class="assistant-panel-list">
        ${projects.length ? projects.map(project => renderWorkspaceItem(project, 'project')).join('') : renderPanelEmpty('No hay proyectos creados.')}
      </div>
    `;
  }

  function normalizeWorkspaceItem(item) {
    const id = item.id || createId();
    return {
      ...item,
      id,
      name: item.name || item.title || 'Sin nombre',
      description: item.description || '',
      chatIds: Array.isArray(item.chatIds) ? item.chatIds : Array.isArray(item.chat_ids) ? item.chat_ids : [],
      createdAt: item.createdAt || item.created_at || nowIso(),
      updatedAt: item.updatedAt || item.updated_at || nowIso()
    };
  }

  function mergeCollection(localItems, incomingItems) {
    const byId = new Map(localItems.map(item => [item.id, item]));
    incomingItems.forEach(item => {
      if (!item || !item.id) return;
      byId.set(item.id, { ...(byId.get(item.id) || {}), ...item });
    });
    return Array.from(byId.values());
  }

  function renderWorkspaceItem(item, type) {
    const isActive = type === 'space' ? item.id === activeSpaceId : item.id === activeProjectId;
    const selectAction = type === 'space' ? 'select-space' : 'select-project';
    const attachAction = type === 'space' ? 'attach-chat-space' : 'attach-chat-project';
    return `
      <article class="assistant-panel-workspace${isActive ? ' active' : ''}">
        <div>
          <span class="assistant-panel-item-kicker">${isActive ? 'Activo' : (type === 'space' ? 'Espacio' : 'Proyecto')}</span>
          <strong>${escapeHtml(item.name)}</strong>
          <p>${escapeHtml(item.description || 'Sin descripcion')}</p>
          <small>${escapeHtml(String((item.chatIds || []).length))} chats asociados</small>
        </div>
        <div class="assistant-panel-actions compact">
          <button type="button" class="assistant-panel-btn" data-panel-action="${selectAction}" data-id="${escapeHtml(item.id)}">
            <i class="fas fa-check" aria-hidden="true"></i><span>Seleccionar</span>
          </button>
          <button type="button" class="assistant-panel-btn" data-panel-action="${attachAction}" data-id="${escapeHtml(item.id)}">
            <i class="fas fa-link" aria-hidden="true"></i><span>Asociar chat</span>
          </button>
        </div>
      </article>
    `;
  }

  async function renderSecurityPanel(refresh = false) {
    const context = getAuthContext();
    const status = refresh || !lastSystemHealth ? await loadSystemStatus() : lastSystemHealth;
    if (activePanelType !== 'security') return;
    const user = context.user || {};
    assistantPanelContent.innerHTML = `
      <div class="assistant-status-grid">
        <div class="assistant-status-item">
          <span>Sesion</span>
          ${renderStatusBadge(Boolean(context.loggedIn), 'Autenticado', 'Invitado')}
        </div>
        <div class="assistant-status-item">
          <span>Backend</span>
          ${renderStatusBadge(status.backendActive, 'Conectado', 'No disponible')}
        </div>
        <div class="assistant-status-item">
          <span>Supabase Auth</span>
          ${renderStatusBadge(status.supabaseConfigured ? true : 'warn', 'Configurado', 'No configurado')}
        </div>
        <div class="assistant-status-item">
          <span>Base de datos</span>
          ${renderStatusBadge(status.databaseConnected ? true : 'warn', 'Conectada', 'No conectada')}
        </div>
      </div>
      <div class="assistant-panel-card">
        <strong>Usuario actual</strong>
        <p>${context.loggedIn ? escapeHtml(user.email || user.name || user.id || 'Usuario autenticado') : 'Modo invitado. Inicia sesion para sincronizar informacion.'}</p>
        <p>Token: ${context.loggedIn ? 'Disponible para Authorization Bearer, no se muestra por seguridad.' : 'No hay token activo.'}</p>
      </div>
      <div class="assistant-panel-card">
        <strong>Recomendaciones</strong>
        <p>No pegues claves privadas ni SUPABASE_SERVICE_ROLE_KEY en el chat.</p>
        <p>Usa Supabase Auth para sincronizar historial, espacios y proyectos cuando el backend exponga esos endpoints.</p>
      </div>
      <div class="assistant-panel-actions">
        <button type="button" class="assistant-panel-btn primary" data-panel-action="reload-security">
          <i class="fas fa-rotate" aria-hidden="true"></i><span>Recargar seguridad</span>
        </button>
        ${context.loggedIn ? `
          <button type="button" class="assistant-panel-btn danger" data-panel-action="logout">
            <i class="fas fa-right-from-bracket" aria-hidden="true"></i><span>Cerrar sesion</span>
          </button>
        ` : `
          <button type="button" class="assistant-panel-btn" data-panel-action="open-auth">
            <i class="fas fa-user-lock" aria-hidden="true"></i><span>Iniciar sesion</span>
          </button>
        `}
      </div>
    `;
  }

  function renderMorePanel(notice = '') {
    assistantPanelContent.innerHTML = `
      ${renderPanelNotice(notice)}
      <div class="assistant-panel-list">
        ${[
          ['settings', 'Configuracion', 'Preferencias locales y estado activo.', 'fa-sliders'],
          ['odysseus', 'Herramientas avanzadas', 'Archivos, analisis, codigo, debug y plan.', 'fa-toolbox'],
          ['clear-current-chat', 'Limpiar chat actual', 'Borra solo los mensajes visibles.', 'fa-broom'],
          ['export-conversation', 'Exportar conversacion', 'Descarga un JSON de la conversacion actual.', 'fa-file-export'],
          ['help', 'Ayuda', 'Ver acciones disponibles.', 'fa-circle-question'],
          ['about', 'Acerca del asistente', 'Informacion de esta interfaz.', 'fa-info-circle'],
          ['reload-status', 'Recargar estado del sistema', 'Consulta /api/health nuevamente.', 'fa-rotate']
        ].map(([action, title, description, icon]) => `
          <button type="button" class="assistant-panel-item" data-panel-action="${action}">
            <i class="fas ${icon}" aria-hidden="true"></i>
            <strong>${title}</strong>
            <span>${description}</span>
          </button>
        `).join('')}
      </div>
    `;
  }

  function renderSettingsPanel(notice = '') {
    assistantPanelContent.innerHTML = `
      ${renderPanelNotice(notice)}
      <form class="assistant-panel-form" data-panel-form="save-settings">
        <label class="assistant-panel-check">
          <input name="rememberPanels" type="checkbox" ${assistantSettings.rememberPanels !== false ? 'checked' : ''}>
          <span>Guardar espacios y proyectos en localStorage</span>
        </label>
        <label class="assistant-panel-check">
          <input name="showEmptyStates" type="checkbox" ${assistantSettings.showEmptyStates !== false ? 'checked' : ''}>
          <span>Mostrar estados vacios claros</span>
        </label>
        <button type="submit" class="assistant-panel-btn primary">
          <i class="fas fa-save" aria-hidden="true"></i><span>Guardar configuracion</span>
        </button>
      </form>
      <div class="assistant-panel-card">
        <strong>Contexto activo</strong>
        <p>Espacio: ${escapeHtml(spaces.find(item => item.id === activeSpaceId)?.name || 'Ninguno')}</p>
        <p>Proyecto: ${escapeHtml(projects.find(item => item.id === activeProjectId)?.name || 'Ninguno')}</p>
      </div>
    `;
  }

  function renderHelpPanel() {
    assistantPanelContent.innerHTML = `
      <div class="assistant-panel-grid">
        <article class="assistant-panel-card"><strong>Buscar</strong><p>Encuentra conversaciones, prompts, espacios y proyectos locales.</p></article>
        <article class="assistant-panel-card"><strong>Historial</strong><p>Restaura conversaciones y usa backend cuando el endpoint exista.</p></article>
        <article class="assistant-panel-card"><strong>Espacios y proyectos</strong><p>Organiza el chat actual con localStorage temporal.</p></article>
        <article class="assistant-panel-card"><strong>Seguridad</strong><p>Verifica autenticacion, backend, Supabase y base de datos sin mostrar tokens.</p></article>
        <article class="assistant-panel-card"><strong>Herramientas avanzadas</strong><p>Analiza archivos subidos, busca contenido y ejecuta herramientas seguras.</p></article>
      </div>
    `;
  }

  function renderAboutPanel() {
    assistantPanelContent.innerHTML = `
      <div class="assistant-panel-card">
        <strong>JAH AI - Asistente de programacion</strong>
        <p>Interfaz frontend preparada para tutor_ia, herramientas avanzadas, Railway, Supabase Auth y PostgreSQL.</p>
        <p>API activa configurada: ${escapeHtml(getBridgeUrl() || 'sin configurar')}</p>
      </div>
    `;
  }

  function insertPrompt(text) {
    if (!coachInput) return;
    coachInput.value = text;
    autosizeInput();
    coachInput.focus();
  }

  function exportConversation() {
    const chat = getActiveChat();
    if (!chat) return;
    const payload = {
      exportedAt: nowIso(),
      source: 'jah-ai-programming-assistant',
      chat
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${(chat.title || 'jah-ai-chat').replace(/[^a-z0-9_-]+/gi, '-').slice(0, 48)}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    openPanel('more', { notice: 'Conversacion exportada como JSON.' });
  }

  function createWorkspaceItem(type, form) {
    const formData = new FormData(form);
    const item = normalizeWorkspaceItem({
      id: createId(),
      name: String(formData.get('name') || '').trim(),
      description: String(formData.get('description') || '').trim(),
      chatIds: [],
      createdAt: nowIso(),
      updatedAt: nowIso()
    });
    if (!item.name) return;
    if (type === 'space') {
      spaces.unshift(item);
      activeSpaceId = item.id;
      persistSpaces();
      persistAssistantSettings({ active_space_id: activeSpaceId });
      saveBackendCollectionItem('spaces', item);
      renderSpacesPanel('Espacio creado localmente. Se intentara sincronizar si /api/spaces existe.');
      return;
    }
    projects.unshift(item);
    activeProjectId = item.id;
    persistProjects();
    persistAssistantSettings({ active_project_id: activeProjectId });
    saveBackendCollectionItem('projects', item);
    renderProjectsPanel('Proyecto creado localmente. Se intentara sincronizar si /api/projects existe.');
  }

  function associateCurrentChat(type, id) {
    const list = type === 'space' ? spaces : projects;
    const item = list.find(entry => entry.id === id);
    if (!item) return;
    item.chatIds = Array.isArray(item.chatIds) ? item.chatIds : [];
    if (!item.chatIds.includes(activeChatId)) item.chatIds.push(activeChatId);
    item.updatedAt = nowIso();
    if (type === 'space') {
      persistSpaces();
      renderSpacesPanel('Chat actual asociado al espacio.');
    } else {
      persistProjects();
      renderProjectsPanel('Chat actual asociado al proyecto.');
    }
  }

  function selectWorkspace(type, id) {
    if (type === 'space') {
      activeSpaceId = id;
      persistAssistantSettings({ active_space_id: id });
      renderSpacesPanel('Espacio activo actualizado.');
      return;
    }
    activeProjectId = id;
    persistAssistantSettings({ active_project_id: id });
    renderProjectsPanel('Proyecto activo actualizado.');
  }

  function handleSidebarAction(action) {
    if (!action) return;
    if (action === 'new-chat') {
      startNewChat();
      return;
    }
    if (action === 'clear-history') {
      clearHistory();
      return;
    }
    openPanel(action);
  }

  async function handlePanelAction(action, button) {
    if (!action) return;
    const id = button.dataset.id || '';
    if (action === 'new-chat') return startNewChat();
    if (action === 'select-chat') {
      activateChat(id);
      closePanel();
      closeSidebar();
      coachInput.focus();
      return;
    }
    if (action === 'restore-backend-chat') {
      const backendChat = backendHistoryCache.find(chat => chat.id === id);
      if (!backendChat) return;
      const restored = normalizeChatRecord({
        ...backendChat,
        id: createId(),
        title: backendChat.title || 'Historial backend restaurado',
        updatedAt: nowIso()
      });
      chats.unshift(restored);
      activeChatId = restored.id;
      currentSessionId = ensureChatSessionId(restored);
      persist();
      renderChat();
      closePanel();
      coachInput.focus();
      return;
    }
    if (action === 'insert-prompt') {
      insertPrompt(button.dataset.prompt || '');
      return;
    }
    if (action === 'open-panel') return openPanel(button.dataset.targetPanel || 'more');
    if (action === 'select-space') return selectWorkspace('space', id);
    if (action === 'select-project') return selectWorkspace('project', id);
    if (action === 'attach-chat-space') return associateCurrentChat('space', id);
    if (action === 'attach-chat-project') return associateCurrentChat('project', id);
    if (action === 'clear-current-chat') return clearCurrentChat();
    if (action === 'clear-history') return clearHistory();
    if (action === 'export-conversation') return exportConversation();
    if (action === 'settings') return openPanel('settings');
    if (action === 'odysseus') return openPanel('odysseus');
    if (action === 'help') return openPanel('help');
    if (action === 'about') return openPanel('about');
    if (action === 'reload-status') return openPanel('system-status');
    if (action === 'reload-security') return openPanel('security');
    if (action === 'reload-odysseus') return openPanel('odysseus');
    if (action === 'odysseus-analyze-file') return runOdysseusFileAction('analyze', button.dataset.path || id);
    if (action === 'odysseus-code-file') return runOdysseusFileAction('code', button.dataset.path || id);
    if (action === 'odysseus-debug-file') return runOdysseusFileAction('debug', button.dataset.path || id);
    if (action === 'odysseus-plan-file') return runOdysseusFileAction('plan', button.dataset.path || id);
    if (action === 'odysseus-read-file') return readOdysseusFile(button.dataset.path || id);
    if (action === 'odysseus-search-files') return searchOdysseusFiles();
    if (action === 'open-auth' && window.JAHAuth && typeof window.JAHAuth.openAuth === 'function') {
      window.JAHAuth.openAuth('login');
      return;
    }
    if (action === 'logout' && window.JAHAuth && typeof window.JAHAuth.logout === 'function') {
      await window.JAHAuth.logout();
      openPanel('security');
    }
  }

  function setComposerLoading(isLoading) {
    if (sendButton) sendButton.disabled = isLoading;
    if (coachInput) coachInput.disabled = isLoading;
    if (fileInput) fileInput.disabled = isLoading;
    if (tutorIABtn) tutorIABtn.disabled = isLoading;
    if (smartSearchBtn) smartSearchBtn.disabled = isLoading;
    if (jarvisVoiceBtn) {
      jarvisVoiceBtn.disabled = isLoading || !jarvisSupported;
      jarvisVoiceBtn.classList.toggle('jarvis-disabled', !jarvisSupported);
      jarvisVoiceBtn.setAttribute('aria-disabled', String(isLoading || !jarvisSupported));
    }
  }

  function fallbackAnswer(error, filesForMessage = []) {
    const fileNames = Array.isArray(filesForMessage)
      ? filesForMessage.map(file => file.name).filter(Boolean)
      : [];
    const fileStatus = fileNames.length
      ? `Archivo recibido por la interfaz: ${fileNames.join(', ')}. El backend debe leerlo antes de llamar al modelo; vuelve a enviar la misma pregunta si el servicio estaba ocupado.`
      : 'No habia archivos adjuntos en este mensaje.';

    if (error && error.name === 'AbortError') {
      return `El backend tutor_ia no respondio dentro de ${Math.round(CHAT_TIMEOUT_MS / 1000)} segundos. ${fileStatus}\n\nPosibles soluciones:\n- Revisa Railway y los logs del servicio jah-ai-bridge.\n- Confirma que /api/health responde correctamente.\n- Si el archivo es grande, intenta una peticion mas concreta sobre una parte del archivo.`;
    }
    if (error && error.code === 'BACKEND_CONNECTION') {
      return error.message;
    }
    const detail = error && error.message ? ` Detalle: ${error.message}` : '';
    const bridgeUrl = getBridgeUrl();
    return `No pude completar la consulta con TUTOR_IA. ${fileStatus}${detail} Verifica el backend en ${bridgeUrl}/api/health.`;
  }

  function autosizeInput() {
    coachInput.style.height = 'auto';
    coachInput.style.height = `${Math.min(coachInput.scrollHeight, 220)}px`;
  }

  function openSidebar() {
    chatSidebar.classList.add('open');
    sidebarBackdrop.hidden = false;
  }

  function closeSidebar() {
    chatSidebar.classList.remove('open');
    sidebarBackdrop.hidden = true;
  }

  function setTutorIA(enabled, options = {}) {
    tutorIAEnabled = Boolean(enabled);
    window.tutorIAEnabled = tutorIAEnabled;
    if (options.persist !== false) {
      persistTutorIaPreference(tutorIAEnabled);
    }
    updateTutorButtonState();
    if (!tutorIAEnabled) {
      renderTutorTechnicalStatus();
    } else if (options.checkConnection !== false) {
      detectTutorBrain();
    } else {
      renderTutorTechnicalStatus();
    }
    if (options.sync !== false) {
      syncAssistantPreferences({
        use_rag: tutorIAEnabled,
        deep_thinking: Boolean(tutorIAEnabled || deepThinkingEnabled)
      });
    }
  }

  function setSmartSearch(enabled, options = {}) {
    smartSearchEnabled = Boolean(enabled);
    window.smartSearchEnabled = smartSearchEnabled;
    smartSearchBtn.classList.toggle('is-active', smartSearchEnabled);
    smartSearchBtn.setAttribute('aria-pressed', String(smartSearchEnabled));
    if (options.sync !== false) {
      syncAssistantPreferences({ use_web: smartSearchEnabled });
    }
  }

  function extensionForFile(file) {
    return String(file.name || '').split('.').pop().toLowerCase();
  }

  function isAllowedFile(file) {
    return ALLOWED_FILE_EXTENSIONS.has(extensionForFile(file));
  }

  function fileKey(file) {
    return `${file.name}-${file.size}-${file.lastModified}`;
  }

  function setSelectedFiles(files) {
    const existingKeys = new Set(selectedFiles.map(fileKey));
    Array.from(files || []).forEach(file => {
      if (!isAllowedFile(file)) return;
      const key = fileKey(file);
      if (!existingKeys.has(key)) {
        selectedFiles.push(file);
        existingKeys.add(key);
      }
    });
    renderAttachments();
  }

  function removeSelectedFile(index) {
    selectedFiles.splice(index, 1);
    renderAttachments();
  }

  function renderAttachments() {
    if (!attachmentPreview) return;
    attachmentPreview.hidden = selectedFiles.length === 0;
    attachmentPreview.innerHTML = selectedFiles.map((file, index) => `
      <span class="attachment-pill">
        <i class="fas fa-file" aria-hidden="true"></i>
        <span>${escapeHtml(file.name)}</span>
        <button class="remove-attachment" type="button" data-file-index="${index}" aria-label="Quitar ${escapeHtml(file.name)}">
          <i class="fas fa-times" aria-hidden="true"></i>
        </button>
      </span>
    `).join('');
    if (fileInput) fileInput.value = '';
  }

  async function uploadSelectedFiles(files) {
    const uploadFiles = Array.from(files || []).filter(isAllowedFile);
    if (!uploadFiles.length) return;
    if (!getUploadEndpoint()) {
      addMessageToChat(activeChatId, {
        role: 'assistant',
        content: 'El backend de archivos no esta configurado. Define la URL HTTPS de Railway en API_BASE_URL antes de subir archivos.'
      });
      renderChat();
      return;
    }

    setBrainStatus('checking', 'Subiendo archivo al cerebro tutor_ia...');
    let uploaded = 0;
    let failed = 0;

    for (const file of uploadFiles) {
      const formData = new FormData();
      formData.append('file', file, file.name);
      const authHeaders = window.JAHAuth && typeof window.JAHAuth.getAuthHeaders === 'function'
        ? window.JAHAuth.getAuthHeaders()
        : {};
      try {
        const response = await fetchWithTimeout(getUploadEndpoint(), {
          method: 'POST',
          headers: {
            ...authHeaders,
            'X-Session-Id': currentSessionId
          },
          body: formData
        }, 60000);
        if (!response.ok) {
          failed += 1;
          continue;
        }
        const data = await response.json().catch(() => ({}));
        const uploadedFiles = Array.isArray(data.files) ? data.files : [data];
        mergeUploadedFileMeta(uploadedFiles);
        uploaded += 1;
      } catch (error) {
        failed += 1;
      }
    }

    const chatId = activeChatId;
    if (uploaded) {
      const message = uploaded === 1
        ? 'Archivo cargado correctamente al cerebro tutor_ia.'
        : `${uploaded} archivos cargados correctamente al cerebro tutor_ia.`;
      addMessageToChat(chatId, { role: 'assistant', content: message });
      setBrainStatus('ready', message);
    }
    if (failed) {
      const message = 'No se pudo subir el archivo. Verificá que el backend esté activo.';
      addMessageToChat(chatId, { role: 'assistant', content: message });
      setBrainStatus('error', 'Error al subir archivo');
    }
    renderChat();
  }

  async function sendCurrentMessage(options = {}) {
    if (isSubmitting) return false;

    const source = options.source || 'typed_chat';
    const typedQuestion = coachInput.value.trim();
    const question = typedQuestion || (selectedFiles.length ? 'Analiza los archivos adjuntos.' : '');
    if (!question) return false;

    if (jarvisAssistant && typeof jarvisAssistant.stopSpeech === 'function') {
      jarvisAssistant.stopSpeech();
    }

    isSubmitting = true;
    const filesForMessage = selectedFiles.map(fileMeta);
    const chatId = activeChatId;
    currentSessionId = ensureChatSessionId(getActiveChat());
    writeStorageValue(scopedStorageKey(SESSION_KEY), currentSessionId);
    addMessageToChat(chatId, { role: 'user', content: question, uploadedFiles: filesForMessage });
    coachInput.value = '';
    autosizeInput();
    renderChat();
    setComposerLoading(true);

    const loadingMessage = {
      id: createId(),
      role: 'assistant',
      content: chatLoadingText(),
      createdAt: nowIso(),
      loading: true
    };
    const chat = chats.find(item => item.id === chatId);
    chat.messages.push(loadingMessage);
    chat.updatedAt = nowIso();
    persist();
    renderChat();

    try {
      if (source === 'jarvis_voice' && jarvisAssistant) {
        jarvisAssistant.showStatus('Jarvis procesando...', 'info', 0);
      }
      const result = await askTutorBrain(question, chatId, source);
      const answer = result.answer || result.response || 'TUTOR_IA respondio sin texto.';
      const showSources = Boolean(result.show_sources || (Array.isArray(result.sources) && result.sources.length));
      updateMessageInChat(chatId, loadingMessage.id, {
        content: answer,
        sources: showSources ? result.sources || [] : [],
        uploadedFiles: result.uploadedFiles || [],
        showSources,
        loading: false
      });
      updateRenderedMessage(loadingMessage.id, answer, {
        sources: showSources ? result.sources || [] : [],
        uploadedFiles: result.uploadedFiles || [],
        showSources
      });
      selectedFiles = [];
      renderAttachments();

      if (source === 'jarvis_voice') {
        notifyJarvisResponse(answer, true);
      }
      return true;
    } catch (error) {
      const answer = fallbackAnswer(error, filesForMessage);
      updateMessageInChat(chatId, loadingMessage.id, {
        content: answer,
        sources: [],
        loading: false
      });
      updateRenderedMessage(loadingMessage.id, answer);

      if (source === 'jarvis_voice') {
        notifyJarvisResponse(answer, false);
      }
      return false;
    } finally {
      isSubmitting = false;
      setComposerLoading(false);
      coachInput.focus();
      renderHistory();
    }
  }

  function setDeepThinkingFromJarvis(enable) {
    const deepThinkingControl = document.getElementById('deepThinkingBtn')
      || document.querySelector('[data-action="deep-thinking"], [data-feature="deep-thinking"], .deep-thinking-btn');

    if (!deepThinkingControl) {
      deepThinkingEnabled = Boolean(enable);
      window.deepThinkingEnabled = deepThinkingEnabled;
      syncAssistantPreferences({ deep_thinking: deepThinkingEnabled });
      return true;
    }

    const isActive = deepThinkingControl.getAttribute('aria-pressed') === 'true'
      || deepThinkingControl.classList.contains('is-active')
      || deepThinkingControl.checked === true;

    if (isActive !== enable) {
      deepThinkingControl.click();
    }

    deepThinkingEnabled = Boolean(enable);
    window.deepThinkingEnabled = deepThinkingEnabled;
    syncAssistantPreferences({ deep_thinking: deepThinkingEnabled });
    return true;
  }

  function getLastAssistantText() {
    const chat = getActiveChat();
    if (!chat || !Array.isArray(chat.messages)) return '';
    const lastAssistant = [...chat.messages]
      .reverse()
      .find(message => message.role === 'assistant' && !message.loading && message.content);
    return lastAssistant ? lastAssistant.content : '';
  }

  function notifyJarvisResponse(answer, ok = true) {
    if (!jarvisAssistant) return;
    jarvisAssistant.showStatus(ok ? 'Jarvis listo.' : 'Jarvis no pudo responder. Puedes escribir tu mensaje.', ok ? 'success' : 'error');
    if (ok) {
      jarvisAssistant.speakResponse(answer);
    }
  }

  async function refreshMarkVoiceStatus(showWhenReady = false) {
    if (!jarvisAssistant) return null;
    if (!getJarvisMarkStatusEndpoint()) return null;
    try {
      const response = await fetchWithTimeout(getJarvisMarkStatusEndpoint(), { method: 'GET' }, 5000);
      if (!response.ok) return null;
      const data = await response.json();
      const mark = data.mark_xxxix || data;
      if (mark.launch_ready && showWhenReady) {
        jarvisAssistant.showStatus('Mark XXXIX disponible: voz Charon lista.', 'success', 5000);
      }
      if (!mark.launch_ready && showWhenReady) {
        const note = Array.isArray(mark.notes) && mark.notes.length ? mark.notes[0] : 'Mark XXXIX requiere configuración.';
        jarvisAssistant.showStatus(note, 'warning', 7000);
      }
      return mark;
    } catch (error) {
      return null;
    }
  }

  async function launchMarkVoice() {
    if (!jarvisAssistant) return false;
    if (!getJarvisMarkLaunchEndpoint()) return false;
    jarvisAssistant.showStatus('Preparando Mark XXXIX...', 'info', 0);
    try {
      const response = await fetchWithTimeout(getJarvisMarkLaunchEndpoint(), { method: 'POST' }, 10000);
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.ok === false) {
        const note = data.message
          || data.detail
          || 'Mark XXXIX no está configurado. Se usará voz del navegador.';
        jarvisAssistant.showStatus(note, 'warning', 8000);
        return false;
      }
      jarvisAssistant.showStatus(data.already_running ? 'Mark XXXIX ya está activo.' : 'Mark XXXIX iniciado con voz Charon.', 'success', 7000);
      return true;
    } catch (error) {
      jarvisAssistant.showStatus('No se pudo iniciar Mark XXXIX. Se usará voz del navegador.', 'error', 7000);
      return false;
    }
  }

  function initJarvisIntegration() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    jarvisSupported = Boolean(SpeechRecognition);

    if (!window.JarvisAssistant) {
      if (jarvisVoiceBtn) {
        jarvisVoiceBtn.disabled = true;
        jarvisVoiceBtn.title = 'Voz no disponible en este navegador.';
      }
      if (jarvisStatus) {
        jarvisStatus.textContent = 'Tu navegador no soporta reconocimiento de voz. Probá con Google Chrome o Microsoft Edge.';
        jarvisStatus.className = 'jarvis-status warning';
      }
      return;
    }

    jarvisAssistant = window.JarvisAssistant.create({
      elements: {
        button: jarvisVoiceBtn,
        status: jarvisStatus,
        input: coachInput
      },
      config: {
        readResponses: JARVIS_READ_RESPONSES,
        stt: {
          provider: 'web-speech',
          language: 'es-NI',
          fallbackLanguage: 'es-ES',
          localProvidersReadyForPhase2: ['faster-whisper', 'vosk', 'speechrecognition']
        },
        tts: {
          provider: 'speech-synthesis',
          maxChars: 1300,
          codeNotice: 'La respuesta incluye código. Te recomiendo revisarlo en pantalla.'
        }
      },
      state: {
        isSubmitting: () => isSubmitting
      },
      callbacks: {
        autosizeInput,
        sendMessage: text => {
          syncAssistantPreferences({ jarvis_voice: true });
          coachInput.value = String(text || '').trim();
          autosizeInput();
          return sendCurrentMessage({ source: 'jarvis_voice' });
        },
        clearChat: () => {
          clearHistory();
          coachInput.value = '';
          autosizeInput();
          return true;
        },
        setSmartSearch: enabled => {
          setSmartSearch(Boolean(enabled));
          coachInput.focus();
          return true;
        },
        setDeepThinking: setDeepThinkingFromJarvis,
        launchMarkVoice,
        openFilePicker: () => {
          if (!fileInput || fileInput.disabled) return false;
          fileInput.click();
          return true;
        },
        getLastAssistantText
      }
    });
    window.jarvisAssistant = jarvisAssistant;
    refreshMarkVoiceStatus(false);
  }

  document.addEventListener('click', event => {
    const actionButton = event.target.closest('[data-action]');
    if (!actionButton) return;
    if (!actionButton.closest('.chat-sidebar')) return;
    event.preventDefault();
    handleSidebarAction(actionButton.dataset.action);
  });

  if (assistantPanelOverlay) {
    assistantPanelOverlay.addEventListener('click', event => {
      if (event.target === assistantPanelOverlay) closePanel();
    });
  }

  if (closeAssistantPanelBtn) {
    closeAssistantPanelBtn.addEventListener('click', closePanel);
  }

  if (assistantPanelContent) {
    assistantPanelContent.addEventListener('click', event => {
      const actionButton = event.target.closest('[data-panel-action]');
      if (!actionButton) return;
      event.preventDefault();
      handlePanelAction(actionButton.dataset.panelAction, actionButton);
    });

    assistantPanelContent.addEventListener('submit', event => {
      const form = event.target.closest('[data-panel-form]');
      if (!form) return;
      event.preventDefault();
      const formType = form.dataset.panelForm;
      if (formType === 'create-space') createWorkspaceItem('space', form);
      if (formType === 'create-project') createWorkspaceItem('project', form);
      if (formType === 'save-settings') {
        const formData = new FormData(form);
        persistAssistantSettings({
          rememberPanels: formData.has('rememberPanels'),
          showEmptyStates: formData.has('showEmptyStates')
        });
        renderSettingsPanel('Configuracion guardada localmente.');
      }
    });
  }

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && assistantPanelOverlay && !assistantPanelOverlay.hidden) {
      closePanel();
    }
  });

  openSidebarBtn.addEventListener('click', openSidebar);
  closeSidebarBtn.addEventListener('click', closeSidebar);
  sidebarBackdrop.addEventListener('click', closeSidebar);
  coachInput.addEventListener('input', autosizeInput);
  coachInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      coachForm.requestSubmit();
    }
  });

  tutorIABtn.addEventListener('click', () => {
    setTutorIA(!tutorIAEnabled);
    coachInput.focus();
  });

  smartSearchBtn.addEventListener('click', () => {
    setSmartSearch(!smartSearchEnabled);
    coachInput.focus();
  });

  fileInput.addEventListener('change', async event => {
    const files = Array.from(event.target.files || []);
    setSelectedFiles(files);
    await uploadSelectedFiles(files);
    coachInput.focus();
  });

  attachmentPreview.addEventListener('click', event => {
    const removeBtn = event.target.closest('.remove-attachment');
    if (!removeBtn) return;
    removeSelectedFile(Number(removeBtn.dataset.fileIndex));
    coachInput.focus();
  });

  coachMessages.addEventListener('click', async event => {
    const copyBtn = event.target.closest('.copy-code-btn');
    if (!copyBtn) return;
    const code = copyBtn.closest('.code-block')?.querySelector('code')?.textContent || '';
    if (!code) return;

    try {
      await navigator.clipboard.writeText(code);
      copyBtn.textContent = 'Copiado';
      window.setTimeout(() => {
        copyBtn.textContent = 'Copiar';
      }, 1300);
    } catch (error) {
      copyBtn.textContent = 'Error';
      window.setTimeout(() => {
        copyBtn.textContent = 'Copiar';
      }, 1300);
    }
  });

  coachForm.addEventListener('submit', async event => {
    event.preventDefault();
    await sendCurrentMessage({ source: 'typed_chat' });
  });

  window.addEventListener('jah-auth-preferences-changed', event => {
    const preferences = event.detail || {};
    if (Object.prototype.hasOwnProperty.call(preferences, 'use_rag')) {
      const preferredTutorState = hasTutorIaPreference()
        ? readTutorIaPreference(Boolean(preferences.use_rag))
        : Boolean(preferences.use_rag);
      setTutorIA(preferredTutorState, {
        sync: false,
        persist: !hasTutorIaPreference(),
        checkConnection: false
      });
    }
    if (Object.prototype.hasOwnProperty.call(preferences, 'use_web')) {
      setSmartSearch(Boolean(preferences.use_web), { sync: false });
    }
    if (Object.prototype.hasOwnProperty.call(preferences, 'deep_thinking')) {
      deepThinkingEnabled = Boolean(preferences.deep_thinking);
      window.deepThinkingEnabled = deepThinkingEnabled;
    }
  });

  window.addEventListener('jah-auth-session-changed', () => {
    initializeChatState('auth-session-changed');
    if (appInitialized) renderChat();
    refreshAdminTechnicalState();
  });

  window.addEventListener('jah-auth-login', () => {
    refreshAdminTechnicalState();
  });

  window.addEventListener('jah-auth-logout', () => {
    setAdminTechnicalVisibility(false);
    deepThinkingEnabled = false;
    window.deepThinkingEnabled = false;
    historyLoaded = false;
    initializeChatState('auth-logout');
    if (appInitialized) renderChat();
    coachInput.focus();
  });

  setTutorIA(readTutorIaPreference(true), { sync: false, persist: false, checkConnection: false });
  setSmartSearch(false, { sync: false });
  initJarvisIntegration();
  renderAttachments();
  autosizeInput();
  ensureButtonAccessibility(document);
  if (window.MutationObserver && document.body) {
    const accessibilityObserver = new MutationObserver(mutations => {
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === Node.ELEMENT_NODE) ensureButtonAccessibility(node);
        });
      });
    });
    accessibilityObserver.observe(document.body, { childList: true, subtree: true });
  }
  waitForAuthBeforeRender();
});
