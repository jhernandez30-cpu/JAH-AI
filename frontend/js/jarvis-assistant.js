(function () {
  const DEFAULT_CONFIG = {
    honorific: '',
    readResponses: true,
    stt: {
      provider: 'web-speech',
      language: 'es-NI',
      fallbackLanguage: 'es-ES',
      localProvidersReadyForPhase2: ['faster-whisper', 'vosk', 'speechrecognition']
    },
    tts: {
      provider: 'speech-synthesis',
      langFallbacks: ['es-NI', 'es-ES', 'es-MX', 'es'],
      rate: 1,
      pitch: 0.9,
      volume: 1,
      maxChars: 1300,
      codeNotice: 'La respuesta incluye código. Te recomiendo revisarlo en pantalla.'
    },
    messages: {
      listening: 'Jarvis escuchando...',
      recognizing: 'Reconociendo voz...',
      detected: 'Texto detectado...',
      sending: 'Enviando al cerebro tutor_ia...',
      processing: 'Jarvis procesando...',
      speaking: 'Jarvis hablando...',
      ready: 'Listo.',
      noSpeech: 'No escuché nada. Intenta de nuevo.',
      micBlocked: 'Permiso de micrófono denegado.',
      micMissing: 'No detecté micrófono conectado.',
      unsupported: 'Tu navegador no soporta reconocimiento de voz. Probá con Google Chrome o Microsoft Edge.',
      network: 'Jarvis no pudo escuchar. Puedes escribir tu mensaje.',
      retry: 'Jarvis no pudo escuchar. Intenta nuevamente.',
      localServer: 'Para usar el micrófono, abre el asistente con Live Server o http://localhost.',
      busy: 'Espera a que termine la respuesta actual.',
      thinking: 'Jarvis procesando...',
      unavailable: 'Esa función todavía no está disponible.',
      help: 'Di: limpia el chat, adjuntar archivo, activa búsqueda inteligente o detén la voz.'
    }
  };

  function mergeConfig(base, overrides) {
    const output = { ...base, ...(overrides || {}) };
    output.stt = { ...base.stt, ...((overrides && overrides.stt) || {}) };
    output.tts = { ...base.tts, ...((overrides && overrides.tts) || {}) };
    output.messages = { ...base.messages, ...((overrides && overrides.messages) || {}) };
    return output;
  }

  function normalizeCommand(text) {
    return String(text || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[¿?¡!.,;:]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function shorten(text, maxLength = 84) {
    const clean = String(text || '').replace(/\s+/g, ' ').trim();
    return clean.length > maxLength ? `${clean.slice(0, maxLength - 1).trim()}...` : clean;
  }

  function hasLongCode(text) {
    const raw = String(text || '');
    if (/```[\s\S]*?```/.test(raw)) return true;
    const codeLikeLines = raw.split('\n').filter(line => {
      const trimmed = line.trim();
      return /^(const|let|var|function|class|import|from|def|SELECT|CREATE|INSERT|UPDATE|DELETE|<\w+|<\/\w+)/i.test(trimmed);
    });
    return codeLikeLines.length >= 4;
  }

  function cleanTextForSpeech(text) {
    return String(text || '')
      .replace(/```[\s\S]*?```/g, ' bloque de código disponible en pantalla. ')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/(?:Fuentes usadas|Fuentes consultadas|Sources used|Sources consulted):[\s\S]*$/i, ' ')
      .replace(/https?:\/\/\S+/g, ' enlace disponible en pantalla ')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/[#*_>\[\]{}()]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function create(options = {}) {
    const config = mergeConfig(DEFAULT_CONFIG, options.config || {});
    const elements = options.elements || {};
    const callbacks = options.callbacks || {};
    const state = options.state || {};

    const button = elements.button || null;
    const status = elements.status || null;
    const input = elements.input || null;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    let recognition = null;
    let isListening = false;
    let isStarting = false;
    let startRequestId = 0;
    let statusTimeout = null;
    let hadResult = false;
    let hadError = false;
    let readResponses = Boolean(config.readResponses);

    function clearStatus() {
      if (!status) return;
      window.clearTimeout(statusTimeout);
      status.textContent = '';
      status.removeAttribute('title');
      status.className = 'jarvis-status';
      if (button) button.classList.remove('error');
    }

    function showStatus(message, type = 'info', autoHideMs = type === 'info' ? 0 : 4000) {
      if (!status) return;
      window.clearTimeout(statusTimeout);
      status.textContent = message;
      status.title = message;
      status.className = `jarvis-status ${type}`;
      if (button) button.classList.toggle('error', type === 'error');

      if (autoHideMs > 0) {
        statusTimeout = window.setTimeout(clearStatus, autoHideMs);
      }
    }

    function setButtonListening(next) {
      isListening = Boolean(next);
      if (!button) return;
      const label = button.querySelector('.jarvis-voice-label');
      button.classList.toggle('listening', isListening);
      button.setAttribute('aria-pressed', String(isListening));
      button.setAttribute('title', isListening ? 'Detener escucha de Jarvis' : 'Usa Chrome o Edge y permite el micrófono.');
      if (label) label.textContent = isListening ? 'Escuchando' : 'Jarvis';
    }

    function setReadResponses(next) {
      readResponses = Boolean(next);
      try {
        localStorage.setItem('jarvisReadResponses', String(readResponses));
      } catch (error) {
        return readResponses;
      }
      return readResponses;
    }

    function stopSpeech() {
      if (window.speechSynthesis) window.speechSynthesis.cancel();
    }

    function speak(text) {
      if (!readResponses || !window.speechSynthesis || !window.SpeechSynthesisUtterance) {
        showStatus(config.messages.ready, 'success');
        return;
      }

      const speechText = hasLongCode(text)
        ? config.tts.codeNotice
        : cleanTextForSpeech(text);
      if (!speechText) {
        showStatus(config.messages.ready, 'success');
        return;
      }

      const maxChars = Number(config.tts.maxChars || 1300);
      const utterance = new SpeechSynthesisUtterance(
        speechText.length > maxChars ? `${speechText.slice(0, maxChars).trim()}. La respuesta completa está en pantalla.` : speechText
      );
      const voices = window.speechSynthesis.getVoices ? window.speechSynthesis.getVoices() : [];
      const preferredVoice = config.tts.langFallbacks
        .map(lang => voices.find(voice => String(voice.lang || '').toLowerCase().startsWith(lang.toLowerCase())))
        .find(Boolean);

      if (preferredVoice) {
        utterance.voice = preferredVoice;
        utterance.lang = preferredVoice.lang;
      } else {
        utterance.lang = config.tts.langFallbacks[1] || 'es-ES';
      }

      utterance.rate = config.tts.rate;
      utterance.pitch = config.tts.pitch;
      utterance.volume = config.tts.volume;
      utterance.onstart = () => showStatus(config.messages.speaking, 'info', 0);
      utterance.onend = () => showStatus(config.messages.ready, 'success');
      utterance.onerror = () => showStatus(config.messages.ready, 'warning');
      stopSpeech();
      window.speechSynthesis.speak(utterance);
    }

    function executeAction(actionName, fallbackMessage = config.messages.unavailable, ...args) {
      const action = callbacks[actionName];
      if (typeof action !== 'function') {
        showStatus(fallbackMessage, 'warning');
        return false;
      }
      const result = action(...args);
      if (result === false) {
        showStatus(fallbackMessage, 'warning');
        return false;
      }
      return true;
    }

    function handleCommand(transcript) {
      const command = normalizeCommand(transcript);
      if (!command.startsWith('jarvis')) return false;

      if (command.includes('ayuda')) {
        showStatus(config.messages.help, 'info', 6000);
        return true;
      }

      if (command.includes('cancela') || command.includes('cancelar')) {
        stopListening();
        stopSpeech();
        showStatus(config.messages.ready, 'success');
        return true;
      }

      if (command.includes('deten la voz') || command.includes('detener voz') || command.includes('para la voz') || command.includes('callate')) {
        stopSpeech();
        showStatus('Voz de Jarvis detenida.', 'success');
        return true;
      }

      if (command.includes('lee la respuesta')) {
        setReadResponses(true);
        const lastAnswer = typeof callbacks.getLastAssistantText === 'function' ? callbacks.getLastAssistantText() : '';
        showStatus('Lectura de respuestas activada.', 'success');
        if (lastAnswer) speak(lastAnswer);
        return true;
      }

      if (command.includes('no leas la respuesta')) {
        setReadResponses(false);
        stopSpeech();
        showStatus('Lectura de respuestas desactivada.', 'success');
        return true;
      }

      if (command.includes('limpia el chat') || command.includes('limpiar el chat') || command.includes('borra la conversacion') || command.includes('borra conversación')) {
        executeAction('clearChat');
        showStatus('Chat limpio.', 'success');
        return true;
      }

      if (command.includes('abre el selector de archivos') || command.includes('adjuntar archivo') || command.includes('adjunta archivo')) {
        if (executeAction('openFilePicker')) showStatus('Selecciona el archivo para adjuntarlo.', 'info', 4000);
        return true;
      }

      if (command.includes('desactiva busqueda inteligente')) {
        if (executeAction('setSmartSearch', config.messages.unavailable, false)) showStatus('Búsqueda inteligente desactivada.', 'success');
        return true;
      }

      if (command.includes('activa busqueda inteligente')) {
        if (executeAction('setSmartSearch', config.messages.unavailable, true)) showStatus('Búsqueda inteligente activada.', 'success');
        return true;
      }

      if (command.includes('desactiva pensamiento profundo')) {
        if (executeAction('setDeepThinking', config.messages.unavailable, false)) showStatus('Pensamiento profundo desactivado.', 'success');
        return true;
      }

      if (command.includes('activa pensamiento profundo')) {
        if (executeAction('setDeepThinking', config.messages.unavailable, true)) showStatus('Pensamiento profundo activado.', 'success');
        return true;
      }

      if (
        (command.includes('mark') || command.includes('xxxix') || command.includes('39'))
        && (command.includes('activa') || command.includes('activar') || command.includes('abre') || command.includes('inicia') || command.includes('usa'))
      ) {
        executeAction('launchMarkVoice', 'Mark XXXIX no está configurado todavía.');
        return true;
      }

      showStatus(config.messages.help, 'info', 6000);
      return true;
    }

    function handleVoiceResult(transcript) {
      const text = String(transcript || '').trim();
      if (!text) {
        showStatus(config.messages.noSpeech, 'warning');
        return;
      }

      hadResult = true;
      if (input) {
        input.value = text;
        if (typeof callbacks.autosizeInput === 'function') callbacks.autosizeInput();
        input.focus();
      }
      showStatus(`${config.messages.detected} ${shorten(text)}`, 'success', 1500);

      if (handleCommand(text)) return;
      sendMessageFromJarvis(text);
    }

    function sendMessageFromJarvis(text) {
      if (!input) {
        showStatus('No encontré el campo de mensaje.', 'error');
        return false;
      }
      input.value = String(text || '').trim();
      if (typeof callbacks.autosizeInput === 'function') callbacks.autosizeInput();
      showStatus(config.messages.sending, 'info', 0);

      if (typeof callbacks.sendMessage === 'function') {
        const result = callbacks.sendMessage(input.value);
        if (result && typeof result.then === 'function') {
          result.catch(() => showStatus('Error al usar el microfono.', 'error'));
        }
        return result;
      }

      showStatus('No encontré la función de enviar mensaje.', 'error');
      return false;
    }

    function handleError(event) {
      const code = event && event.error ? event.error : '';
      let message = config.messages.retry;
      let type = 'error';

      switch (code) {
        case 'not-allowed':
        case 'service-not-allowed':
          message = config.messages.micBlocked;
          break;
        case 'no-speech':
          message = config.messages.noSpeech;
          type = 'warning';
          break;
        case 'audio-capture':
          message = config.messages.micMissing;
          break;
        case 'network':
          message = config.messages.network;
          break;
        default:
          message = config.messages.retry;
      }

      hadError = true;
      isStarting = false;
      setButtonListening(false);
      showStatus(message, type);
    }

    function createRecognition() {
      const voiceRecognition = new SpeechRecognition();
      voiceRecognition.lang = config.stt.language;
      voiceRecognition.interimResults = false;
      voiceRecognition.continuous = false;
      voiceRecognition.maxAlternatives = 1;

      voiceRecognition.onstart = () => {
        isStarting = false;
        hadResult = false;
        hadError = false;
        setButtonListening(true);
        showStatus(config.messages.listening, 'info', 0);
      };

      voiceRecognition.onresult = event => {
        showStatus(config.messages.recognizing, 'info', 0);
        const result = event.results && event.results[0] && event.results[0][0];
        handleVoiceResult(result ? result.transcript : '');
      };

      voiceRecognition.onerror = handleError;
      voiceRecognition.onend = () => {
        isStarting = false;
        setButtonListening(false);
        if (!hadResult && !hadError) showStatus(config.messages.ready, 'success');
      };

      return voiceRecognition;
    }

    async function canUseMicrophone() {
      if (!navigator.permissions || !navigator.permissions.query) return true;

      try {
        const permission = await navigator.permissions.query({ name: 'microphone' });
        if (permission && permission.state === 'denied') {
          showStatus(config.messages.micBlocked, 'error');
          return false;
        }
      } catch (error) {
        return true;
      }

      return true;
    }

    async function startListening() {
      if (!SpeechRecognition) {
        showStatus(config.messages.unsupported, 'warning');
        return;
      }

      if (isListening || isStarting) {
        stopListening();
        return;
      }

      if (window.location.protocol === 'file:') {
        showStatus(config.messages.localServer, 'warning');
        return;
      }

      if (!window.isSecureContext && !['localhost', '127.0.0.1'].includes(window.location.hostname)) {
        showStatus(config.messages.localServer, 'warning');
        return;
      }

      if (typeof state.isSubmitting === 'function' && state.isSubmitting()) {
        showStatus(config.messages.busy, 'warning');
        return;
      }

      const requestId = ++startRequestId;
      isStarting = true;
      const microphoneAllowed = await canUseMicrophone();
      if (requestId !== startRequestId) return;
      if (!microphoneAllowed) {
        isStarting = false;
        return;
      }

      if (!recognition) recognition = createRecognition();

      try {
        stopSpeech();
        recognition.start();
      } catch (error) {
        isStarting = false;
        showStatus('Jarvis ya está escuchando.', 'warning');
      }
    }

    function stopListening() {
      startRequestId += 1;
      isStarting = false;
      if (!recognition) {
        setButtonListening(false);
        showStatus(config.messages.ready, 'success');
        return;
      }
      try {
        recognition.stop();
      } catch (error) {
        // El navegador lanza error si la escucha ya terminó.
      }
      setButtonListening(false);
      showStatus(config.messages.ready, 'success');
    }

    function init() {
      if (!button) return;

      if (!SpeechRecognition) {
        button.disabled = true;
        button.classList.add('jarvis-disabled');
        button.setAttribute('aria-disabled', 'true');
        button.title = 'Voz no disponible en este navegador.';
        showStatus(config.messages.unsupported, 'warning');
        return;
      }

      try {
        const storedRead = localStorage.getItem('jarvisReadResponses');
        if (storedRead !== null) readResponses = storedRead === 'true';
      } catch (error) {
        readResponses = Boolean(config.readResponses);
      }

      button.classList.remove('jarvis-disabled');
      button.setAttribute('aria-disabled', 'false');
      button.disabled = false;
      button.title = 'Usa Chrome o Edge y permite el micrófono.';
      recognition = createRecognition();
      button.addEventListener('click', () => {
        if (isListening || isStarting) stopListening();
        else startListening();
      });

      if (window.speechSynthesis && window.speechSynthesis.getVoices) {
        window.speechSynthesis.getVoices();
      }
    }

    init();

    return {
      startListening,
      stopListening,
      showStatus,
      clearStatus,
      handleCommand,
      handleVoiceResult,
      sendMessageFromJarvis,
      speakResponse: speak,
      stopSpeech,
      setReadResponses,
      isReadResponsesEnabled: () => readResponses,
      getProviderInfo: () => ({
        sttProvider: config.stt.provider,
        ttsProvider: config.tts.provider,
        localSttProvidersReadyForPhase2: config.stt.localProvidersReadyForPhase2.slice()
      })
    };
  }

  window.JarvisAssistant = {
    create,
    defaultConfig: DEFAULT_CONFIG,
    normalizeCommand
  };
})();
