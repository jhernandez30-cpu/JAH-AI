(() => {
  const BRAND_LOGO_SRC = './assets/brand/jah-ai-logo-transparent.png';
  const AUTH_TOKEN_KEY = 'jahAiAuthToken';
  const AUTH_USER_KEY = 'jahAiCurrentUser';
  const AUTH_PREFS_KEY = 'jahAiUserPreferences';
  function resolveApiBaseUrl() {
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

  function supabaseConfig() {
    return {
      url: String(window.APP_CONFIG?.SUPABASE_URL || '').trim().replace(/\/$/, ''),
      anonKey: String(window.APP_CONFIG?.SUPABASE_ANON_KEY || '').trim()
    };
  }

  function isSupabaseConfigured() {
    const config = supabaseConfig();
    return Boolean(config.url && config.anonKey);
  }

  function isSupabaseProviderEnabled(provider) {
    if (!isSupabaseConfigured()) return false;
    const key = provider === 'apple'
      ? 'SUPABASE_APPLE_ENABLED'
      : 'SUPABASE_GOOGLE_ENABLED';
    return window.APP_CONFIG?.[key] === true;
  }

  function getSupabaseClient() {
    if (!isSupabaseConfigured()) return null;
    if (supabaseClient) return supabaseClient;
    if (!window.supabase || typeof window.supabase.createClient !== 'function') return null;
    const config = supabaseConfig();
    supabaseClient = window.supabase.createClient(config.url, config.anonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true
      }
    });
    return supabaseClient;
  }

  const DEFAULT_PREFERENCES = {
    theme: 'system',
    language: 'es',
    response_style: 'explicativo',
    assistant_preference: 'respuestas_completas',
    visible_name: '',
    use_rag: true,
    use_web: false,
    jarvis_voice: false,
    direct_answers: false,
    deep_thinking: false,
    chat_history_enabled: true
  };

  const state = {
    token: readStorage(AUTH_TOKEN_KEY, ''),
    user: readJsonStorage(AUTH_USER_KEY, null),
    preferences: normalizePreferences(readJsonStorage(AUTH_PREFS_KEY, DEFAULT_PREFERENCES))
  };

  const els = {};
  let authFlow = 'register';
  let activeEmail = '';
  let authChecked = false;
  let authHydrating = false;
  let authProviders = { google: false, apple: false, local: true, supabase: false };
  let supabaseClient = null;

  window.JAHAuth = {
    getToken: () => state.token,
    getUser: () => state.user,
    getPreferences: () => ({ ...state.preferences }),
    getAuthHeaders,
    getContext,
    isReady: () => authChecked,
    isHydrating: () => authHydrating,
    isAdmin: () => isAdminUser(state.user),
    getApiBaseUrl: resolveApiBaseUrl,
    getSupabaseClient,
    savePreferences: savePreferencesPatch,
    openAuth: openAuthModal,
    logout
  };

  document.addEventListener('DOMContentLoaded', initAuth);

  async function initAuth() {
    authHydrating = true;
    const authCallback = readAuthCallback();
    cacheElements();
    bindBaseEvents();
    applyPreferences(state.preferences, false);
    renderAuthState();
    await loadAuthProviders();
    await bootstrapSupabaseSession();
    if (authCallback.error) {
      openAuthModal('login');
      setAuthStatus(authErrorMessage(authCallback.error, authCallback.provider), 'error');
    }
    try {
      await refreshSession(authCallback.code);
    } finally {
      authHydrating = false;
      authChecked = true;
      renderAuthState();
      window.dispatchEvent(new CustomEvent('jah-auth-ready', {
        detail: {
          context: getContext(),
          callback: Boolean(authCallback.code || authCallback.error)
        }
      }));
    }
  }

  function cacheElements() {
    [
      'assistantAuthArea',
      'guestAuthActions',
      'openLoginBtn',
      'openRegisterBtn',
      'userAccountArea',
      'userMenuBtn',
      'userMenu',
      'userAvatar',
      'userDisplayName',
      'authOverlay',
      'authModalContent',
      'closeAuthModalBtn',
      'accountPanelOverlay',
      'accountPanelContent',
      'closeAccountPanelBtn',
      'loginSoftInvite'
    ].forEach(id => {
      els[id] = document.getElementById(id);
    });
  }

  function bindBaseEvents() {
    els.openLoginBtn?.addEventListener('click', () => openAuthModal('login'));
    els.openRegisterBtn?.addEventListener('click', () => openAuthModal('register'));
    els.loginSoftInvite?.addEventListener('click', () => openAuthModal('register'));
    els.closeAuthModalBtn?.addEventListener('click', closeAuthModal);
    els.closeAccountPanelBtn?.addEventListener('click', closeAccountPanel);
    els.authOverlay?.addEventListener('click', event => {
      if (event.target === els.authOverlay) closeAuthModal();
    });
    els.accountPanelOverlay?.addEventListener('click', event => {
      if (event.target === els.accountPanelOverlay) closeAccountPanel();
    });

    els.userMenuBtn?.addEventListener('click', event => {
      event.stopPropagation();
      toggleUserMenu();
    });

    els.userMenu?.addEventListener('click', event => {
      const actionButton = event.target.closest('[data-account-action]');
      if (!actionButton) return;
      closeUserMenu();
      handleAccountAction(actionButton.dataset.accountAction);
    });

    document.addEventListener('click', event => {
      if (!event.target.closest('#userAccountArea')) closeUserMenu();
    });

    document.addEventListener('keydown', event => {
      if (event.key !== 'Escape') return;
      closeUserMenu();
      closeAuthModal();
      closeAccountPanel();
    });

    const colorScheme = window.matchMedia?.('(prefers-color-scheme: dark)');
    colorScheme?.addEventListener?.('change', () => applyPreferences(state.preferences, false));
  }

  function openAuthModal(flow = 'register', email = '') {
    authFlow = flow === 'login' ? 'login' : 'register';
    activeEmail = email || '';
    renderAuthEntry();
    if (els.authOverlay) els.authOverlay.hidden = false;
    window.setTimeout(() => {
      document.getElementById('authEmailInput')?.focus();
    }, 0);
  }

  function closeAuthModal() {
    if (els.authOverlay) els.authOverlay.hidden = true;
  }

  function closeAccountPanel() {
    if (els.accountPanelOverlay) els.accountPanelOverlay.hidden = true;
  }

  async function loadAuthProviders() {
    const apiBaseUrl = resolveApiBaseUrl();
    const fallbackProviders = {
      google: isSupabaseProviderEnabled('google'),
      apple: isSupabaseProviderEnabled('apple'),
      local: true,
      supabase: isSupabaseConfigured(),
      email_password: true
    };
    if (!apiBaseUrl) {
      authProviders = fallbackProviders;
      return authProviders;
    }
    try {
      const response = await fetchWithTimeout(`${apiBaseUrl}/api/auth/providers`, { method: 'GET' }, 4000);
      if (response.ok) {
        const data = await response.json();
        authProviders = {
          google: Boolean(data.google) || fallbackProviders.google,
          apple: Boolean(data.apple) || fallbackProviders.apple,
          local: data.local !== false
            || (Boolean(data.supabase) && data.email_password !== false),
          supabase: Boolean(data.supabase) || fallbackProviders.supabase,
          email_password: data.email_password !== false
        };
      }
    } catch (error) {
      authProviders = fallbackProviders;
    }
    return authProviders;
  }

  function renderAuthEntry() {
    if (!els.authModalContent) return;
    loadAuthProviders().then(() => {
      if (!els.authModalContent) return;
      applyProviderButtonState();
    });
    els.authModalContent.innerHTML = `
      <img src="${BRAND_LOGO_SRC}" alt="JAH AI" class="brand-logo-large auth-brand-logo" width="88" height="88" loading="eager" decoding="async">
      <h2 id="authModalTitle" class="auth-title">Iniciar sesi&oacute;n o registrarse</h2>
      <p class="auth-description">Obtendr&aacute;s respuestas m&aacute;s inteligentes y podr&aacute;s cargar archivos, im&aacute;genes y mucho m&aacute;s.</p>
      <div class="auth-stack">
        <div class="auth-flow-tabs" role="tablist" aria-label="Modo de acceso">
          <button class="${authFlow === 'register' ? 'is-active' : ''}" type="button" data-auth-flow="register">Crear cuenta</button>
          <button class="${authFlow === 'login' ? 'is-active' : ''}" type="button" data-auth-flow="login">Iniciar sesi&oacute;n</button>
        </div>
        <button id="googleLoginBtn" class="auth-provider-btn" type="button">
          <i class="fab fa-google" aria-hidden="true"></i>
          <span>Continuar con Google</span>
        </button>
        <button id="appleLoginBtn" class="auth-provider-btn" type="button">
          <i class="fab fa-apple" aria-hidden="true"></i>
          <span>Continuar con Apple</span>
        </button>
        <button id="phoneLoginBtn" class="auth-provider-btn" type="button">
          <i class="fas fa-phone" aria-hidden="true"></i>
          <span>Continuar con tel&eacute;fono</span>
        </button>
        <div class="auth-separator">o</div>
        <form id="authEmailForm" class="auth-form" novalidate>
          <div class="auth-field">
            <label for="authEmailInput">Direcci&oacute;n de correo electr&oacute;nico</label>
            <input id="authEmailInput" class="auth-input" type="email" value="${escapeHtml(activeEmail)}" autocomplete="email" placeholder="tu@email.com">
            <span class="auth-error" data-error-for="email"></span>
          </div>
          <button class="auth-submit-btn" type="submit">Continuar</button>
          <p id="authStatus" class="auth-status" role="status" aria-live="polite"></p>
        </form>
      </div>
    `;

    els.authModalContent.querySelectorAll('[data-auth-flow]').forEach(button => {
      button.addEventListener('click', () => {
        authFlow = button.dataset.authFlow;
        activeEmail = document.getElementById('authEmailInput')?.value.trim() || '';
        renderAuthEntry();
      });
    });

    document.getElementById('googleLoginBtn')?.addEventListener('click', handleGoogleAuth);
    document.getElementById('appleLoginBtn')?.addEventListener('click', handleAppleAuth);
    document.getElementById('phoneLoginBtn')?.addEventListener('click', handlePhoneLogin);
    applyProviderButtonState();
    document.getElementById('authEmailForm')?.addEventListener('submit', event => {
      event.preventDefault();
      const email = document.getElementById('authEmailInput')?.value.trim() || '';
      clearAuthErrors();
      if (!isValidEmail(email)) {
        setFieldError('email', 'Escribe un correo electr&oacute;nico v&aacute;lido.');
        return;
      }
      activeEmail = email;
      if (authFlow === 'login') {
        renderLoginForm(email);
      } else {
        renderRegisterForm(email);
      }
    });
  }

  function renderRegisterForm(email = '') {
    if (!els.authModalContent) return;
    els.authModalContent.innerHTML = `
      <img src="${BRAND_LOGO_SRC}" alt="JAH AI" class="brand-logo-large auth-brand-logo" width="88" height="88" loading="eager" decoding="async">
      <h2 id="authModalTitle" class="auth-title">Crear cuenta</h2>
      <p class="auth-description">Reg&iacute;strate gratis para guardar perfil, preferencias e historial cuando el backend est&eacute; activo.</p>
      <form id="registerForm" class="auth-form auth-stack" novalidate>
        <div class="auth-field">
          <label for="registerName">Nombre</label>
          <input id="registerName" class="auth-input" type="text" autocomplete="name" placeholder="Tu nombre">
          <span class="auth-error" data-error-for="name"></span>
        </div>
        <div class="auth-field">
          <label for="registerEmail">Correo electr&oacute;nico</label>
          <input id="registerEmail" class="auth-input" type="email" value="${escapeHtml(email)}" autocomplete="email">
          <span class="auth-error" data-error-for="email"></span>
        </div>
        <div class="auth-field">
          <label for="registerPassword">Contrase&ntilde;a</label>
          <input id="registerPassword" class="auth-input" type="password" autocomplete="new-password">
          <span class="auth-error" data-error-for="password"></span>
        </div>
        <div class="auth-field">
          <label for="registerConfirmPassword">Confirmar contrase&ntilde;a</label>
          <input id="registerConfirmPassword" class="auth-input" type="password" autocomplete="new-password">
          <span class="auth-error" data-error-for="confirm"></span>
        </div>
        <button class="auth-submit-btn" type="submit">Crear cuenta</button>
        <div class="auth-switch-row">
          <button id="goToLoginBtn" class="auth-link-btn" type="button">Ya tengo cuenta</button>
        </div>
        <p id="authStatus" class="auth-status" role="status" aria-live="polite"></p>
      </form>
    `;
    document.getElementById('goToLoginBtn')?.addEventListener('click', () => renderLoginForm(email));
    document.getElementById('registerForm')?.addEventListener('submit', submitRegister);
    window.setTimeout(() => document.getElementById('registerName')?.focus(), 0);
  }

  function renderLoginForm(email = '') {
    if (!els.authModalContent) return;
    els.authModalContent.innerHTML = `
      <img src="${BRAND_LOGO_SRC}" alt="JAH AI" class="brand-logo-large auth-brand-logo" width="88" height="88" loading="eager" decoding="async">
      <h2 id="authModalTitle" class="auth-title">Iniciar sesi&oacute;n</h2>
      <p class="auth-description">Entra con tu correo para recuperar tu perfil y preferencias del asistente.</p>
      <form id="loginForm" class="auth-form auth-stack" novalidate>
        <div class="auth-field">
          <label for="loginEmail">Correo electr&oacute;nico</label>
          <input id="loginEmail" class="auth-input" type="email" value="${escapeHtml(email)}" autocomplete="email">
          <span class="auth-error" data-error-for="email"></span>
        </div>
        <div class="auth-field">
          <label for="loginPassword">Contrase&ntilde;a</label>
          <input id="loginPassword" class="auth-input" type="password" autocomplete="current-password">
          <span class="auth-error" data-error-for="password"></span>
        </div>
        <button class="auth-submit-btn" type="submit">Iniciar sesi&oacute;n</button>
        <div class="auth-switch-row">
          <button id="goToRegisterBtn" class="auth-link-btn" type="button">Crear cuenta gratis</button>
        </div>
        <p id="authStatus" class="auth-status" role="status" aria-live="polite"></p>
      </form>
    `;
    document.getElementById('goToRegisterBtn')?.addEventListener('click', () => renderRegisterForm(email));
    document.getElementById('loginForm')?.addEventListener('submit', submitLogin);
    window.setTimeout(() => document.getElementById('loginPassword')?.focus(), 0);
  }

  async function submitRegister(event) {
    event.preventDefault();
    clearAuthErrors();
    const payload = {
      name: document.getElementById('registerName')?.value.trim() || '',
      email: document.getElementById('registerEmail')?.value.trim() || '',
      password: document.getElementById('registerPassword')?.value || '',
      confirm: document.getElementById('registerConfirmPassword')?.value || ''
    };

    let hasError = false;
    if (!payload.name) {
      setFieldError('name', 'Escribe tu nombre.');
      hasError = true;
    }
    if (!isValidEmail(payload.email)) {
      setFieldError('email', 'Escribe un correo electr&oacute;nico v&aacute;lido.');
      hasError = true;
    }
    if (payload.password.length < 8) {
      setFieldError('password', 'La contrase&ntilde;a debe tener m&iacute;nimo 8 caracteres.');
      hasError = true;
    }
    if (payload.password !== payload.confirm) {
      setFieldError('confirm', 'Las contrase&ntilde;as no coinciden.');
      hasError = true;
    }
    if (hasError) return;

    setAuthStatus('Creando cuenta...');
    if (isSupabaseConfigured()) {
      await submitSupabaseRegister(payload);
      return;
    }
    const backendReady = await ensureAuthBackendAvailable();
    if (!backendReady) return;
    try {
      const data = await authFetch('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          name: payload.name,
          email: payload.email,
          password: payload.password
        })
      });
      acceptSession(data);
      setAuthStatus('Cuenta creada correctamente.', 'success');
      window.setTimeout(closeAuthModal, 450);
    } catch (error) {
      setAuthStatus(error.message || 'No se pudo crear la cuenta.', 'error');
    }
  }

  async function submitLogin(event) {
    event.preventDefault();
    clearAuthErrors();
    const payload = {
      email: document.getElementById('loginEmail')?.value.trim() || '',
      password: document.getElementById('loginPassword')?.value || ''
    };

    let hasError = false;
    if (!isValidEmail(payload.email)) {
      setFieldError('email', 'Escribe un correo electr&oacute;nico v&aacute;lido.');
      hasError = true;
    }
    if (!payload.password) {
      setFieldError('password', 'Escribe tu contrase&ntilde;a.');
      hasError = true;
    }
    if (hasError) return;

    setAuthStatus('Iniciando sesi&oacute;n...');
    if (isSupabaseConfigured()) {
      await submitSupabaseLogin(payload);
      return;
    }
    const backendReady = await ensureAuthBackendAvailable();
    if (!backendReady) return;
    try {
      const data = await authFetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      acceptSession(data);
      setAuthStatus('Sesi&oacute;n iniciada.', 'success');
      window.setTimeout(closeAuthModal, 450);
    } catch (error) {
      setAuthStatus(error.message || 'Credenciales incorrectas.', 'error');
    }
  }

  async function submitSupabaseRegister(payload) {
    try {
      const client = getSupabaseClient();
      if (!client) throw new Error('Supabase Auth no está configurado.');
      const { data, error } = await client.auth.signUp({
        email: payload.email,
        password: payload.password,
        options: {
          data: {
            name: payload.name,
            full_name: payload.name,
            display_name: payload.name
          },
          emailRedirectTo: currentReturnUrl()
        }
      });
      if (error) throw error;
      if (!data?.session?.access_token) {
        setAuthStatus('Cuenta creada. Revisa tu correo si Supabase exige confirmación antes de iniciar sesión.', 'success');
        return;
      }
      await acceptSupabaseSession(data.session, data.user);
      setAuthStatus('Cuenta creada correctamente.', 'success');
      window.setTimeout(closeAuthModal, 450);
    } catch (error) {
      setAuthStatus(supabaseErrorMessage(error, 'No se pudo crear la cuenta.'), 'error');
    }
  }

  async function submitSupabaseLogin(payload) {
    try {
      const client = getSupabaseClient();
      if (!client) throw new Error('Supabase Auth no está configurado.');
      const { data, error } = await client.auth.signInWithPassword({
        email: payload.email,
        password: payload.password
      });
      if (error) throw error;
      await acceptSupabaseSession(data.session, data.user);
      setAuthStatus('Sesi&oacute;n iniciada.', 'success');
      window.setTimeout(closeAuthModal, 450);
    } catch (error) {
      setAuthStatus(supabaseErrorMessage(error, 'Credenciales incorrectas.'), 'error');
    }
  }

  async function bootstrapSupabaseSession() {
    if (!isSupabaseConfigured()) return false;
    try {
      const client = getSupabaseClient();
      if (!client) return false;
      const { data, error } = await client.auth.getSession();
      if (error) throw error;
      const session = data?.session;
      if (!session?.access_token) return false;
      acceptSupabaseFallbackSession(session, session.user);
      return true;
    } catch (error) {
      console.warn('[JAHAuth] No se pudo restaurar sesión Supabase.', error);
      return false;
    }
  }

  async function acceptSupabaseSession(session, user) {
    if (!session?.access_token) {
      throw new Error('Supabase no devolvió una sesión activa.');
    }
    acceptSupabaseFallbackSession(session, user || session.user);
    try {
      const data = await authFetch('/api/auth/session', { method: 'GET' });
      if (data.authenticated && data.user) {
        acceptSession(data);
      }
      return data;
    } catch (error) {
      console.warn('[JAHAuth] Sesión Supabase activa sin sincronización backend.', error);
      return {
        ok: true,
        authenticated: true,
        user: state.user,
        preferences: state.preferences,
        persistence: { status: 'SUPABASE_FRONTEND_ONLY' }
      };
    }
  }

  function acceptSupabaseFallbackSession(session, user) {
    state.token = session?.access_token || '';
    state.user = supabasePublicUser(user || session?.user || {});
    state.preferences = normalizePreferences(state.preferences);
    writeStorage(AUTH_TOKEN_KEY, state.token);
    writeJsonStorage(AUTH_USER_KEY, state.user);
    writeJsonStorage(AUTH_PREFS_KEY, state.preferences);
    applyPreferences(state.preferences);
    renderAuthState();
    window.dispatchEvent(new CustomEvent('jah-auth-session-changed', {
      detail: {
        context: getContext(),
        persistence: { status: 'SUPABASE_FRONTEND_SESSION' }
      }
    }));
  }

  function supabasePublicUser(user = {}) {
    const metadata = user.user_metadata && typeof user.user_metadata === 'object'
      ? user.user_metadata
      : {};
    const email = String(user.email || metadata.email || '').trim().toLowerCase();
    const name = metadata.name || metadata.full_name || metadata.display_name || email.split('@')[0] || 'Usuario';
    return {
      id: String(user.id || ''),
      name,
      email,
      auth_provider: 'supabase',
      role: 'user',
      is_admin: false,
      profile_picture: metadata.avatar_url || metadata.picture || '',
      created_at: user.created_at || '',
      updated_at: user.updated_at || '',
      last_login: user.last_sign_in_at || '',
      plan: metadata.plan || 'Gratis'
    };
  }

  function handleGoogleAuth() {
    startProviderAuth('google');
  }

  function handleAppleAuth() {
    startProviderAuth('apple');
  }

  function handleGoogleLogin() {
    handleGoogleAuth();
  }

  function handleAppleLogin() {
    handleAppleAuth();
  }

  function applyProviderButtonState() {
    const googleBtn = document.getElementById('googleLoginBtn');
    const appleBtn = document.getElementById('appleLoginBtn');
    if (googleBtn) {
      googleBtn.disabled = !authProviders.google;
      googleBtn.title = authProviders.google
        ? 'Continuar con Google'
        : 'Google no configurado. Activa Google en Supabase Auth y define SUPABASE_GOOGLE_ENABLED=true en Railway.';
      googleBtn.classList.toggle('is-disabled', !authProviders.google);
    }
    if (appleBtn) {
      appleBtn.disabled = !authProviders.apple;
      appleBtn.title = authProviders.apple
        ? 'Continuar con Apple'
        : 'Apple no configurado. Activa Apple en Supabase Auth y define SUPABASE_APPLE_ENABLED=true en Railway.';
      appleBtn.classList.toggle('is-disabled', !authProviders.apple);
    }
  }

  async function startProviderAuth(provider) {
    const providerLabel = provider === 'apple' ? 'Apple' : 'Google';
    if (isSupabaseConfigured()) {
      await loadAuthProviders();
      if (!authProviders[provider]) {
        setAuthStatus(
          provider === 'google'
            ? 'Google Login pendiente de configurar en Supabase Auth.'
            : 'Apple Login pendiente de configurar en Supabase Auth.',
          'error'
        );
        return;
      }
      try {
        const client = getSupabaseClient();
        if (!client) throw new Error('Supabase no está disponible en esta página.');
        setAuthStatus(`Conectando con ${providerLabel}...`);
        const { error } = await client.auth.signInWithOAuth({
          provider,
          options: {
            redirectTo: currentReturnUrl(),
            queryParams: provider === 'google' ? { prompt: 'select_account' } : {}
          }
        });
        if (error) throw error;
      } catch (error) {
        setAuthStatus(error.message || `No se pudo iniciar sesión con ${providerLabel}.`, 'error');
      }
      return;
    }
    const apiBaseUrl = resolveApiBaseUrl();
    if (!apiBaseUrl) {
      setAuthStatus(`No se puede conectar con ${providerLabel}: el backend de autenticación no está configurado. Revisa la URL pública de Railway.`, 'error');
      return;
    }
    await loadAuthProviders();
    if (!authProviders[provider]) {
      setAuthStatus(
        provider === 'google'
          ? 'Google Login pendiente de configuración. Activa Google en Supabase Auth y define las variables necesarias en Railway.'
          : 'Apple Login pendiente de configuración. Activa Apple en Supabase Auth y define las variables necesarias en Railway.',
        'error'
      );
      return;
    }
    setAuthStatus(`Conectando con ${providerLabel}...`);
    const backendReady = await ensureAuthBackendAvailable();
    if (!backendReady) return;
    const returnTo = currentReturnUrl();
    window.location.assign(`${apiBaseUrl}/api/auth/${provider}/start?return_to=${encodeURIComponent(returnTo)}`);
  }

  function handlePhoneLogin() {
    if (!els.authModalContent) return;
    els.authModalContent.innerHTML = `
      <h2 id="authModalTitle" class="auth-title">Continuar con tel&eacute;fono</h2>
      <p class="auth-description">La verificaci&oacute;n por SMS queda preparada para conectarse al backend.</p>
      <form id="phoneForm" class="auth-form auth-stack" novalidate>
        <div class="phone-grid">
          <div class="auth-field">
            <label for="phoneCountry">C&oacute;digo</label>
            <input id="phoneCountry" class="auth-input" type="text" value="+505" inputmode="tel">
          </div>
          <div class="auth-field">
            <label for="phoneNumber">N&uacute;mero de tel&eacute;fono</label>
            <input id="phoneNumber" class="auth-input" type="tel" inputmode="tel" placeholder="8888 8888">
          </div>
        </div>
        <button class="auth-submit-btn" type="submit">Continuar</button>
        <button id="backToAuthBtn" class="auth-secondary-btn" type="button">Volver</button>
        <p id="authStatus" class="auth-status" role="status" aria-live="polite"></p>
      </form>
    `;
    document.getElementById('backToAuthBtn')?.addEventListener('click', renderAuthEntry);
    document.getElementById('phoneForm')?.addEventListener('submit', event => {
      event.preventDefault();
      setAuthStatus('Verificaci\u00f3n por tel\u00e9fono pendiente de configurar.');
    });
    window.setTimeout(() => document.getElementById('phoneNumber')?.focus(), 0);
  }

  window.handleGoogleLogin = handleGoogleLogin;
  window.handleAppleLogin = handleAppleLogin;
  window.handleGoogleAuth = handleGoogleAuth;
  window.handleAppleAuth = handleAppleAuth;
  window.handlePhoneLogin = handlePhoneLogin;

  function acceptSession(data) {
    const previousUserKey = state.user ? String(state.user.id || state.user.email || '') : '';
    state.token = data.token || data.access_token || '';
    state.user = data.user || null;
    state.preferences = normalizePreferences(data.preferences || state.preferences);
    writeStorage(AUTH_TOKEN_KEY, state.token);
    writeJsonStorage(AUTH_USER_KEY, state.user);
    writeJsonStorage(AUTH_PREFS_KEY, state.preferences);
    applyPreferences(state.preferences);
    renderAuthState();
    window.dispatchEvent(new CustomEvent('jah-auth-session-changed', {
      detail: {
        context: getContext(),
        memory: data.memory || {},
        persistence: data.persistence || {},
        sqlserver: data.sqlserver || {}
      }
    }));
    const nextUserKey = state.user ? String(state.user.id || state.user.email || '') : '';
    if (state.user && nextUserKey !== previousUserKey) {
      window.dispatchEvent(new CustomEvent('jah-auth-login', {
        detail: {
          user: { ...state.user },
          memory: data.memory || {},
          persistence: data.persistence || {}
        }
      }));
    }
  }

  async function refreshSession(authCode = '') {
    if (!state.token && !authCode) return;
    try {
      const path = authCode
        ? `/api/auth/session?code=${encodeURIComponent(authCode)}`
        : '/api/auth/session';
      const data = await authFetch(path, { method: 'GET' });
      if (data.authenticated && data.user) {
        acceptSession(data);
        if (authCode) {
          closeAuthModal();
          renderAuthState();
        }
      } else if (authCode) {
        openAuthModal('login');
        setAuthStatus('No se pudo recuperar la sesion del proveedor.', 'error');
      }
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        clearSession(false);
      } else if (authCode) {
        openAuthModal('login');
        setAuthStatus(error.message || 'No se pudo completar la autenticacion.', 'error');
      }
    }
  }

  function renderAuthState() {
    const loggedIn = Boolean(state.token && state.user);
    const showGuestAuth = !loggedIn && authChecked && !authHydrating;
    const authState = loggedIn
      ? 'logged-in'
      : showGuestAuth
        ? 'guest'
        : 'checking';
    if (els.assistantAuthArea) {
      els.assistantAuthArea.dataset.authState = authState;
    }
    if (els.guestAuthActions) els.guestAuthActions.hidden = !showGuestAuth;
    if (els.userAccountArea) els.userAccountArea.hidden = !loggedIn;
    if (els.loginSoftInvite) els.loginSoftInvite.hidden = !showGuestAuth;
    if (!loggedIn) return;

    const label = displayName();
    if (els.userDisplayName) els.userDisplayName.textContent = label;
    if (els.userAvatar) els.userAvatar.textContent = initialFrom(label);
  }

  function displayName() {
    return (
      state.preferences.visible_name ||
      state.user?.name ||
      state.user?.email ||
      'Usuario'
    );
  }

  function initialFrom(value) {
    const clean = String(value || 'U').trim();
    return clean ? clean.charAt(0).toUpperCase() : 'U';
  }

  function toggleUserMenu() {
    if (!els.userMenu || !els.userMenuBtn) return;
    const isHidden = els.userMenu.hidden;
    els.userMenu.hidden = !isHidden;
    els.userMenuBtn.setAttribute('aria-expanded', String(isHidden));
  }

  function closeUserMenu() {
    if (els.userMenu) els.userMenu.hidden = true;
    if (els.userMenuBtn) els.userMenuBtn.setAttribute('aria-expanded', 'false');
  }

  function handleAccountAction(action) {
    if (action === 'logout') {
      logout();
      return;
    }
    if (action === 'profile') openProfilePanel();
    if (action === 'settings') openSettingsPanel();
    if (action === 'personalization') openPersonalizationPanel();
    if (action === 'help') openHelpPanel();
    if (action === 'upgrade') openUpgradePanel();
  }

  async function openProfilePanel() {
    let profile = state.user;
    if (state.token) {
      try {
        const data = await authFetch('/api/user/profile', { method: 'GET' });
        profile = data.user || profile;
        state.user = profile;
        writeJsonStorage(AUTH_USER_KEY, state.user);
      } catch (error) {
        profile = state.user;
      }
    }

    renderPanel(`
      <h2 id="accountPanelTitle" class="panel-title">Perfil</h2>
      <p class="panel-description">Administra los datos principales de tu cuenta local.</p>
      <div class="panel-stack">
        <div class="panel-readonly-grid">
          <div class="panel-readonly-item">
            <span>Nombre</span>
            <strong>${escapeHtml(profile?.name || 'Sin nombre')}</strong>
          </div>
          <div class="panel-readonly-item">
            <span>Correo</span>
            <strong>${escapeHtml(profile?.email || 'Sin correo')}</strong>
          </div>
          <div class="panel-readonly-item">
            <span>Fecha de creaci&oacute;n</span>
            <strong>${escapeHtml(formatDate(profile?.created_at))}</strong>
          </div>
          <div class="panel-readonly-item">
            <span>Plan actual</span>
            <strong>${escapeHtml(profile?.plan || 'Gratis')}</strong>
          </div>
        </div>
        <form id="profileForm" class="panel-form" novalidate>
          <div class="panel-field">
            <label for="profileName">Editar nombre</label>
            <input id="profileName" class="panel-input" type="text" value="${escapeHtml(profile?.name || '')}">
          </div>
          <button class="panel-primary-btn" type="submit">Guardar cambios</button>
          <p id="panelStatus" class="panel-status" role="status" aria-live="polite"></p>
        </form>
      </div>
    `);

    document.getElementById('profileForm')?.addEventListener('submit', async event => {
      event.preventDefault();
      const name = document.getElementById('profileName')?.value.trim() || '';
      if (!name) {
        setPanelStatus('Escribe un nombre v&aacute;lido.', 'error');
        return;
      }
      try {
        const data = await authFetch('/api/user/profile', {
          method: 'PUT',
          body: JSON.stringify({ name })
        });
        state.user = data.user || { ...state.user, name };
        writeJsonStorage(AUTH_USER_KEY, state.user);
        renderAuthState();
        setPanelStatus('Perfil actualizado.', 'success');
      } catch (error) {
        setPanelStatus(error.message || 'No se pudo guardar el perfil.', 'error');
      }
    });
  }

  function openSettingsPanel() {
    const prefs = normalizePreferences(state.preferences);
    renderPanel(`
      <h2 id="accountPanelTitle" class="panel-title">Configuraci&oacute;n</h2>
      <p class="panel-description">Estas preferencias se guardan localmente y quedan listas para sincronizarse con el backend.</p>
      <form id="settingsForm" class="panel-form panel-stack" novalidate>
        <div class="panel-field">
          <label for="settingsTheme">Tema</label>
          <select id="settingsTheme" class="panel-select">
            ${option('light', 'Claro', prefs.theme)}
            ${option('dark', 'Oscuro', prefs.theme)}
            ${option('system', 'Sistema', prefs.theme)}
          </select>
        </div>
        <div class="panel-field">
          <label for="settingsLanguage">Idioma</label>
          <select id="settingsLanguage" class="panel-select">
            ${option('es', 'Espa&ntilde;ol', prefs.language)}
          </select>
        </div>
        <label class="panel-toggle">
          <span>Activar historial del chat</span>
          <input id="settingsChatHistory" type="checkbox" ${prefs.chat_history_enabled ? 'checked' : ''}>
        </label>
        <label class="panel-toggle">
          <span>Respuestas m&aacute;s directas</span>
          <input id="settingsDirectAnswers" type="checkbox" ${prefs.direct_answers ? 'checked' : ''}>
        </label>
        <label class="panel-toggle">
          <span>Pensamiento profundo</span>
          <input id="settingsDeepThinking" type="checkbox" ${prefs.deep_thinking ? 'checked' : ''}>
        </label>
        <button class="panel-primary-btn" type="submit">Guardar preferencias</button>
        <p id="panelStatus" class="panel-status" role="status" aria-live="polite"></p>
      </form>
    `);

    document.getElementById('settingsForm')?.addEventListener('submit', async event => {
      event.preventDefault();
      await savePreferencesFromPanel({
        theme: document.getElementById('settingsTheme')?.value || 'system',
        language: document.getElementById('settingsLanguage')?.value || 'es',
        chat_history_enabled: Boolean(document.getElementById('settingsChatHistory')?.checked),
        direct_answers: Boolean(document.getElementById('settingsDirectAnswers')?.checked),
        deep_thinking: Boolean(document.getElementById('settingsDeepThinking')?.checked)
      });
    });
  }

  function openPersonalizationPanel() {
    const prefs = normalizePreferences(state.preferences);
    renderPanel(`
      <h2 id="accountPanelTitle" class="panel-title">Personalizaci&oacute;n</h2>
      <p class="panel-description">Ajusta c&oacute;mo quieres que el asistente adapte las respuestas.</p>
      <form id="personalizationForm" class="panel-form panel-stack" novalidate>
        <div class="panel-field">
          <label for="visibleName">Nombre visible del usuario</label>
          <input id="visibleName" class="panel-input" type="text" value="${escapeHtml(prefs.visible_name || '')}" placeholder="${escapeHtml(state.user?.name || 'Tu nombre')}">
        </div>
        <div class="panel-field">
          <label for="responseStyle">Estilo de respuesta</label>
          <select id="responseStyle" class="panel-select">
            ${option('directo', 'Directo', prefs.response_style)}
            ${option('explicativo', 'Explicativo', prefs.response_style)}
            ${option('tutor_paso_a_paso', 'Tutor paso a paso', prefs.response_style)}
            ${option('tecnico_avanzado', 'T&eacute;cnico avanzado', prefs.response_style)}
          </select>
        </div>
        <div class="panel-field">
          <label for="assistantPreference">Preferencia del asistente</label>
          <select id="assistantPreference" class="panel-select">
            ${option('respuestas_cortas', 'Respuestas cortas', prefs.assistant_preference)}
            ${option('respuestas_completas', 'Respuestas completas', prefs.assistant_preference)}
            ${option('respuestas_con_ejemplos', 'Respuestas con ejemplos', prefs.assistant_preference)}
          </select>
        </div>
        <button class="panel-primary-btn" type="submit">Guardar cambios</button>
        <p id="panelStatus" class="panel-status" role="status" aria-live="polite"></p>
      </form>
    `);

    document.getElementById('personalizationForm')?.addEventListener('submit', async event => {
      event.preventDefault();
      await savePreferencesFromPanel({
        visible_name: document.getElementById('visibleName')?.value.trim() || '',
        response_style: document.getElementById('responseStyle')?.value || 'explicativo',
        assistant_preference: document.getElementById('assistantPreference')?.value || 'respuestas_completas'
      });
    });
  }

  function openHelpPanel() {
    renderPanel(`
      <h2 id="accountPanelTitle" class="panel-title">Centro de ayuda</h2>
      <ul class="help-list">
        <li><i class="fas fa-message" aria-hidden="true"></i><span>C&oacute;mo usar el asistente</span></li>
        <li><i class="fas fa-file-arrow-up" aria-hidden="true"></i><span>C&oacute;mo subir archivos</span></li>
        <li><i class="fas fa-brain" aria-hidden="true"></i><span>C&oacute;mo funciona el cerebro tutor_ia</span></li>
        <li><i class="fas fa-magnifying-glass" aria-hidden="true"></i><span>C&oacute;mo activar b&uacute;squeda inteligente</span></li>
        <li><i class="fas fa-microphone" aria-hidden="true"></i><span>C&oacute;mo usar Jarvis por voz</span></li>
        <li><i class="fas fa-headset" aria-hidden="true"></i><span>Contactar soporte</span></li>
      </ul>
    `);
  }

  function openUpgradePanel() {
    renderPanel(`
      <h2 id="accountPanelTitle" class="panel-title">Upgrade plan</h2>
      <p class="panel-description">Tu plan actual es Gratis. La estructura queda preparada para conectar planes, pagos o limites desde el backend.</p>
      <div class="panel-stack">
        <button class="panel-primary-btn" type="button">Plan actual: Gratis</button>
        <p id="panelStatus" class="panel-status">Upgrade plan pendiente de configurar.</p>
      </div>
    `);
  }

  function renderPanel(html) {
    if (!els.accountPanelContent || !els.accountPanelOverlay) return;
    els.accountPanelContent.innerHTML = html;
    els.accountPanelOverlay.hidden = false;
  }

  async function savePreferencesFromPanel(patch) {
    try {
      await savePreferencesPatch(patch);
    } catch (error) {
      setPanelStatus('Guardado local. Backend no disponible para sincronizar.', 'error');
      return;
    }
    renderAuthState();
    if (!state.token) {
      setPanelStatus('Preferencias guardadas localmente.', 'success');
      return;
    }
    setPanelStatus('Preferencias guardadas.', 'success');
  }

  async function savePreferencesPatch(patch) {
    const nextPrefs = normalizePreferences({ ...state.preferences, ...(patch || {}) });
    state.preferences = nextPrefs;
    writeJsonStorage(AUTH_PREFS_KEY, state.preferences);
    applyPreferences(state.preferences);

    if (!state.token) {
      return state.preferences;
    }

    const data = await authFetch('/api/user/preferences', {
      method: 'PUT',
      body: JSON.stringify(nextPrefs)
    });
    state.preferences = normalizePreferences(data.preferences || nextPrefs);
    writeJsonStorage(AUTH_PREFS_KEY, state.preferences);
    applyPreferences(state.preferences);
    return state.preferences;
  }

  async function logout() {
    if (isSupabaseConfigured()) {
      try {
        await getSupabaseClient()?.auth.signOut();
      } catch (error) {
        // La sesion visual se cierra aunque Supabase no responda.
      }
    }
    if (state.token) {
      try {
        await authFetch('/api/auth/logout', { method: 'POST' });
      } catch (error) {
        // La sesion local se cierra aunque el backend no responda.
      }
    }
    clearSession(true);
  }

  function clearSession(emitLogout) {
    state.token = '';
    state.user = null;
    removeStorage(AUTH_TOKEN_KEY);
    removeStorage(AUTH_USER_KEY);
    closeUserMenu();
    closeAccountPanel();
    renderAuthState();
    if (emitLogout) {
      window.dispatchEvent(new CustomEvent('jah-auth-logout'));
    }
  }

  function applyPreferences(preferences, emitEvent = true) {
    const prefs = normalizePreferences(preferences);
    const wantsDark = prefs.theme === 'dark'
      || (prefs.theme === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches);
    document.body.classList.toggle('assistant-theme-dark', Boolean(wantsDark));
    if (emitEvent) {
      window.dispatchEvent(new CustomEvent('jah-auth-preferences-changed', { detail: prefs }));
    }
  }

  function getContext() {
    return {
      token: state.token,
      user: state.user ? { ...state.user } : null,
      preferences: { ...state.preferences },
      isAdmin: isAdminUser(state.user),
      loggedIn: Boolean(state.token && state.user)
    };
  }

  function getAuthHeaders() {
    return state.token ? { Authorization: `Bearer ${state.token}` } : {};
  }

  async function authFetch(path, options = {}) {
    const apiBaseUrl = resolveApiBaseUrl();
    if (!apiBaseUrl) {
      const error = new Error('El backend de autenticación no está disponible. Configura la URL HTTPS de Railway en API_BASE_URL.');
      error.status = 0;
      error.code = 'AUTH_BACKEND_NOT_CONFIGURED';
      throw error;
    }
    const headers = {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...getAuthHeaders(),
      ...(options.headers || {})
    };
    const requestUrl = `${apiBaseUrl}${path}`;
    let response;
    try {
      response = await fetchWithTimeout(requestUrl, {
        ...options,
        headers
      }, options.timeoutMs || 9000);
    } catch (error) {
      const friendly = buildAuthNetworkError(error, requestUrl, path);
      console.warn('[JAHAuth] No se pudo conectar con autenticacion.', {
        path,
        apiBaseUrl,
        errorName: error?.name || '',
        errorMessage: error?.message || ''
      });
      throw friendly;
    }
    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      data = {};
    }
    if (!response.ok || data.ok === false) {
      const message = authHttpErrorMessage(response.status, path, data);
      const error = new Error(message);
      error.status = response.status;
      error.code = data.code || data.error_code || '';
      throw error;
    }
    return data;
  }

  function buildAuthNetworkError(error, requestUrl, path) {
    const friendly = new Error(authNetworkErrorMessage(error, requestUrl, path));
    friendly.status = 0;
    friendly.code = error?.name === 'AbortError'
      ? 'AUTH_BACKEND_TIMEOUT'
      : 'AUTH_BACKEND_UNREACHABLE';
    friendly.cause = error;
    return friendly;
  }

  function authNetworkErrorMessage(error, requestUrl, path) {
    void requestUrl;
    void path;
    if (error?.name === 'AbortError') {
      return 'El backend de autenticación no respondió a tiempo. Verifica Railway y la URL configurada: ' + resolveApiBaseUrl() + '.';
    }
    return 'No se pudo conectar con el backend de autenticación en ' + resolveApiBaseUrl() + '. Verifica Railway, CORS y la URL del servicio.';
  }

  function authHttpErrorMessage(status, path, data = {}) {
    const backendMsg = backendErrorMessage(data);
    if (status === 404) {
      if (path.includes('/register')) return 'La ruta de registro no existe en el backend. Verifica que el backend esté actualizado.';
      if (path.includes('/login')) return 'La ruta de login no existe en el backend. Verifica que el backend esté actualizado.';
      return 'La ruta de autenticación no existe en el backend.';
    }
    if (status === 405) {
      return 'El método HTTP no es compatible con la ruta del backend.';
    }
    if (status === 409) {
      return backendMsg || 'Ya existe una cuenta con ese correo electrónico.';
    }
    if (status === 401) {
      return backendMsg || 'Correo o contraseña incorrectos.';
    }
    if (status === 422) {
      return backendMsg || 'Los datos enviados no son válidos. Revisa los campos del formulario.';
    }
    if (status === 500) {
      return 'Error interno del servidor. Intenta de nuevo en unos momentos.';
    }
    if (status === 503) {
      return backendMsg || 'El servicio de autenticación no está disponible temporalmente.';
    }
    return backendMsg || `Error HTTP ${status} en autenticación.`;
  }

  function backendErrorMessage(data = {}) {
    const candidates = [data.detail, data.error, data.message];
    for (const candidate of candidates) {
      const message = normalizeBackendMessage(candidate);
      if (message) return message;
    }
    return '';
  }

  function normalizeBackendMessage(value) {
    if (!value) return '';
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) {
      return value.map(normalizeBackendMessage).filter(Boolean).join(' ');
    }
    if (typeof value === 'object') {
      if (value.msg) return String(value.msg);
      if (value.message) return String(value.message);
      if (value.detail) return normalizeBackendMessage(value.detail);
      try {
        return JSON.stringify(value);
      } catch (error) {
        return '';
      }
    }
    return String(value);
  }

  async function ensureAuthBackendAvailable() {
    const apiBaseUrl = resolveApiBaseUrl();
    if (!apiBaseUrl) {
      setAuthStatus('El backend de autenticación no está configurado. Define la URL HTTPS de Railway en API_BASE_URL.', 'error');
      return false;
    }
    try {
      await authFetch('/api/health', { method: 'GET', timeoutMs: 4500 });
      return true;
    } catch (error) {
      const isNotConfigured = error.code === 'AUTH_BACKEND_NOT_CONFIGURED';
      const onPublicSite = window.APP_CONFIG?.IS_GITHUB_PAGES && window.location.protocol === 'https:';
      let hint = isNotConfigured
        ? 'El backend no está configurado. Define la URL HTTPS de Railway en API_BASE_URL.'
        : 'No se pudo conectar con el backend en ' + apiBaseUrl + '. Verifica Railway, CORS y la URL del servicio.';
      if (onPublicSite && !isNotConfigured) {
        hint += ' Desde GitHub Pages el asistente debe llamar al backend HTTPS de Railway, no a procesos locales.';
      }
      setAuthStatus(hint, 'error');
      return false;
    }
  }

  async function fetchWithTimeout(url, options = {}, timeoutMs = 9000) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...options, signal: controller.signal });
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function readAuthCallback() {
    const result = { code: '', error: '', provider: '' };
    try {
      const url = new URL(window.location.href);
      result.code = url.searchParams.get('auth_code') || '';
      result.error = url.searchParams.get('auth_error') || '';
      result.provider = url.searchParams.get('provider') || '';
      const hasAuthParams = ['auth_status', 'auth_code', 'auth_error', 'provider'].some(param => url.searchParams.has(param));
      if (hasAuthParams) {
        ['auth_status', 'auth_code', 'auth_error', 'provider'].forEach(param => url.searchParams.delete(param));
        window.history.replaceState({}, document.title, url.toString());
      }
    } catch (error) {
      return result;
    }
    return result;
  }

  function currentReturnUrl() {
    try {
      const url = new URL(window.location.href);
      ['auth_status', 'auth_code', 'auth_error', 'provider'].forEach(param => url.searchParams.delete(param));
      return url.toString();
    } catch (error) {
      return window.location.href;
    }
  }

  function authErrorMessage(errorCode, provider) {
    const providerLabel = provider === 'apple' ? 'Apple' : provider === 'google' ? 'Google' : 'autenticación';
    const normalized = String(errorCode || '').toLowerCase();
    if (normalized.includes('google_not_configured')) {
      return 'Google Login no está configurado. Añade GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET y GOOGLE_REDIRECT_URI en bridge_api/.env.';
    }
    if (normalized.includes('apple_not_configured')) {
      return 'Apple Login no está configurado. Añade APPLE_CLIENT_ID, APPLE_CLIENT_SECRET y APPLE_REDIRECT_URI en bridge_api/.env.';
    }
    if (normalized.includes('access_denied')) {
      return `Inicio con ${providerLabel} cancelado.`;
    }
    return `No se pudo iniciar sesión con ${providerLabel}. ${errorCode || ''}`.trim();
  }

  function supabaseErrorMessage(error, fallback) {
    const raw = String(error?.message || error?.error_description || error || '').trim();
    const normalized = raw.toLowerCase();
    if (normalized.includes('already') || normalized.includes('registered')) {
      return 'Ya existe una cuenta con ese correo electrónico.';
    }
    if (normalized.includes('invalid login') || normalized.includes('invalid credentials')) {
      return 'Correo o contraseña incorrectos.';
    }
    if (normalized.includes('email not confirmed')) {
      return 'Debes confirmar tu correo antes de iniciar sesión.';
    }
    return raw || fallback;
  }

  function normalizePreferences(value) {
    const source = value && typeof value === 'object' ? value : {};
    return {
      ...DEFAULT_PREFERENCES,
      ...source,
      use_rag: asBoolean(source.use_rag, DEFAULT_PREFERENCES.use_rag),
      use_web: asBoolean(source.use_web, DEFAULT_PREFERENCES.use_web),
      jarvis_voice: asBoolean(source.jarvis_voice, DEFAULT_PREFERENCES.jarvis_voice),
      direct_answers: asBoolean(source.direct_answers, DEFAULT_PREFERENCES.direct_answers),
      deep_thinking: asBoolean(source.deep_thinking, DEFAULT_PREFERENCES.deep_thinking),
      chat_history_enabled: asBoolean(source.chat_history_enabled, DEFAULT_PREFERENCES.chat_history_enabled)
    };
  }

  function asBoolean(value, fallback) {
    if (typeof value === 'boolean') return value;
    if (value === undefined || value === null) return fallback;
    return !['0', 'false', 'no', 'off', ''].includes(String(value).trim().toLowerCase());
  }

  function option(value, label, current) {
    return `<option value="${escapeHtml(value)}" ${value === current ? 'selected' : ''}>${label}</option>`;
  }

  function isValidEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || '').trim());
  }

  function isAdminUser(user) {
    if (!user) return false;
    return user.is_admin === true || user.isAdmin === true;
  }

  function clearAuthErrors() {
    els.authModalContent?.querySelectorAll('.auth-error').forEach(item => {
      item.textContent = '';
    });
  }

  function setFieldError(field, message) {
    const target = els.authModalContent?.querySelector(`[data-error-for="${field}"]`);
    if (target) target.innerHTML = message;
  }

  function setAuthStatus(message, type = '') {
    const status = document.getElementById('authStatus');
    if (!status) return;
    status.textContent = message;
    status.className = `auth-status${type ? ` ${type}` : ''}`;
  }

  function setPanelStatus(message, type = '') {
    const status = document.getElementById('panelStatus');
    if (!status) return;
    status.innerHTML = message;
    status.className = `panel-status${type ? ` ${type}` : ''}`;
  }

  function formatDate(value) {
    if (!value) return 'No disponible';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'No disponible';
    return new Intl.DateTimeFormat('es-NI', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    }).format(date);
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function readStorage(key, fallback) {
    try {
      return localStorage.getItem(key) || fallback;
    } catch (error) {
      return fallback;
    }
  }

  function writeStorage(key, value) {
    try {
      if (value) localStorage.setItem(key, value);
    } catch (error) {
      return false;
    }
    return true;
  }

  function removeStorage(key) {
    try {
      localStorage.removeItem(key);
    } catch (error) {
      return false;
    }
    return true;
  }

  function readJsonStorage(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (error) {
      return fallback;
    }
  }

  function writeJsonStorage(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      return false;
    }
    return true;
  }
})();
