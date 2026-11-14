// MindPlay Cognitive Challenges Script — js/mindplay.js
// ALVI Phase 7: Real Cognitive Games Telemetry & FastAPI Analytics Integration

document.addEventListener('DOMContentLoaded', () => {
  // DOM References
  const mindplayCh1 = document.getElementById('mindplay-ch1');
  const mindplayCh2 = document.getElementById('mindplay-ch2');
  const mindplayCh3 = document.getElementById('mindplay-ch3');
  const mindplaySummary = document.getElementById('mindplay-summary');

  const ch1NextBtn = document.getElementById('ch1-next-btn');
  const ch2BackBtn = document.getElementById('ch2-back-btn');
  const ch2NextBtn = document.getElementById('ch2-next-btn');
  const ch3BackBtn = document.getElementById('ch3-back-btn');
  const completeMindplayBtn = document.getElementById('complete-mindplay-btn');
  const analyzeCheckinBtn = document.getElementById('analyze-checkin-btn');

  // Summary Elements
  const summaryHeading = document.getElementById('summary-heading');
  const summarySubheading = document.getElementById('summary-subheading');
  const summaryCompositeScore = document.getElementById('summary-composite-score');
  const summaryPerformanceBand = document.getElementById('summary-performance-band');
  const summaryBandDesc = document.getElementById('summary-band-desc');
  const summaryRecallEl = document.getElementById('summary-recall');
  const summaryRecallDetail = document.getElementById('summary-recall-detail');
  const summaryPatternEl = document.getElementById('summary-pattern');
  const summaryPatternDetail = document.getElementById('summary-pattern-detail');
  const summaryReactionEl = document.getElementById('summary-reaction');
  const summaryTimeEl = document.getElementById('summary-time');
  const historySessionsCount = document.getElementById('history-sessions-count');
  const historySummaryText = document.getElementById('history-summary-text');
  const disclaimerEl = document.getElementById('mindplay-scoring-disclaimer');

  // ── High-Resolution Telemetry State ─────────────────────────────────────────
  const mindplayStartTime = performance.now();
  let ch1StartTime = performance.now();
  let ch1DurationMs = 0;
  let ch1ToggleCount = 0;

  let ch2StartTime = null;
  let ch2DurationMs = 0;
  let ch2MoveCount = 0;

  let findStartTime = null;
  let findTimerInterval = null;
  let findSelection = null;
  let findMs = null;

  let isSubmitting = false;

  // ── Challenge 1: Remember (Multi-select) ────────────────────────────────────
  const selectCards = document.querySelectorAll('.mindplay-select-card');
  const selectedCh1Items = new Set();

  selectCards.forEach(card => {
    card.addEventListener('click', () => {
      ch1ToggleCount++;
      const itemKey = card.getAttribute('data-item');
      if (selectedCh1Items.has(itemKey)) {
        selectedCh1Items.delete(itemKey);
        card.classList.remove('selected', 'border-indigo-600', 'bg-indigo-50/80');
      } else {
        selectedCh1Items.add(itemKey);
        card.classList.add('selected', 'border-indigo-600', 'bg-indigo-50/80');
      }
    });
  });

  if (ch1NextBtn) {
    ch1NextBtn.addEventListener('click', () => {
      ch1DurationMs = performance.now() - ch1StartTime;
      ch2StartTime = performance.now();

      if (mindplayCh1) mindplayCh1.classList.add('hidden');
      if (mindplayCh2) mindplayCh2.classList.remove('hidden');
      renderSequenceItems();
    });
  }

  // ── Challenge 2: Sequence (Chronological Reordering) ─────────────────────────
  const sequenceEvents = [
    { id: 1, text: 'Aarav left home', correctOrder: 1 },
    { id: 2, text: 'Aarav went to the market', correctOrder: 2 },
    { id: 3, text: 'Aarav bought apples', correctOrder: 3 },
    { id: 4, text: 'Aarav met Meera', correctOrder: 4 },
    { id: 5, text: 'Aarav returned home', correctOrder: 5 }
  ];

  // Initial scrambled order presented to user
  let currentSequence = [
    sequenceEvents[0], // 1
    sequenceEvents[2], // 3
    sequenceEvents[1], // 2
    sequenceEvents[4], // 5
    sequenceEvents[3]  // 4
  ];

  function renderSequenceItems() {
    const container = document.getElementById('sequence-items-container');
    if (!container) return;
    container.innerHTML = '';

    currentSequence.forEach((item, index) => {
      const el = document.createElement('div');
      el.className = 'seq-item p-4 rounded-2xl bg-white border-2 border-slate-200 flex items-center justify-between shadow-sm';
      el.innerHTML = `
        <div class="flex items-center space-x-3">
          <span class="w-7 h-7 rounded-full bg-amber-100 text-amber-900 flex items-center justify-center font-bold text-xs">
            ${index + 1}
          </span>
          <span class="text-sm font-semibold text-slate-800">${item.text}</span>
        </div>
        <div class="flex items-center space-x-1">
          <button class="btn-move-up p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 ${index === 0 ? 'opacity-40 cursor-not-allowed' : ''}" ${index === 0 ? 'disabled' : ''}>
            ▲
          </button>
          <button class="btn-move-down p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 ${index === currentSequence.length - 1 ? 'opacity-40 cursor-not-allowed' : ''}" ${index === currentSequence.length - 1 ? 'disabled' : ''}>
            ▼
          </button>
        </div>
      `;

      const upBtn = el.querySelector('.btn-move-up');
      if (upBtn && index > 0) {
        upBtn.addEventListener('click', () => {
          ch2MoveCount++;
          const temp = currentSequence[index];
          currentSequence[index] = currentSequence[index - 1];
          currentSequence[index - 1] = temp;
          renderSequenceItems();
        });
      }

      const downBtn = el.querySelector('.btn-move-down');
      if (downBtn && index < currentSequence.length - 1) {
        downBtn.addEventListener('click', () => {
          ch2MoveCount++;
          const temp = currentSequence[index];
          currentSequence[index] = currentSequence[index + 1];
          currentSequence[index + 1] = temp;
          renderSequenceItems();
        });
      }

      container.appendChild(el);
    });
  }

  // Pre-render
  renderSequenceItems();

  if (ch2BackBtn) {
    ch2BackBtn.addEventListener('click', () => {
      if (mindplayCh2) mindplayCh2.classList.add('hidden');
      if (mindplayCh1) mindplayCh1.classList.remove('hidden');
    });
  }

  if (ch2NextBtn) {
    ch2NextBtn.addEventListener('click', () => {
      if (ch2StartTime) ch2DurationMs = performance.now() - ch2StartTime;

      if (mindplayCh2) mindplayCh2.classList.add('hidden');
      if (mindplayCh3) {
        mindplayCh3.classList.remove('hidden');
        startFindTimer();
      }
    });
  }

  // ── Challenge 3: Find (Visual Target Discrimination) ────────────────────────
  function startFindTimer() {
    findStartTime = performance.now();
    const findTimerDisplay = document.getElementById('find-timer');
    clearInterval(findTimerInterval);
    findTimerInterval = setInterval(() => {
      const elapsed = performance.now() - findStartTime;
      const secs = (elapsed / 1000).toFixed(1);
      if (findTimerDisplay) findTimerDisplay.textContent = `00:${secs}s`;
    }, 100);
  }

  const findCards = document.querySelectorAll('.find-card');
  findCards.forEach(card => {
    card.addEventListener('click', () => {
      clearInterval(findTimerInterval);
      const item = card.getAttribute('data-find-item');
      findSelection = item;
      if (findStartTime !== null) {
        findMs = performance.now() - findStartTime;
      }
      findCards.forEach(c => c.classList.remove('selected-correct', 'selected-incorrect', 'border-emerald-500', 'bg-emerald-50', 'border-rose-500', 'bg-rose-50'));
      if (item === 'umbrella') {
        card.classList.add('selected-correct', 'border-emerald-500', 'bg-emerald-50');
      } else {
        card.classList.add('selected-incorrect', 'border-rose-500', 'bg-rose-50');
      }
    });
  });

  if (ch3BackBtn) {
    ch3BackBtn.addEventListener('click', () => {
      if (mindplayCh3) mindplayCh3.classList.add('hidden');
      if (mindplayCh2) mindplayCh2.classList.remove('hidden');
    });
  }

  // ── Complete MindPlay & FastAPI Analytics Evaluation ────────────────────────
  if (completeMindplayBtn) {
    completeMindplayBtn.addEventListener('click', async () => {
      if (isSubmitting) return;
      isSubmitting = true;

      clearInterval(findTimerInterval);
      if (findMs === null && findStartTime !== null) {
        findMs = performance.now() - findStartTime;
      }

      const totalElapsedMs = performance.now() - mindplayStartTime;
      const totalSec = parseFloat((totalElapsedMs / 1000).toFixed(1));

      // Visual Transition to Summary with Loading State
      if (mindplayCh3) mindplayCh3.classList.add('hidden');
      if (mindplaySummary) mindplaySummary.classList.remove('hidden');

      if (summaryHeading) summaryHeading.textContent = 'ANALYZING COGNITIVE RESPONSES...';
      if (summarySubheading) summarySubheading.textContent = 'Transmitting game telemetry to ALVI FastAPI analytics engine…';
      if (summaryCompositeScore) summaryCompositeScore.textContent = 'Score: Evaluating…';

      // Assemble Telemetry Payload
      const ch1_selected = Array.from(selectedCh1Items);
      const ch2_sequence = currentSequence.map(item => item.id);
      const ch3_reaction_ms = findMs !== null ? Math.round(findMs) : null;
      const sessionId = (window.ALVI && window.ALVI.session) ? window.ALVI.session.get().sessionId : ('mp_' + Date.now());

      const payload = {
        session_id: sessionId,
        ch1_selected: ch1_selected,
        ch2_sequence: ch2_sequence,
        ch3_selected: findSelection,
        ch3_reaction_ms: ch3_reaction_ms,
        total_time_seconds: totalSec,
        interaction_metadata: {
          ch1_toggle_count: ch1ToggleCount,
          ch1_duration_ms: Math.round(ch1DurationMs),
          ch2_move_count: ch2MoveCount,
          ch2_duration_ms: Math.round(ch2DurationMs),
          ch3_duration_ms: ch3_reaction_ms
        }
      };

      try {
        if (!window.ALVI_API || typeof window.ALVI_API.submitMindplaySession !== 'function') {
          throw new Error('ALVI_API client is not loaded. Please verify api.js inclusion.');
        }

        // 1. Submit current session to FastAPI backend
        const result = await window.ALVI_API.submitMindplaySession(payload);

        // 2. Fetch or update personal session history in localStorage
        let historyArray = [];
        try {
          const stored = localStorage.getItem('alvi_mindplay_history');
          if (stored) historyArray = JSON.parse(stored);
        } catch (_) {}
        if (!Array.isArray(historyArray)) historyArray = [];

        // Append current attempt
        historyArray.push({
          session_id: sessionId,
          composite_score: result.composite_score,
          total_time_seconds: totalSec,
          ch3_reaction_ms: ch3_reaction_ms,
          timestamp: new Date().toISOString()
        });

        try {
          localStorage.setItem('alvi_mindplay_history', JSON.stringify(historyArray));
        } catch (_) {}

        // 3. Request multi-session trajectory analytics
        let historyAnalysis = null;
        try {
          historyAnalysis = await window.ALVI_API.analyzeMindplayHistory(historyArray);
        } catch (hErr) {
          console.warn('[MindPlay History] Analysis error:', hErr);
        }

        // 4. Render Real Backend Analytics on UI
        if (summaryHeading) summaryHeading.textContent = 'MINDPLAY COMPLETE';
        if (summarySubheading) summarySubheading.textContent = 'Your cognitive responses have been processed by the ALVI analytics engine.';

        if (summaryCompositeScore) {
          summaryCompositeScore.textContent = `Score: ${result.composite_score}%`;
        }

        if (summaryPerformanceBand) {
          summaryPerformanceBand.textContent = result.performance_band;
          summaryPerformanceBand.className = result.composite_score >= 85
            ? 'text-xs font-bold px-3.5 py-1 rounded-full bg-emerald-600 text-white shadow-xs'
            : (result.composite_score >= 65
              ? 'text-xs font-bold px-3.5 py-1 rounded-full bg-teal-600 text-white shadow-xs'
              : (result.composite_score >= 40
                ? 'text-xs font-bold px-3.5 py-1 rounded-full bg-amber-600 text-white shadow-xs'
                : 'text-xs font-bold px-3.5 py-1 rounded-full bg-rose-600 text-white shadow-xs'));
        }

        if (summaryBandDesc) {
          summaryBandDesc.textContent = result.band_description || '';
        }

        // Grid cards
        if (summaryRecallEl) summaryRecallEl.textContent = `${result.challenges.ch1_remember.ch1_score}/2`;
        if (summaryRecallDetail) {
          summaryRecallDetail.textContent = `Points: ${result.challenges.ch1_remember.raw_points} / 2.0`;
        }

        if (summaryPatternEl) {
          summaryPatternEl.textContent = result.challenges.ch2_sequence.is_correct ? 'Correct' : 'Incorrect';
        }
        if (summaryPatternDetail) {
          const invs = result.challenges.ch2_sequence.inversions_count;
          summaryPatternDetail.textContent = `${invs} Inversion${invs === 1 ? '' : 's'}`;
        }

        if (summaryReactionEl) {
          summaryReactionEl.textContent = result.challenges.ch3_find.reaction_time_ms !== null
            ? `${Math.round(result.challenges.ch3_find.reaction_time_ms)}ms`
            : '—';
        }
        if (summaryTimeEl) summaryTimeEl.textContent = `Total: ${totalSec}s`;

        // Personal History Box
        if (historySessionsCount && historySummaryText) {
          if (historyAnalysis && historyAnalysis.has_baseline) {
            historySessionsCount.textContent = `${historyAnalysis.sessions_evaluated} sessions`;
            const bl = historyAnalysis.personal_baseline;
            const tr = historyAnalysis.trajectory;
            historySummaryText.textContent = `Baseline: ${bl.mean_score}% (${bl.consistency_label}) · Trajectory: ${tr.label} (${tr.score_delta >= 0 ? '+' : ''}${tr.score_delta} pts)`;
          } else {
            historySessionsCount.textContent = 'Session 1';
            historySummaryText.textContent = 'First check-in recorded. Complete 2 or more sessions to establish a personal baseline trajectory.';
          }
        }

        if (disclaimerEl) {
          disclaimerEl.textContent = result.disclaimer || '';
        }

        // 5. Persist to Session for Case Comparison & Downstream Pages
        if (window.ALVI && window.ALVI.session) {
          window.ALVI.session.saveMindplay({
            ch1_selected: ch1_selected,
            ch1_correct: result.challenges.ch1_remember.is_correct,
            ch1_score: result.challenges.ch1_remember.ch1_score,
            ch2_correct: result.challenges.ch2_sequence.is_correct,
            ch3_correct: result.challenges.ch3_find.is_correct,
            ch3_reactionMs: result.challenges.ch3_find.reaction_time_ms,
            completed: true,
            total_time_seconds: totalSec,
            composite_score: result.composite_score,
            performance_band: result.performance_band,
            challenges: result.challenges,
            history_analytics: historyAnalysis,
            disclaimer: result.disclaimer
          });

          if (typeof window.ALVI.session.recordPracticeCompletion === 'function') {
            window.ALVI.session.recordPracticeCompletion({
              exerciseId: 'ex_temporal_chronology_builder',
              exerciseTitle: 'Story Chronology & Temporal Sequencing',
              domain: 'executive_sequencing',
              score: result.composite_score,
              durationSeconds: totalSec,
              isDemo: false
            });
          }
        }

      } catch (err) {
        console.error('[MindPlay Analytics] Backend submission error:', err);

        // Graceful Client-side Fallback
        const correctItems = new Set(['umbrella', 'apples']);
        const ch1_score = ch1_selected.filter(i => correctItems.has(i)).length;
        const ch1_correct = ch1_score === 2 && selectedCh1Items.size === 2;
        const ch2_correct = currentSequence.every((item, idx) => item.correctOrder === idx + 1);
        const ch3_correct = findSelection === 'umbrella';
        const ch3_reactionMs = findMs !== null ? Math.round(findMs) : null;

        if (summaryHeading) summaryHeading.textContent = 'MINDPLAY COMPLETE';
        if (summarySubheading) summarySubheading.textContent = 'Scored locally (Backend at http://127.0.0.1:8765 was unreachable).';
        if (summaryCompositeScore) summaryCompositeScore.textContent = `Local: ${ch1_correct && ch2_correct && ch3_correct ? '100%' : 'Partial'}`;
        if (summaryRecallEl) summaryRecallEl.textContent = `${ch1_score}/2`;
        if (summaryPatternEl) summaryPatternEl.textContent = ch2_correct ? 'Correct' : 'Incorrect';
        if (summaryReactionEl) summaryReactionEl.textContent = ch3_reactionMs ? `${ch3_reactionMs}ms` : '—';
        if (summaryTimeEl) summaryTimeEl.textContent = `Total: ${totalSec}s`;

        if (window.ALVI && window.ALVI.session) {
          window.ALVI.session.saveMindplay({
            ch1_selected,
            ch1_correct,
            ch1_score,
            ch2_correct,
            ch3_correct,
            ch3_reactionMs,
            completed: true,
            total_time_seconds: totalSec
          });
        }
      } finally {
        isSubmitting = false;
      }
    });
  }

  if (analyzeCheckinBtn) {
    analyzeCheckinBtn.addEventListener('click', () => {
      window.location.href = 'analysis.html';
    });
  }
});
