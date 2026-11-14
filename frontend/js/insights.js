// ─────────────────────────────────────────────────────────────────────────────
// ALVI Gemma 4 AI Insights & Explanation Engine — js/insights.js
// ─────────────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  let isGenerating = false;
  let isChatting = false;
  let chatHistory = [];
  let latestInsightData = null;

  // ── 1. DOM Element References ───────────────────────────────────────────────
  const btnGenerate = document.getElementById('btn-generate-insights');
  const btnSpinner = document.getElementById('btn-generate-spinner');
  const btnGenText = document.getElementById('btn-generate-text');
  const lastGenTimeEl = document.getElementById('last-generated-time');
  const consentCheckbox = document.getElementById('user-consent-checkbox');
  const aiModelLabel = document.getElementById('ai-model-label');
  const aiStatusDot = document.getElementById('ai-status-dot');
  const aiOfflineBadge = document.getElementById('ai-offline-badge');

  // Tab elements
  const tabBtnInsights = document.getElementById('tab-btn-insights');
  const tabBtnChat = document.getElementById('tab-btn-chat');
  const tabBtnGround = document.getElementById('tab-btn-ground');
  const tabContentInsights = document.getElementById('tab-content-insights');
  const tabContentChat = document.getElementById('tab-content-chat');
  const tabContentGround = document.getElementById('tab-content-ground');

  // Explanation elements
  const overviewTextEl = document.getElementById('overview-text');
  const voiceObsTextEl = document.getElementById('voice-obs-text');
  const memoryObsTextEl = document.getElementById('memory-obs-text');
  const execObsTextEl = document.getElementById('exec-obs-text');
  const strengthsListEl = document.getElementById('strengths-list');
  const growthListEl = document.getElementById('growth-list');
  const focusListEl = document.getElementById('focus-list');
  const groundJsonDisplay = document.getElementById('ground-json-display');
  const disclaimerTextEl = document.getElementById('disclaimer-text');

  // Key metric badges & stats
  const voiceBadge = document.getElementById('voice-metric-badge');
  const storyBadge = document.getElementById('story-metric-badge');
  const mindplayBadge = document.getElementById('mindplay-metric-badge');
  const voiceF0Val = document.getElementById('voice-f0-val');
  const voicePauseVal = document.getElementById('voice-pause-val');
  const voiceDurVal = document.getElementById('voice-dur-val');
  const storyScoreVal = document.getElementById('story-score-val');
  const storyRecalledVal = document.getElementById('story-recalled-val');
  const storyMissedVal = document.getElementById('story-missed-val');
  const mpBindingVal = document.getElementById('mp-binding-val');
  const mpSeqVal = document.getElementById('mp-seq-val');
  const mpLatencyVal = document.getElementById('mp-latency-val');

  // Chat elements
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const btnSendChat = document.getElementById('btn-send-chat');
  const chatMessagesContainer = document.getElementById('chat-messages-container');
  const btnClearChat = document.getElementById('btn-clear-chat');
  const quickChips = document.querySelectorAll('.quick-chip');

  // ── 2. Storage Helpers ──────────────────────────────────────────────────────
  function getCurrentSession() {
    if (window.ALVI && window.ALVI.session && typeof window.ALVI.session.get === 'function') {
      return window.ALVI.session.get();
    }
    return null;
  }

  function getSessionHistory() {
    try {
      const stored = localStorage.getItem('alvi_session_history');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (_) {}
    return [];
  }

  function getPracticeHistory() {
    try {
      const stored = localStorage.getItem('alvi_practice_history');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (_) {}
    return [];
  }

  // ── 3. Tab Switching Setup ──────────────────────────────────────────────────
  function switchTab(target) {
    [tabBtnInsights, tabBtnChat, tabBtnGround].forEach(b => {
      b.classList.remove('border-indigo-600', 'text-indigo-600');
      b.classList.add('border-transparent', 'text-slate-500');
    });
    [tabContentInsights, tabContentChat, tabContentGround].forEach(c => c.classList.add('hidden'));

    if (target === 'chat') {
      tabBtnChat.classList.remove('border-transparent', 'text-slate-500');
      tabBtnChat.classList.add('border-indigo-600', 'text-indigo-600');
      tabContentChat.classList.remove('hidden');
      chatInput?.focus();
    } else if (target === 'ground') {
      tabBtnGround.classList.remove('border-transparent', 'text-slate-500');
      tabBtnGround.classList.add('border-indigo-600', 'text-indigo-600');
      tabContentGround.classList.remove('hidden');
    } else {
      tabBtnInsights.classList.remove('border-transparent', 'text-slate-500');
      tabBtnInsights.classList.add('border-indigo-600', 'text-indigo-600');
      tabContentInsights.classList.remove('hidden');
    }
  }

  tabBtnInsights?.addEventListener('click', () => switchTab('insights'));
  tabBtnChat?.addEventListener('click', () => switchTab('chat'));
  tabBtnGround?.addEventListener('click', () => switchTab('ground'));

  // ── 4. Initial Status & Metrics Hydration ───────────────────────────────────
  // Restore consent preference
  try {
    const savedConsent = localStorage.getItem('alvi_ai_consent');
    if (savedConsent !== null && consentCheckbox) {
      consentCheckbox.checked = savedConsent === 'true';
    }
  } catch (_) {}

  consentCheckbox?.addEventListener('change', () => {
    try {
      localStorage.setItem('alvi_ai_consent', String(consentCheckbox.checked));
    } catch (_) {}
  });

  // Check Backend AI Provider Status
  async function checkAIStatus() {
    const api = window.ALVI_API || (window.ALVI && window.ALVI.api);
    if (!api || typeof api.fetchInsightStatus !== 'function') return;

    try {
      const statusData = await api.fetchInsightStatus();
      if (statusData && statusData.model) {
        if (aiModelLabel) aiModelLabel.textContent = statusData.model;
      }
      if (statusData.configured && statusData.available) {
        if (aiStatusDot) {
          aiStatusDot.className = 'w-2 h-2 rounded-full bg-emerald-500 animate-pulse';
        }
        if (aiOfflineBadge) aiOfflineBadge.classList.add('hidden');
      } else {
        if (aiStatusDot) {
          aiStatusDot.className = 'w-2 h-2 rounded-full bg-amber-500';
        }
        if (aiOfflineBadge) aiOfflineBadge.classList.remove('hidden');
        if (aiModelLabel) aiModelLabel.textContent = `${statusData.model || 'Gemma 4'} (Offline Mode)`;
      }
    } catch (err) {
      console.warn('[AI Insights] Could not reach AI status endpoint:', err);
      if (aiOfflineBadge) aiOfflineBadge.classList.remove('hidden');
    }
  }

  // Populate verified numbers from current session into KPI cards immediately
  function populateCurrentMetricsFromSession() {
    const s = getCurrentSession();
    if (!s) return;

    // Voice
    if (s.voice && s.voice.completed) {
      const v = s.voice;
      const feats = v.features || v.acoustic_features || {};
      const f0 = feats.mean_f0 || feats.pitch_hz || feats.mean_pitch;
      const pauseRatio = feats.low_energy_frame_ratio || feats.pause_ratio;
      const dur = v.durationSeconds || v.audio_summary?.duration_seconds;

      if (voiceBadge) voiceBadge.textContent = 'Recorded';
      if (voiceBadge) voiceBadge.className = 'text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full';
      if (voiceF0Val) voiceF0Val.textContent = f0 ? `${Math.round(f0)} Hz` : 'Recorded';
      if (voicePauseVal) voicePauseVal.textContent = pauseRatio != null ? `${(pauseRatio * 100).toFixed(1)}%` : 'Recorded';
      if (voiceDurVal) voiceDurVal.textContent = dur ? `${Math.round(dur * 10) / 10}s` : 'Recorded';
    }

    // Story Recall
    if (s.story && (s.story.completed || s.story.score_percent != null)) {
      const st = s.story;
      const score = st.score_percent ?? st.composite_score;
      const band = st.performance_band || 'Recorded';
      const recalled = Array.isArray(st.recalled_facts) ? st.recalled_facts.length : (st.recalled_facts ?? '—');
      const missed = Array.isArray(st.missed_facts) ? st.missed_facts.length : (st.missed_facts ?? '—');

      if (storyBadge) storyBadge.textContent = `${band}`;
      if (storyBadge) storyBadge.className = 'text-[11px] font-bold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full';
      if (storyScoreVal) storyScoreVal.textContent = score != null ? `${Math.round(score)}%` : '—';
      if (storyRecalledVal) storyRecalledVal.textContent = `${recalled} units`;
      if (storyMissedVal) storyMissedVal.textContent = `${missed} units`;
    }

    // MindPlay
    if (s.mindplay && (s.mindplay.completed || s.mindplay.composite_score != null)) {
      const mp = s.mindplay;
      const score = mp.composite_score;
      const latency = mp.ch3_reactionMs || mp.ch3_reaction_ms;

      if (mindplayBadge) mindplayBadge.textContent = score != null ? `${Math.round(score)}%` : 'Recorded';
      if (mindplayBadge) mindplayBadge.className = 'text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full';
      if (mpBindingVal) mpBindingVal.textContent = mp.ch1_score != null ? `${mp.ch1_score}/2 correct` : (mp.ch1_correct ? 'Correct' : 'Partial');
      if (mpSeqVal) mpSeqVal.textContent = mp.ch2_correct ? '100% Correct' : 'Sequence Inversion';
      if (mpLatencyVal) mpLatencyVal.textContent = latency ? `${Math.round(latency)} ms` : 'Recorded';
    }
  }

  // Restore previously generated insights if available
  try {
    const cached = localStorage.getItem('alvi_latest_ai_insights');
    if (cached) {
      latestInsightData = JSON.parse(cached);
      renderInsightReport(latestInsightData);
    }
  } catch (_) {}

  await checkAIStatus();
  populateCurrentMetricsFromSession();

  // ── 5. Generate AI Insights Workflow ────────────────────────────────────────
  btnGenerate?.addEventListener('click', async () => {
    if (isGenerating) return;

    const consent = consentCheckbox ? consentCheckbox.checked : true;
    if (!consent) {
      alert('Please check the consent box to allow ALVI to analyze your assessment measurements.');
      return;
    }

    isGenerating = true;
    btnSpinner?.classList.remove('hidden');
    if (btnGenText) btnGenText.textContent = 'Synthesizing with Gemma 4...';
    btnGenerate.disabled = true;

    const currentSession = getCurrentSession();
    const historySessions = getSessionHistory();
    const practiceHistory = getPracticeHistory();

    const api = window.ALVI_API || (window.ALVI && window.ALVI.api);
    if (!api || typeof api.generateInsights !== 'function') {
      alert('ALVI API client is not loaded. Please refresh the page.');
      resetGenerateBtn();
      return;
    }

    try {
      const data = await api.generateInsights({
        currentSession,
        historySessions,
        practiceHistory,
        userConsent: consent
      });

      latestInsightData = data;
      try {
        localStorage.setItem('alvi_latest_ai_insights', JSON.stringify(data));
      } catch (_) {}

      renderInsightReport(data);

      if (lastGenTimeEl) {
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        lastGenTimeEl.textContent = `Generated at ${timeStr}`;
      }

    } catch (err) {
      console.error('[AI Insights] Generation failed:', err);
      alert(`Could not generate AI insights: ${err.message}`);
    } finally {
      resetGenerateBtn();
    }
  });

  function resetGenerateBtn() {
    isGenerating = false;
    btnSpinner?.classList.add('hidden');
    if (btnGenText) btnGenText.textContent = '✨ Re-Generate Insights';
    if (btnGenerate) btnGenerate.disabled = false;
  }

  // ── 6. Render Insights Report ───────────────────────────────────────────────
  function renderInsightReport(data) {
    if (!data) return;

    if (overviewTextEl && data.session_overview) {
      overviewTextEl.textContent = data.session_overview;
    }
    if (voiceObsTextEl && data.voice_observations) {
      voiceObsTextEl.textContent = data.voice_observations;
    }
    if (memoryObsTextEl && data.memory_observations) {
      memoryObsTextEl.textContent = data.memory_observations;
    }
    if (execObsTextEl && data.executive_observations) {
      execObsTextEl.textContent = data.executive_observations;
    }
    if (disclaimerTextEl && data.disclaimer) {
      disclaimerTextEl.textContent = data.disclaimer;
    }

    // Render Strengths
    if (strengthsListEl && Array.isArray(data.strengths)) {
      strengthsListEl.innerHTML = data.strengths.map(s => `
        <li class="flex items-start gap-2 bg-emerald-50/50 p-2.5 rounded-xl border border-emerald-100 text-emerald-900">
          <span class="font-bold text-emerald-600">✓</span> <span>${escapeHtml(s)}</span>
        </li>
      `).join('');
    }

    // Render Growth Opportunities
    if (growthListEl && Array.isArray(data.growth_opportunities)) {
      growthListEl.innerHTML = data.growth_opportunities.map(g => `
        <li class="flex items-start gap-2 bg-amber-50/50 p-2.5 rounded-xl border border-amber-100 text-amber-900">
          <span class="font-bold text-amber-600">•</span> <span>${escapeHtml(g)}</span>
        </li>
      `).join('');
    }

    // Render Recommended Focus
    if (focusListEl && Array.isArray(data.recommended_focus)) {
      focusListEl.innerHTML = data.recommended_focus.map((f, idx) => `
        <li class="p-3 rounded-2xl bg-slate-50 border border-slate-100 flex items-start gap-3">
          <span class="text-indigo-600 font-bold text-sm">${idx + 1}</span>
          <div>
            <p class="font-bold text-slate-800">${escapeHtml(f)}</p>
          </div>
        </li>
      `).join('');
    }

    // Render Grounded JSON display
    if (groundJsonDisplay && data.grounded_metrics) {
      groundJsonDisplay.textContent = JSON.stringify(data.grounded_metrics, null, 2);
    }
  }

  // ── 7. Interactive Gemma 4 Assistant Chat ──────────────────────────────────
  chatForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = chatInput?.value?.trim();
    if (!query || isChatting) return;

    await sendUserChat(query);
  });

  quickChips.forEach(chip => {
    chip.addEventListener('click', async () => {
      const text = chip.textContent.trim();
      switchTab('chat');
      await sendUserChat(text);
    });
  });

  btnClearChat?.addEventListener('click', () => {
    chatHistory = [];
    if (chatMessagesContainer) {
      chatMessagesContainer.innerHTML = `
        <div class="flex items-start gap-3">
          <div class="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
            🤖
          </div>
          <div class="bg-white p-3.5 rounded-2xl rounded-tl-none border border-slate-200 shadow-sm text-xs text-slate-800 space-y-1 max-w-xl">
            <p class="font-semibold text-indigo-700 text-[11px]">ALVI Cognitive Assistant (Gemma 4)</p>
            <p class="leading-relaxed">
              Chat history cleared. You can ask questions about your voice check-in, story recall accuracy, or MindPlay latencies anytime.
            </p>
          </div>
        </div>
      `;
    }
  });

  async function sendUserChat(question) {
    if (!question || isChatting) return;

    const consent = consentCheckbox ? consentCheckbox.checked : true;
    if (!consent) {
      alert('Please check the consent box to chat with the AI assistant.');
      return;
    }

    isChatting = true;
    if (chatInput) chatInput.value = '';
    if (btnSendChat) btnSendChat.disabled = true;

    // Append user message bubble
    appendMessageBubble('user', question);
    chatHistory.push({ role: 'user', content: question });

    // Append typing indicator bubble
    const typingId = 'typing-' + Date.now();
    appendTypingBubble(typingId);

    const api = window.ALVI_API || (window.ALVI && window.ALVI.api);
    const currentSession = getCurrentSession();
    const historySessions = getSessionHistory();

    try {
      const response = await api.sendInsightChatMessage({
        question,
        currentSession,
        historySessions,
        chatHistory,
        userConsent: consent
      });

      removeTypingBubble(typingId);
      const replyText = response.reply || 'No response returned.';
      appendMessageBubble('assistant', replyText, response.disclaimer);
      chatHistory.push({ role: 'assistant', content: replyText });

    } catch (err) {
      removeTypingBubble(typingId);
      appendMessageBubble('assistant', `⚠️ Sorry, I could not complete your request: ${err.message}. Please verify the backend is running.`);
    } finally {
      isChatting = false;
      if (btnSendChat) btnSendChat.disabled = false;
      chatInput?.focus();
    }
  }

  function appendMessageBubble(role, text, disclaimer = null) {
    if (!chatMessagesContainer) return;

    const isUser = role === 'user';
    const bubble = document.createElement('div');
    bubble.className = isUser ? 'flex items-start justify-end gap-3' : 'flex items-start gap-3';

    if (isUser) {
      bubble.innerHTML = `
        <div class="bg-indigo-600 text-white p-3.5 rounded-2xl rounded-tr-none shadow-sm text-xs leading-relaxed max-w-xl">
          <p>${escapeHtml(text)}</p>
        </div>
        <div class="w-7 h-7 rounded-lg bg-slate-800 text-white flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
          👤
        </div>
      `;
    } else {
      bubble.innerHTML = `
        <div class="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
          🤖
        </div>
        <div class="bg-white p-3.5 rounded-2xl rounded-tl-none border border-slate-200 shadow-sm text-xs text-slate-800 space-y-2 max-w-xl">
          <p class="font-semibold text-indigo-700 text-[11px]">Gemma 4 Assistant</p>
          <div class="leading-relaxed space-y-1.5">${formatMarkdownSimple(text)}</div>
          ${disclaimer ? `<p class="text-[10px] text-slate-400 border-t border-slate-100 pt-1 leading-tight">Note: Informational only. ALVI is non-diagnostic.</p>` : ''}
        </div>
      `;
    }

    chatMessagesContainer.appendChild(bubble);
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
  }

  function appendTypingBubble(id) {
    if (!chatMessagesContainer) return;
    const bubble = document.createElement('div');
    bubble.id = id;
    bubble.className = 'flex items-start gap-3';
    bubble.innerHTML = `
      <div class="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
        🤖
      </div>
      <div class="bg-white p-3.5 rounded-2xl rounded-tl-none border border-slate-200 shadow-sm text-xs text-slate-400 flex items-center space-x-1.5">
        <span class="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce"></span>
        <span class="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style="animation-delay: 0.15s"></span>
        <span class="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style="animation-delay: 0.3s"></span>
        <span class="text-[11px] text-slate-500 pl-1">Gemma is analyzing...</span>
      </div>
    `;
    chatMessagesContainer.appendChild(bubble);
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
  }

  function removeTypingBubble(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatMarkdownSimple(text) {
    const escaped = escapeHtml(text);
    return escaped
      .split('\n\n')
      .map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`)
      .join('');
  }

});
