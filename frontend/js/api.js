// ============================================================================
// ALVI Backend API Client — js/api.js
// Handles communication with the FastAPI backend for ALVI ML features.
// Connects to local FastAPI backend (http://127.0.0.1:8765) or configured Render URL.
// ============================================================================

window.ALVI = window.ALVI || {};

(function () {
  // ==========================================================================
  // BACKEND CONFIGURATION
  // To switch to your production Render URL during final deployment, either:
  //   1. Replace DEFAULT_BACKEND_URL below with your Render URL
  //      (e.g., "https://alvi-backend.onrender.com"), OR
  //   2. Set window.ALVI_BACKEND_URL before this script loads, OR
  //   3. Call ALVI_API.setBaseUrl("https://your-service.onrender.com") in console
  // ==========================================================================
  const DEFAULT_BACKEND_URL = "http://127.0.0.1:8765";

  // Production Render URL fallback
  const PRODUCTION_RENDER_URL = "https://alvi-backend.onrender.com";

  /**
   * Resolves the active backend URL in order of priority:
   * 1. Explicit window.ALVI_BACKEND_URL override
   * 2. localStorage 'alvi_backend_url'
   * 3. Current host if frontend is hosted on Render
   * 4. DEFAULT_BACKEND_URL (http://127.0.0.1:8765)
   */
  function getBaseUrl() {
    if (window.ALVI_BACKEND_URL) {
      return window.ALVI_BACKEND_URL.replace(/\/+$/, '');
    }
    try {
      const stored = localStorage.getItem('alvi_backend_url');
      if (stored) return stored.replace(/\/+$/, '');
    } catch (_) {}

    // Check if running in a cloud/Render environment
    if (window.location && window.location.hostname.includes('onrender.com')) {
      return PRODUCTION_RENDER_URL;
    }

    return DEFAULT_BACKEND_URL;
  }

  function setBaseUrl(url) {
    if (!url) return;
    const clean = url.replace(/\/+$/, '');
    window.ALVI_BACKEND_URL = clean;
    try {
      localStorage.setItem('alvi_backend_url', clean);
    } catch (_) {}
    console.log(`[ALVI API] Backend URL updated to: ${clean}`);
  }

  // Guard flag against duplicate concurrent uploads
  let isUploading = false;
  let activeAbortController = null;

  /**
   * Check backend server health: GET /health
   * @param {number} [timeoutMs=5000] - Abort timeout in ms
   * @returns {Promise<Object>} Response JSON (e.g. { status: "healthy" })
   */
  async function checkBackend(timeoutMs = 5000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/health`, {
        method: "GET",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });
      clearTimeout(timer);

      if (!response.ok) {
        throw new Error(`Backend health check failed: HTTP ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`Backend health check timed out after ${timeoutMs}ms.`);
      }
      throw err;
    }
  }

  /**
   * Upload audio recording to the FastAPI ML feature extraction and inference pipeline:
   * POST /api/voice/analyze
   *
   * @param {Blob|File} audioBlob - The recorded audio Blob or imported File
   * @param {string} [customFilename] - Optional override filename
   * @param {number} [timeoutMs=60000] - Request timeout (default 60s for full extraction)
   * @returns {Promise<Object>} The actual backend response containing audio_summary,
   *                            79 acoustic_features, and research_prediction
   */
  async function uploadVoiceRecording(audioBlob, customFilename = null, timeoutMs = 60000) {
    if (isUploading) {
      throw new Error("An audio analysis is already in progress. Please wait for it to complete.");
    }

    if (!audioBlob || !(audioBlob instanceof Blob)) {
      throw new Error("Invalid audio input: Expected a valid audio Blob or File object.");
    }

    // Backend size limit enforcement (25 MB)
    const MAX_SIZE_BYTES = 25 * 1024 * 1024;
    if (audioBlob.size > MAX_SIZE_BYTES) {
      const sizeMb = (audioBlob.size / (1024 * 1024)).toFixed(1);
      throw new Error(`Audio file size (${sizeMb} MB) exceeds the maximum allowed limit of 25 MB.`);
    }

    if (audioBlob.size === 0) {
      throw new Error("Recorded audio is empty (0 bytes). Please record your speech and try again.");
    }

    // Resolve appropriate filename and extension
    let filename = customFilename || (audioBlob.name ? audioBlob.name : null);
    if (!filename) {
      const mime = (audioBlob.type || '').toLowerCase();
      if (mime.includes('wav')) {
        filename = 'voice_recording.wav';
      } else if (mime.includes('ogg')) {
        filename = 'voice_recording.ogg';
      } else if (mime.includes('mp4') || mime.includes('m4a')) {
        filename = 'voice_recording.m4a';
      } else if (mime.includes('mp3') || mime.includes('mpeg')) {
        filename = 'voice_recording.mp3';
      } else {
        // Default WebM container from browser MediaRecorder
        filename = 'voice_recording.webm';
      }
    }

    const formData = new FormData();
    // Exact form field name 'file'
    formData.append("file", audioBlob, filename);

    activeAbortController = new AbortController();
    const timeoutId = setTimeout(() => {
      if (activeAbortController) activeAbortController.abort();
    }, timeoutMs);

    isUploading = true;
    try {
      // NOTE: Do NOT set Content-Type header; browser must set multipart boundary automatically
      const response = await fetch(`${getBaseUrl()}/api/voice/analyze`, {
        method: "POST",
        body: formData,
        signal: activeAbortController.signal
      });
      clearTimeout(timeoutId);

      const rawText = await response.text();
      let data = null;
      try {
        data = JSON.parse(rawText);
      } catch (_) {
        data = null;
      }

      if (!response.ok) {
        let msg = `HTTP ${response.status}: `;
        if (data && data.detail) {
          msg += (typeof data.detail === 'string') ? data.detail : JSON.stringify(data.detail);
        } else {
          msg += rawText || "Unknown server error";
        }
        throw new Error(msg);
      }

      if (!data || data.status !== 'success') {
        const detail = (data && data.detail) ? data.detail : "Malformed response from server.";
        throw new Error(`Server returned unexpected format: ${detail}`);
      }

      // Validate core required response fields
      if (!data.audio_summary || !data.acoustic_features || !data.research_prediction) {
        throw new Error("Backend response missing required ML data sections.");
      }

      return data;
    } catch (err) {
      clearTimeout(timeoutId);
      if (err.name === 'AbortError') {
        throw new Error(`Audio analysis request timed out after ${timeoutMs / 1000} seconds. The backend may be busy.`);
      }
      throw err;
    } finally {
      isUploading = false;
      activeAbortController = null;
    }
  }

  /**
   * Cancel any pending voice upload request
   */
  function cancelUpload() {
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
      isUploading = false;
    }
  }

  /**
   * Fetch backend root information: GET /
   */
  async function getApiRoot() {
    const response = await fetch(`${getBaseUrl()}/`);
    if (!response.ok) throw new Error("Failed to reach API root");
    return await response.json();
  }

  /**
   * Fetch available stories catalog: GET /api/story/stories
   * @param {number} [timeoutMs=10000]
   * @returns {Promise<Object>} Catalog response
   */
  async function fetchStories(timeoutMs = 10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(`${getBaseUrl()}/api/story/stories`, {
        method: "GET",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });
      clearTimeout(timer);
      if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to load stories`);
      return await response.json();
    } catch (err) {
      clearTimeout(timer);
      throw err;
    }
  }

  /**
   * Fetch details for a specific story: GET /api/story/{story_id}
   * @param {string} storyId
   * @param {number} [timeoutMs=10000]
   * @returns {Promise<Object>} Story details
   */
  async function fetchStoryDetails(storyId, timeoutMs = 10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(`${getBaseUrl()}/api/story/${encodeURIComponent(storyId)}`, {
        method: "GET",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });
      clearTimeout(timer);
      if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to load story details`);
      return await response.json();
    } catch (err) {
      clearTimeout(timer);
      throw err;
    }
  }

  /**
   * Evaluate story recall transcript using explainable backend NLP:
   * POST /api/story/evaluate
   *
   * @param {Object} options
   * @param {string} [options.storyId="aarav_story_v1"]
   * @param {string} options.transcript
   * @param {string} [options.inputMode="speech"]
   * @param {number} [options.timingSeconds=null]
   * @param {number} [options.timeoutMs=20000]
   * @returns {Promise<Object>} Evaluated NLP metrics and composite score
   */
  async function evaluateStoryRecall({
    storyId = "aarav_story_v1",
    transcript,
    inputMode = "speech",
    timingSeconds = null,
    timeoutMs = 20000
  }) {
    if (!transcript || typeof transcript !== "string" || !transcript.trim()) {
      throw new Error("Transcript is empty. Please speak or type your story recall before evaluating.");
    }

    const payload = {
      story_id: storyId,
      transcript: transcript.trim(),
      input_mode: inputMode,
      timing_seconds: timingSeconds !== null ? Number(timingSeconds) : null
    };

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/story/evaluate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify(payload),
        signal: controller.signal
      });
      clearTimeout(timer);

      const rawText = await response.text();
      let data = null;
      try {
        data = JSON.parse(rawText);
      } catch (_) {
        data = null;
      }

      if (!response.ok) {
        let msg = `HTTP ${response.status}: `;
        if (data && data.detail) {
          msg += (typeof data.detail === 'string') ? data.detail : JSON.stringify(data.detail);
        } else {
          msg += rawText || "Story evaluation failed";
        }
        throw new Error(msg);
      }

      if (!data || data.status !== 'success' || !data.data) {
        throw new Error("Malformed response received from story evaluation service.");
      }

      return data.data;
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`Story evaluation timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  /**
   * Fetch MindPlay challenges catalog: GET /api/games/catalog
   * @param {number} [timeoutMs=10000]
   * @returns {Promise<Object>} Catalog response
   */
  async function fetchGamesCatalog(timeoutMs = 10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(`${getBaseUrl()}/api/games/catalog`, {
        method: "GET",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });
      clearTimeout(timer);
      if (!response.ok) throw new Error(`HTTP ${response.status}: Failed to load games catalog`);
      return await response.json();
    } catch (err) {
      clearTimeout(timer);
      throw err;
    }
  }

  /**
   * Submit completed MindPlay session for deterministic scoring:
   * POST /api/games/submit
   *
   * @param {Object} payload
   * @param {string} [payload.session_id]
   * @param {string[]} payload.ch1_selected
   * @param {number[]} payload.ch2_sequence
   * @param {string} payload.ch3_selected
   * @param {number} [payload.ch3_reaction_ms]
   * @param {number} [payload.total_time_seconds]
   * @param {Object} [payload.interaction_metadata]
   * @param {number} [timeoutMs=15000]
   * @returns {Promise<Object>} Evaluated challenge and session scores
   */
  async function submitMindplaySession(payload, timeoutMs = 15000) {
    if (!payload || typeof payload !== 'object') {
      throw new Error("Invalid MindPlay payload provided.");
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/games/submit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify(payload),
        signal: controller.signal
      });
      clearTimeout(timer);

      const rawText = await response.text();
      let data = null;
      try {
        data = JSON.parse(rawText);
      } catch (_) {
        data = null;
      }

      if (!response.ok) {
        let msg = `HTTP ${response.status}: `;
        if (data && data.detail) {
          msg += (typeof data.detail === 'string') ? data.detail : JSON.stringify(data.detail);
        } else {
          msg += rawText || "MindPlay submission failed";
        }
        throw new Error(msg);
      }

      if (!data || data.status !== 'success' || !data.data) {
        throw new Error("Malformed response received from MindPlay scoring service.");
      }

      return data.data;
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`MindPlay submission timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  /**
   * Analyze multi-session history for personal cognitive baseline & trajectory:
   * POST /api/games/analyze-history
   *
   * @param {Array<Object>} sessions - List of past completed MindPlay sessions
   * @param {number} [timeoutMs=15000]
   * @returns {Promise<Object>} Personalized analytics & trajectory report
   */
  async function analyzeMindplayHistory(sessions, timeoutMs = 15000) {
    if (!Array.isArray(sessions)) {
      throw new Error("Expected sessions to be an array of past game results.");
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/games/analyze-history`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({ sessions }),
        signal: controller.signal
      });
      clearTimeout(timer);

      const rawText = await response.text();
      let data = null;
      try {
        data = JSON.parse(rawText);
      } catch (_) {
        data = null;
      }

      if (!response.ok) {
        let msg = `HTTP ${response.status}: `;
        if (data && data.detail) {
          msg += (typeof data.detail === 'string') ? data.detail : JSON.stringify(data.detail);
        } else {
          msg += rawText || "MindPlay history analysis failed";
        }
        throw new Error(msg);
      }

      return (data && data.data) ? data.data : data;
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`MindPlay history analysis timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  /**
   * Fetch empirical research reference statistics:
   * GET /api/cases/reference-stats
   *
   * @param {number} [timeoutMs=10000]
   * @returns {Promise<Object>} Descriptive acoustic reference distribution from cleaned DementiaNet corpus
   */
  async function fetchReferenceStats(timeoutMs = 10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/cases/reference-stats`, {
        method: "GET",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });
      clearTimeout(timer);

      if (!response.ok) {
        throw new Error(`Failed to fetch reference statistics: HTTP ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`Reference statistics request timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  /**
   * Compare session cases across multi-modal evaluation modes:
   * POST /api/cases/compare
   *
   * @param {Object} payload - { currentSession, historySessions }
   * @param {number} [timeoutMs=15000]
   * @returns {Promise<Object>} Comparison result package (Mode A, Mode B, Mode C)
   */
  async function compareSessionCases({ currentSession, historySessions = [] }, timeoutMs = 15000) {
    if (!currentSession || typeof currentSession !== 'object') {
      throw new Error("Expected currentSession to be an active session object.");
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/cases/compare`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({
          current_session: currentSession,
          history_sessions: Array.isArray(historySessions) ? historySessions : []
        }),
        signal: controller.signal
      });
      clearTimeout(timer);

      const rawText = await response.text();
      let data = null;
      try {
        data = JSON.parse(rawText);
      } catch (_) {
        data = null;
      }

      if (!response.ok) {
        let msg = `HTTP ${response.status}: `;
        if (data && data.detail) {
          msg += (typeof data.detail === 'string') ? data.detail : JSON.stringify(data.detail);
        } else {
          msg += rawText || "Case comparison failed";
        }
        throw new Error(msg);
      }

      return data;
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`Case comparison timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  /**
   * Fetch the structured cognitive practice exercise catalog:
   * GET /api/learning/catalog
   *
   * @param {number} [timeoutMs=10000]
   * @returns {Promise<Object>} Exercise catalog object
   */
  async function fetchLearningCatalog(timeoutMs = 10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/learning/catalog`, {
        method: "GET",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });
      clearTimeout(timer);

      if (!response.ok) {
        throw new Error(`Failed to fetch exercise catalog: HTTP ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`Catalog request timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  /**
   * Request personalized practice recommendations:
   * POST /api/learning/recommend
   *
   * @param {Object} payload - { currentSession, historySessions, practiceHistory }
   * @param {number} [timeoutMs=15000]
   * @returns {Promise<Object>} Recommendation results package
   */
  async function getLearningRecommendations({ currentSession = null, historySessions = [], practiceHistory = [] } = {}, timeoutMs = 15000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/learning/recommend`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({
          current_session: currentSession,
          history_sessions: Array.isArray(historySessions) ? historySessions : [],
          practice_history: Array.isArray(practiceHistory) ? practiceHistory : []
        }),
        signal: controller.signal
      });
      clearTimeout(timer);

      const rawText = await response.text();
      let data = null;
      try {
        data = JSON.parse(rawText);
      } catch (_) {
        data = null;
      }

      if (!response.ok) {
        let msg = `HTTP ${response.status}: `;
        if (data && data.detail) {
          msg += (typeof data.detail === 'string') ? data.detail : JSON.stringify(data.detail);
        } else {
          msg += rawText || "Recommendation request failed";
        }
        throw new Error(msg);
      }

      return data;
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`Recommendation request timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  /**
   * Analyze practice progress and personal bests:
   * POST /api/learning/progress
   *
   * @param {Object} payload - { practiceRecords }
   * @param {number} [timeoutMs=10000]
   * @returns {Promise<Object>} Practice progress summary
   */
  async function analyzePracticeProgress({ practiceRecords = [] } = {}, timeoutMs = 10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/learning/progress`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({
          practice_records: Array.isArray(practiceRecords) ? practiceRecords : []
        }),
        signal: controller.signal
      });
      clearTimeout(timer);

      const rawText = await response.text();
      let data = null;
      try {
        data = JSON.parse(rawText);
      } catch (_) {
        data = null;
      }

      if (!response.ok) {
        let msg = `HTTP ${response.status}: `;
        if (data && data.detail) {
          msg += (typeof data.detail === 'string') ? data.detail : JSON.stringify(data.detail);
        } else {
          msg += rawText || "Progress analysis failed";
        }
        throw new Error(msg);
      }

      return data;
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`Progress analysis timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  // ── Phase 10: Pattern Explorer & Longitudinal Analytics Client Methods ───────
  /**
   * Fetch available metrics catalog:
   * GET /api/patterns/metrics
   */
  async function fetchPatternMetrics(timeoutMs = 15000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/patterns/metrics`, {
        method: "GET",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });
      clearTimeout(timer);

      const rawText = await response.text();
      let data = null;
      try { data = JSON.parse(rawText); } catch (_) {}

      if (!response.ok) {
        let msg = `HTTP ${response.status}: `;
        if (data && data.detail) {
          msg += (typeof data.detail === 'string') ? data.detail : JSON.stringify(data.detail);
        } else {
          msg += rawText || "Failed to fetch pattern metrics";
        }
        throw new Error(msg);
      }

      return data;
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`Pattern metrics request timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  /**
   * Submit historical sessions and practice records for longitudinal pattern analysis:
   * POST /api/patterns/analyze
   * @param {Object} payload - { sessionHistory, practiceHistory, filterOptions }
   */
  async function analyzePatterns({ sessionHistory = [], practiceHistory = [], filterOptions = {} } = {}, timeoutMs = 15000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/patterns/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({
          session_history: Array.isArray(sessionHistory) ? sessionHistory : [],
          practice_history: Array.isArray(practiceHistory) ? practiceHistory : [],
          filter_options: filterOptions || {}
        }),
        signal: controller.signal
      });
      clearTimeout(timer);

      const rawText = await response.text();
      let data = null;
      try { data = JSON.parse(rawText); } catch (_) {}

      if (!response.ok) {
        let msg = `HTTP ${response.status}: `;
        if (data && data.detail) {
          msg += (typeof data.detail === 'string') ? data.detail : JSON.stringify(data.detail);
        } else {
          msg += rawText || "Pattern analysis failed";
        }
        throw new Error(msg);
      }

      return data;
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`Pattern analysis timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  /**
   * Phase 11 — Fetch Gemma 4 AI Insights Service Status:
   * GET /api/insights/status
   * @param {number} [timeoutMs=5000]
   * @returns {Promise<Object>} Status object { provider, model, configured, available, version }
   */
  async function fetchInsightStatus(timeoutMs = 5000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/insights/status`, {
        method: "GET",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });
      clearTimeout(timer);

      if (!response.ok) {
        throw new Error(`Failed to fetch AI insights status: HTTP ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`AI insights status check timed out after ${timeoutMs}ms.`);
      }
      throw err;
    }
  }

  /**
   * Phase 11 — Generate Gemma 4 AI Insights grounded in authentic measurements:
   * POST /api/insights/generate
   *
   * @param {Object} params
   * @param {Object} [params.currentSession] - Current check-in session metrics
   * @param {Array} [params.historySessions] - Longitudinal prior sessions
   * @param {Array} [params.practiceHistory] - Completed practice records
   * @param {Object} [params.learningRecommendations] - Learning path recommendations
   * @param {boolean} [params.userConsent=true] - Explicit consent to analyze data with AI
   * @param {number} [timeoutMs=45000] - Request timeout (default 45s for LLM inference)
   * @returns {Promise<Object>} Validated structured AI explanation
   */
  async function generateInsights({
    currentSession = null,
    historySessions = [],
    practiceHistory = [],
    learningRecommendations = null,
    userConsent = true
  } = {}, timeoutMs = 45000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/insights/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({
          current_session: currentSession,
          history_sessions: Array.isArray(historySessions) ? historySessions : [],
          practice_history: Array.isArray(practiceHistory) ? practiceHistory : [],
          learning_recommendations: learningRecommendations,
          user_consent: Boolean(userConsent)
        }),
        signal: controller.signal
      });
      clearTimeout(timer);

      const rawText = await response.text();
      let data = null;
      try { data = JSON.parse(rawText); } catch (_) {}

      if (!response.ok) {
        let msg = `HTTP ${response.status}: `;
        if (data && data.detail) {
          msg += (typeof data.detail === 'string') ? data.detail : JSON.stringify(data.detail);
        } else {
          msg += rawText || "AI Insights generation failed.";
        }
        throw new Error(msg);
      }

      return data;
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`AI Insights generation timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  /**
   * Phase 11 — Chat with Gemma 4 Cognitive Assistant:
   * POST /api/insights/chat
   *
   * @param {Object} params
   * @param {string} params.question - Inquiry text
   * @param {Object} [params.currentSession] - Current session metrics
   * @param {Array} [params.historySessions] - Longitudinal prior sessions
   * @param {Array} [params.chatHistory] - Recent conversation turns
   * @param {boolean} [params.userConsent=true] - User consent flag
   * @param {number} [timeoutMs=30000] - Request timeout
   * @returns {Promise<Object>} Assistant reply and disclaimer
   */
  async function sendInsightChatMessage({
    question,
    currentSession = null,
    historySessions = [],
    chatHistory = [],
    userConsent = true
  } = {}, timeoutMs = 30000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${getBaseUrl()}/api/insights/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({
          question: String(question || '').trim(),
          current_session: currentSession,
          history_sessions: Array.isArray(historySessions) ? historySessions : [],
          chat_history: Array.isArray(chatHistory) ? chatHistory : [],
          user_consent: Boolean(userConsent)
        }),
        signal: controller.signal
      });
      clearTimeout(timer);

      const rawText = await response.text();
      let data = null;
      try { data = JSON.parse(rawText); } catch (_) {}

      if (!response.ok) {
        let msg = `HTTP ${response.status}: `;
        if (data && data.detail) {
          msg += (typeof data.detail === 'string') ? data.detail : JSON.stringify(data.detail);
        } else {
          msg += rawText || "AI chat request failed.";
        }
        throw new Error(msg);
      }

      return data;
    } catch (err) {
      clearTimeout(timer);
      if (err.name === 'AbortError') {
        throw new Error(`AI chat response timed out after ${timeoutMs / 1000} seconds.`);
      }
      throw err;
    }
  }

  // Unified API export
  const ALVI_API = {
    getBaseUrl,
    setBaseUrl,
    checkBackend,
    uploadVoiceRecording,
    cancelUpload,
    getApiRoot,
    fetchStories,
    fetchStoryDetails,
    evaluateStoryRecall,
    fetchGamesCatalog,
    submitMindplaySession,
    analyzeMindplayHistory,
    fetchReferenceStats,
    compareSessionCases,
    fetchLearningCatalog,
    getLearningRecommendations,
    analyzePracticeProgress,
    fetchPatternMetrics,
    analyzePatterns,
    fetchInsightStatus,
    generateInsights,
    sendInsightChatMessage,
    get isUploading() { return isUploading; }
  };

  // Expose to both window.ALVI_API and window.ALVI.api for backwards compatibility
  window.ALVI_API = ALVI_API;
  window.ALVI.api = ALVI_API;
})();
