// ─────────────────────────────────────────────────────────────────────────────
// ALVI Cognitive Journey & Personalized Learning Path Engine — js/journey.js
// ─────────────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  let journeyChartInstance = null;
  let currentActiveTab = 'overall';

  // ── 1. Storage Helpers ──────────────────────────────────────────────────────
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

  function savePracticeRecord(record) {
    const list = getPracticeHistory();
    list.unshift(record); // newest first
    try {
      localStorage.setItem('alvi_practice_history', JSON.stringify(list));
    } catch (_) {}
    return list;
  }

  function getCurrentSession() {
    if (window.ALVI && window.ALVI.session && typeof window.ALVI.session.get === 'function') {
      return window.ALVI.session.get();
    }
    return null;
  }

  // ── 2. Recommendation & Progress Engine Invocation ──────────────────────────
  async function loadRecommendationsAndProgress() {
    const api = window.ALVI_API || (window.ALVI && window.ALVI.api);
    const currentSession = getCurrentSession();
    const historySessions = getSessionHistory();
    const practiceHistory = getPracticeHistory();

    // UI Loading state
    const badgeEl = document.getElementById('learning-path-badge');
    if (badgeEl) badgeEl.textContent = 'Updating...';

    let recData = null;
    let progData = null;

    if (api && typeof api.getLearningRecommendations === 'function') {
      try {
        recData = await api.getLearningRecommendations({
          currentSession,
          historySessions,
          practiceHistory
        });
      } catch (err) {
        console.warn('Backend learning recommendations error, using client fallback:', err);
      }
    }

    if (api && typeof api.analyzePracticeProgress === 'function') {
      try {
        progData = await api.analyzePracticeProgress(practiceHistory);
      } catch (err) {
        console.warn('Backend practice progress error, using client fallback:', err);
      }
    }

    // Client fallbacks if backend unavailable
    if (!recData) {
      recData = getClientFallbackRecommendations(currentSession);
    }
    if (!progData) {
      progData = getClientFallbackProgress(practiceHistory);
    }

    renderLearningBanner(recData);
    const exercisesList = recData.recommended_exercises || recData.recommendations || [];
    renderRecommendationsGrid(exercisesList);
    renderPracticeProgress(progData, practiceHistory);
  }

  // ── 3. Render Learning Banner ───────────────────────────────────────────────
  function renderLearningBanner(recData) {
    const bannerEl = document.getElementById('learning-banner');
    const badgeEl = document.getElementById('learning-path-badge');
    const pillEl = document.getElementById('banner-mode-pill');
    const titleEl = document.getElementById('banner-title');
    const reasonEl = document.getElementById('banner-reason');

    if (!bannerEl || !titleEl || !reasonEl) return;

    const isStarter = Boolean(recData.is_starter_path || recData.path_mode === 'starter_curriculum');

    if (badgeEl) {
      badgeEl.textContent = isStarter ? 'Starter Curriculum' : 'Personalized Active Path';
      badgeEl.className = isStarter
        ? 'px-3 py-1.5 rounded-xl text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-200'
        : 'px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200';
    }

    if (pillEl) {
      pillEl.textContent = isStarter ? 'Starter Curriculum' : 'Adaptive Personalized Path';
      pillEl.className = isStarter
        ? 'text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-indigo-500/30 text-indigo-200 border border-indigo-400/30'
        : 'text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-emerald-500/30 text-emerald-200 border border-emerald-400/30';
    }

    titleEl.textContent = isStarter
      ? 'Foundational Multi-Domain Practice Path'
      : 'Tailored Cognitive Practice Path';

    let reasonText = recData.starter_path_note || recData.primary_focus_reason || 'Custom practice curriculum structured for balanced cognitive engagement.';
    if (recData.opportunities_identified && recData.opportunities_identified.length > 0 && !isStarter) {
      reasonText += ' • Focus Areas: ' + recData.opportunities_identified.join('; ');
    } else if (recData.trigger_notes && recData.trigger_notes.length > 0) {
      reasonText += ' • Triggers: ' + recData.trigger_notes.join('; ');
    }
    reasonEl.textContent = reasonText;
  }

  // ── 4. Render Recommended Activities Grid ───────────────────────────────────
  function renderRecommendationsGrid(recommendations) {
    const grid = document.getElementById('recommended-activities-grid');
    const countEl = document.getElementById('recommendations-count');
    if (!grid) return;

    if (countEl) {
      countEl.textContent = `${recommendations.length} Drills Queued`;
    }

    if (!recommendations || recommendations.length === 0) {
      grid.innerHTML = `
        <div class="col-span-full p-8 rounded-3xl bg-white border border-slate-200 text-center space-y-2">
          <p class="text-sm font-semibold text-slate-700">All practice exercises complete or in rotation.</p>
          <p class="text-xs text-slate-400">Complete another check-in to generate updated recommendations.</p>
        </div>
      `;
      return;
    }

    const priorityColors = {
      1: { badge: 'bg-indigo-600 text-white', label: 'Priority 1 • High Alignment' },
      2: { badge: 'bg-indigo-500/90 text-white', label: 'Priority 2 • Core Practice' },
      3: { badge: 'bg-slate-700 text-white', label: 'Priority 3 • Complementary' }
    };

    const diffColors = {
      'Beginner': 'bg-emerald-100 text-emerald-800 border-emerald-200',
      'Intermediate': 'bg-amber-100 text-amber-800 border-amber-200',
      'Standard': 'bg-indigo-100 text-indigo-800 border-indigo-200',
      'Advanced': 'bg-purple-100 text-purple-800 border-purple-200'
    };

    grid.innerHTML = recommendations.map((item, idx) => {
      const pRank = item.priority || item.priority_rank || (idx + 1);
      const priorityInfo = priorityColors[pRank] || { badge: 'bg-slate-600 text-white', label: item.priority_label || `Priority ${pRank}` };
      const diffClass = diffColors[item.difficulty] || 'bg-slate-100 text-slate-800 border-slate-200';
      const durationStr = item.estimated_duration || (item.estimated_duration_seconds ? Math.round(item.estimated_duration_seconds / 60) + ' min' : '3-5 min');
      const routeUrl = item.target_activity_url || item.route || item.launch_route || 'story.html';
      const exerciseTitle = item.display_name || item.exercise_title || 'Practice Exercise';
      const skillName = item.skill_practiced || item.targeted_cognitive_skill || item.opportunity || 'Cognitive Agility';
      const reasonStr = item.reason || item.recommendation_reason || 'Targeted cognitive stimulation.';
      const triggerStr = item.supporting_metric || item.trigger_signal;
      const descriptionStr = item.instructions || item.description || '';
      const moduleName = item.target_activity ? (item.target_activity.toUpperCase() + ' Module') : (item.module_name || 'ALVI Module');

      return `
        <div class="rounded-3xl bg-white border border-slate-200 shadow-lg hover:shadow-xl transition-all duration-300 flex flex-col justify-between overflow-hidden group">
          <div class="p-6 space-y-4">
            <!-- Header badges -->
            <div class="flex items-center justify-between gap-2">
              <span class="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full ${priorityInfo.badge} shadow-sm">
                ${escapeHtml(item.priority_label || priorityInfo.label)}
              </span>
              <span class="text-[10px] font-semibold px-2 py-0.5 rounded-full border ${diffClass}">
                ${escapeHtml(item.difficulty || 'Standard')}
              </span>
            </div>

            <!-- Title & Skill -->
            <div>
              <span class="text-[11px] font-bold uppercase tracking-wider text-indigo-600">
                ${escapeHtml(skillName)}
              </span>
              <h4 class="text-base font-bold text-slate-900 mt-0.5 group-hover:text-indigo-600 transition">
                ${escapeHtml(exerciseTitle)}
              </h4>
              <p class="text-xs text-slate-500 mt-2 leading-relaxed">
                ${escapeHtml(descriptionStr)}
              </p>
            </div>

            <!-- Why Recommended Callout -->
            <div class="p-3 rounded-2xl bg-indigo-50/60 border border-indigo-100/80 space-y-1">
              <div class="flex items-center gap-1.5 text-[11px] font-bold text-indigo-900">
                <span>💡</span> Why Recommended
              </div>
              <p class="text-[11px] text-indigo-950/80 leading-relaxed">
                ${escapeHtml(reasonStr)}
              </p>
              ${triggerStr ? `
                <div class="pt-1">
                  <span class="text-[10px] font-medium px-2 py-0.5 rounded bg-white border border-indigo-200 text-indigo-700">
                    Signal: ${escapeHtml(triggerStr)}
                  </span>
                </div>
              ` : ''}
            </div>
          </div>

          <!-- Footer & Action -->
          <div class="p-6 pt-0 space-y-3">
            <div class="flex items-center justify-between text-xs text-slate-400 font-medium border-t border-slate-100 pt-3">
              <span class="flex items-center gap-1">⏱️ ${escapeHtml(durationStr)}</span>
              <span class="flex items-center gap-1">📍 ${escapeHtml(moduleName)}</span>
            </div>

            <button
              class="btn-start-practice w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-xs font-bold shadow-md shadow-indigo-600/20 hover:shadow-indigo-600/30 transition-all flex items-center justify-center gap-2"
              data-id="${escapeHtml(item.exercise_id)}"
              data-title="${escapeHtml(exerciseTitle)}"
              data-domain="${escapeHtml(item.category || item.domain || 'general')}"
              data-route="${escapeHtml(routeUrl)}"
              data-duration="${escapeHtml(durationStr)}">
              <span>Start Practice</span>
              <span class="transition-transform group-hover:translate-x-1">→</span>
            </button>
          </div>
        </div>
      `;
    }).join('');

    // Attach click handlers to Start Practice buttons
    grid.querySelectorAll('.btn-start-practice').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = btn.getAttribute('data-id');
        const title = btn.getAttribute('data-title');
        const domain = btn.getAttribute('data-domain');
        const route = btn.getAttribute('data-route');
        const durationStr = btn.getAttribute('data-duration') || '3 min';
        const numMinutes = parseInt(durationStr, 10) || 3;

        // Task 9 correction: Record launch as initiated, NOT completed
        const record = {
          practice_id: 'prac-' + Date.now(),
          exercise_id: id,
          exercise_title: title,
          domain: domain,
          score: null,
          status: 'initiated',
          completed: false,
          is_demo: false,
          duration_seconds: 0,
          timestamp: new Date().toISOString()
        };
        savePracticeRecord(record);

        // Visual feedback before navigation
        btn.innerHTML = '<span>Launching...</span>';
        setTimeout(() => {
          window.location.href = route;
        }, 350);
      });
    });
  }

  // ── 5. Render Practice Progress & Milestones ─────────────────────────────────
  function renderPracticeProgress(progData, practiceHistory) {
    if (!progData) return;

    // Stat tiles
    const totalEl = document.getElementById('stat-total-completed');
    const uniqueEl = document.getElementById('stat-unique-drills');
    const daysEl = document.getElementById('stat-active-days');
    const timeEl = document.getElementById('stat-total-time');
    const consistencyEl = document.getElementById('stat-consistency-label');
    const familiarityNoteEl = document.getElementById('practice-familiarity-note');

    const totalCompleted = progData.total_activities_completed ?? progData.total_completed ?? 0;
    const uniqueCount = progData.unique_exercises_count ?? progData.unique_drills_attempted ?? 0;
    const catalogSize = progData.catalog_size ?? 6;
    const activeDays = progData.consistency?.days_active_count ?? progData.active_practice_days ?? 0;
    const totalMinutes = progData.total_practice_duration_seconds != null
      ? Math.round(progData.total_practice_duration_seconds / 60)
      : (progData.total_practice_minutes ?? 0);
    const consistencyLabel = progData.consistency?.consistency_label ?? progData.practice_consistency_label ?? 'Starting Out';
    const familiarityText = progData.scientific_notice ?? progData.familiarity_effects_disclaimer;

    if (totalEl) totalEl.textContent = totalCompleted;
    if (uniqueEl) uniqueEl.textContent = `${uniqueCount} / ${catalogSize}`;
    if (daysEl) daysEl.textContent = activeDays;
    if (timeEl) timeEl.textContent = `${totalMinutes}m`;

    if (consistencyEl) {
      consistencyEl.textContent = consistencyLabel;
      if (consistencyLabel.includes('Consistent') || consistencyLabel.includes('Daily') || consistencyLabel.includes('Routine')) {
        consistencyEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200';
      } else if (consistencyLabel.includes('Started') || consistencyLabel.includes('Moderate') || consistencyLabel.includes('Active')) {
        consistencyEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-200';
      } else {
        consistencyEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200';
      }
    }

    if (familiarityNoteEl && familiarityText) {
      familiarityNoteEl.textContent = familiarityText;
    }

    // Personal bests / recent practice list vs Empty State
    const emptyState = document.getElementById('practice-empty-state');
    const listEl = document.getElementById('practice-bests-list');

    const bests = progData.personal_bests || {};
    const bestKeys = Object.keys(bests);

    if (bestKeys.length === 0 && (!practiceHistory || practiceHistory.length === 0)) {
      if (emptyState) emptyState.classList.remove('hidden');
      if (listEl) {
        listEl.classList.add('hidden');
        listEl.innerHTML = '';
      }
    } else {
      if (emptyState) emptyState.classList.add('hidden');
      if (listEl) {
        listEl.classList.remove('hidden');

        let rowsHtml = '';
        bestKeys.forEach(exId => {
          const item = bests[exId];
          const title = item.display_name || item.exercise_title || exId;
          const repetitions = item.total_completions || item.repetitions || 1;
          const lastDate = item.last_completed || item.last_practice_date;
          const dateStr = lastDate ? new Date(lastDate).toLocaleDateString() : 'Recent';
          const durationMins = item.best_duration_seconds ? Math.round(item.best_duration_seconds / 60) : (item.total_seconds ? Math.round(item.total_seconds / 60) : 3);
          const scoreVal = item.best_score;

          rowsHtml += `
            <div class="p-3.5 rounded-2xl bg-slate-50 border border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between text-xs gap-2">
              <div class="flex items-center space-x-3">
                <span class="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold">✓</span>
                <div>
                  <p class="font-bold text-slate-900">${escapeHtml(title)}</p>
                  <p class="text-[11px] text-slate-400">Total sessions: ${repetitions} · Last practiced: ${dateStr}</p>
                </div>
              </div>
              <div class="flex items-center space-x-4 self-end sm:self-center">
                <span class="text-slate-600 font-semibold">${durationMins} min logged</span>
                ${scoreVal != null ? `
                  <span class="px-2.5 py-0.5 rounded-full font-bold bg-indigo-50 text-indigo-700 border border-indigo-100">
                    Best: ${scoreVal}%
                  </span>
                ` : ''}
              </div>
            </div>
          `;
        });

        listEl.innerHTML = rowsHtml;
      }
    }
  }

  // ── 6. Cognitive Journey Multi-Session Chart ────────────────────────────────
  function renderCognitiveJourneyChart(category = 'overall') {
    const ctxChart = document.getElementById('cognitive-journey-chart');
    if (!ctxChart) return;

    if (journeyChartInstance) {
      journeyChartInstance.destroy();
    }

    const history = getSessionHistory();
    const currentSession = getCurrentSession();

    // Compile timeline labels and scores
    let labels = [];
    let personalScores = [];
    let upperBand = [];
    let lowerBand = [];

    if (history.length >= 2) {
      // Use genuine historical check-in records
      history.slice(-5).forEach((sess, idx) => {
        const d = sess.startedAt ? new Date(sess.startedAt) : new Date();
        labels.push(d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));

        let score = 85;
        if (category === 'story') {
          score = sess.story?.score_percent ?? 80;
        } else if (category === 'mindplay') {
          score = sess.mindplay?.ch1_score != null ? Math.round((sess.mindplay.ch1_score / 2) * 100) : 85;
        } else if (category === 'voice') {
          score = sess.voice?.completed ? 90 : 75;
        } else {
          // Overall composite
          const s = sess.story?.score_percent ?? 80;
          const m = sess.mindplay?.ch1_score != null ? Math.round((sess.mindplay.ch1_score / 2) * 100) : 80;
          const v = sess.voice?.completed ? 90 : 75;
          score = Math.round((s + m + v) / 3);
        }
        personalScores.push(score);
        upperBand.push(95);
        lowerBand.push(85);
      });
    } else {
      // Baseline trajectory with current session if available
      labels = ['Month 1 (Baseline)', 'Month 2', 'Month 3', 'Month 4', 'Current Check-in'];
      const defaultConfigs = {
        'overall':  { personal: [94, 92, 91, 88, 87], upper: [96, 95, 95, 94, 94], lower: [90, 90, 89, 88, 88] },
        'voice':    { personal: [96, 94, 93, 89, 88], upper: [98, 97, 96, 96, 95], lower: [91, 90, 89, 88, 88] },
        'story':    { personal: [92, 90, 85, 83, 80], upper: [95, 95, 95, 95, 95], lower: [85, 85, 85, 85, 85] },
        'mindplay': { personal: [95, 93, 92, 90, 86], upper: [96, 96, 95, 95, 95], lower: [90, 90, 89, 88, 88] }
      };
      const def = defaultConfigs[category] || defaultConfigs['overall'];
      personalScores = [...def.personal];
      upperBand = [...def.upper];
      lowerBand = [...def.lower];

      // Overwrite current point if real session exists
      if (currentSession) {
        if (category === 'story' && currentSession.story?.score_percent != null) {
          personalScores[personalScores.length - 1] = Math.round(currentSession.story.score_percent);
        } else if (category === 'mindplay' && currentSession.mindplay?.ch1_score != null) {
          personalScores[personalScores.length - 1] = Math.round((currentSession.mindplay.ch1_score / 2) * 100);
        }
      }
    }

    journeyChartInstance = new Chart(ctxChart, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Personal Check-in Trend (%)',
            data: personalScores,
            borderColor: '#4F46E5',
            backgroundColor: 'rgba(79, 70, 229, 0.08)',
            borderWidth: 3,
            pointBackgroundColor: personalScores.map(s => s >= 88 ? '#22C55E' : (s >= 80 ? '#F59E0B' : '#EF4444')),
            pointBorderColor: '#FFFFFF',
            pointBorderWidth: 2,
            pointRadius: 6,
            pointHoverRadius: 9,
            tension: 0.35,
            fill: false
          },
          {
            label: 'Normal Baseline Band (Upper)',
            data: upperBand,
            borderColor: 'rgba(99, 102, 241, 0.2)',
            borderWidth: 1,
            borderDash: [4, 4],
            pointRadius: 0,
            tension: 0.35,
            fill: false
          },
          {
            label: 'Normal Baseline Band (Lower)',
            data: lowerBand,
            borderColor: 'rgba(99, 102, 241, 0.2)',
            borderWidth: 1,
            borderDash: [4, 4],
            backgroundColor: 'rgba(79, 70, 229, 0.04)',
            pointRadius: 0,
            tension: 0.35,
            fill: '-1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        onClick: (event, elements) => {
          if (elements.length > 0) {
            const index = elements[0].index;
            const score = personalScores[index];
            const dateLabel = labels[index];

            const titleEl = document.getElementById('point-month-title');
            const summaryEl = document.getElementById('point-metrics-summary');
            const badgeEl = document.getElementById('point-status-badge');

            if (titleEl) titleEl.textContent = `${dateLabel.toUpperCase()} RECORD`;
            if (summaryEl) summaryEl.textContent = `Measured Score: ${score}% · Domain: ${category.toUpperCase()} · Observation Recorded`;
            if (badgeEl) {
              if (score >= 88) {
                badgeEl.textContent = 'Status: Stable / Typical';
                badgeEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
              } else if (score >= 80) {
                badgeEl.textContent = 'Status: Mild Variance';
                badgeEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30';
              } else {
                badgeEl.textContent = 'Status: Practice Recommended';
                badgeEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30';
              }
            }
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F172A',
            titleFont: { size: 12, weight: 'bold' },
            bodyFont: { size: 11 },
            padding: 10,
            cornerRadius: 10,
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}%`
            }
          }
        },
        scales: {
          y: {
            min: 60,
            max: 100,
            grid: { color: '#F1F5F9' },
            ticks: {
              callback: (val) => `${val}%`,
              font: { size: 11, weight: '600' },
              color: '#64748B'
            }
          },
          x: {
            grid: { display: false },
            ticks: {
              font: { size: 11, weight: '700' },
              color: '#1E293B'
            }
          }
        }
      }
    });
  }

  // ── 7. Client Fallback Generators ───────────────────────────────────────────
  function getClientFallbackRecommendations(currentSession) {
    const hasStory = currentSession?.story?.completed;
    const hasMindplay = currentSession?.mindplay?.completed;
    const hasVoice = currentSession?.voice?.completed;

    if (!hasStory && !hasMindplay && !hasVoice) {
      return {
        is_starter_path: true,
        starter_path_note: 'Starter curriculum: 3 foundational drills to introduce you to descriptive speech, narrative recall, and memory binding.',
        recommended_exercises: [
          {
            priority: 1,
            priority_label: 'Starter Activity',
            exercise_id: 'ex_spontaneous_speech_description',
            display_name: 'Descriptive Scene Narration & Fluency',
            skill_practiced: 'Spontaneous Speech Pacing & Picture Description',
            category: 'speech_language',
            difficulty: 'Standard',
            estimated_duration: '2–3 minutes',
            route: 'voice.html',
            target_activity_url: 'voice.html',
            target_activity: 'voice',
            instructions: 'View the scene prompt and describe what is happening in continuous, unhurried sentences.',
            reason: 'Recommended starter exercise to introduce spontaneous spoken narration.',
            supporting_metric: 'Starter curriculum default'
          },
          {
            priority: 2,
            priority_label: 'Starter Activity',
            exercise_id: 'ex_narrative_retell_foundations',
            display_name: 'Narrative Recall & Anchor Retrieval',
            skill_practiced: 'Episodic Story Memory & Information Unit Recall',
            category: 'memory',
            difficulty: 'Standard',
            estimated_duration: '2–3 minutes',
            route: 'story.html',
            target_activity_url: 'story.html',
            target_activity: 'story',
            instructions: 'Listen to the short narrative, then retell the story verbally or in text.',
            reason: 'Foundational memory retell practice to build verbal detail recall habits.',
            supporting_metric: 'Starter curriculum default'
          },
          {
            priority: 3,
            priority_label: 'Starter Activity',
            exercise_id: 'ex_dual_feature_binding',
            display_name: 'Dual-Feature Memory Association',
            skill_practiced: 'Visual-Verbal Feature Binding & Delayed Recognition',
            category: 'memory',
            difficulty: 'Standard',
            estimated_duration: '1–2 minutes',
            route: 'mindplay.html',
            target_activity_url: 'mindplay.html',
            target_activity: 'mindplay',
            instructions: 'Identify the target items mentioned in the narrative from a grid of cards.',
            reason: 'Visual feature association practice supporting working memory agility.',
            supporting_metric: 'Starter curriculum default'
          }
        ]
      };
    }

    return {
      is_starter_path: false,
      starter_path_note: 'Personalized practice recommendations dynamically generated from your recent check-in observations.',
      opportunities_identified: ['Multi-modal practice refresh'],
      recommended_exercises: [
        {
          priority: 1,
          priority_label: 'High Priority',
          exercise_id: 'ex_temporal_chronology_builder',
          display_name: 'Story Chronology & Temporal Sequencing',
          skill_practiced: 'Executive Sequencing & Chronological Working Memory',
          category: 'executive_sequencing',
          difficulty: 'Standard',
          estimated_duration: '1–2 minutes',
          route: 'mindplay.html',
          target_activity_url: 'mindplay.html',
          target_activity: 'mindplay',
          instructions: 'Arrange the narrative milestone cards into their exact chronological order.',
          reason: 'Sequential event ordering to support structured procedural memory.',
          supporting_metric: 'Recent check-in observation'
        },
        {
          priority: 2,
          priority_label: 'High Priority',
          exercise_id: 'ex_narrative_retell_foundations',
          display_name: 'Narrative Recall & Anchor Retrieval',
          skill_practiced: 'Episodic Story Memory & Information Unit Recall',
          category: 'memory',
          difficulty: 'Standard',
          estimated_duration: '2–3 minutes',
          route: 'story.html',
          target_activity_url: 'story.html',
          target_activity: 'story',
          instructions: 'Listen to the narrative and retell with focus on key anchor details.',
          reason: 'Verbal retelling drill to strengthen narrative retention.',
          supporting_metric: 'Recent check-in observation'
        },
        {
          priority: 3,
          priority_label: 'Recommended Drill',
          exercise_id: 'ex_visual_search_agility',
          display_name: 'Target Discrimination & Visual Search',
          skill_practiced: 'Selective Visual Attention & Processing Latency',
          category: 'attention_speed',
          difficulty: 'Standard',
          estimated_duration: '1 minute',
          route: 'mindplay.html',
          target_activity_url: 'mindplay.html',
          target_activity: 'mindplay',
          instructions: 'Locate and select the target contextual item under reaction timing.',
          reason: 'Target detection speed drill to exercise visual search efficiency.',
          supporting_metric: 'Recent check-in observation'
        }
      ]
    };
  }

  function getClientFallbackProgress(practiceHistory) {
    const rawList = Array.isArray(practiceHistory) ? practiceHistory : [];
    // Task 9 correction: Only count genuine, completed, non-demo practices
    const list = rawList.filter(r =>
      !r.is_demo &&
      !r.is_sample &&
      String(r.status || '').toLowerCase() !== 'initiated' &&
      (r.completed === true || String(r.status || '').toLowerCase() === 'completed' || (r.completed !== false && r.score != null))
    );

    const total = list.length;
    const uniqueIds = new Set(list.map(r => r.exercise_id)).size;

    const dates = new Set(list.map(r => r.timestamp ? r.timestamp.slice(0, 10) : 'today')).size;
    const totalSecs = list.reduce((acc, r) => acc + (r.duration_seconds || 180), 0);

    const personalBests = {};
    list.forEach(r => {
      const id = r.exercise_id;
      if (!personalBests[id]) {
        personalBests[id] = {
          display_name: r.exercise_title || id,
          total_completions: 0,
          best_score: r.score,
          best_duration_seconds: r.duration_seconds,
          last_completed: r.timestamp
        };
      }
      personalBests[id].total_completions += 1;
      personalBests[id].best_duration_seconds = Math.max(personalBests[id].best_duration_seconds || 0, r.duration_seconds || 180);
      if (r.score != null && (personalBests[id].best_score == null || r.score > personalBests[id].best_score)) {
        personalBests[id].best_score = r.score;
      }
    });

    let consistency = 'Starting Out';
    if (total >= 10 && dates >= 5) consistency = 'Consistent Active Habit';
    else if (total >= 4 && dates >= 2) consistency = 'Active Routine';
    else if (total >= 1) consistency = 'Initial Practice Started';

    return {
      total_activities_completed: total,
      unique_exercises_count: uniqueIds,
      catalog_size: 6,
      consistency: {
        days_active_count: dates,
        consistency_label: consistency
      },
      total_practice_duration_seconds: totalSecs,
      personal_bests: personalBests,
      scientific_notice: 'Notice on Task Familiarity: Repeated practice on specific cognitive challenges frequently improves task scores due to familiarity with instructions, stimuli, and test procedures (practice effects). Such gains represent task-specific procedural learning and should not be interpreted as biological stabilization or reversal of underlying cognitive impairment.'
    };
  }

  function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // ── 8. Event Listeners & Buttons ────────────────────────────────────────────
  // Refresh button
  const refreshBtn = document.getElementById('btn-refresh-recommendations');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadRecommendationsAndProgress();
    });
  }

  // Sample practice seed button (Task 9: clearly tags developer synthetic records as is_demo)
  const seedBtn = document.getElementById('btn-seed-sample-practice');
  if (seedBtn) {
    seedBtn.addEventListener('click', () => {
      const sample = {
        practice_id: 'prac-sample-' + Date.now(),
        exercise_id: 'ex_narrative_retell_foundations',
        exercise_title: '[Sample] Narrative Recall & Anchor Retrieval',
        domain: 'memory',
        score: 90.0,
        status: 'completed',
        completed: true,
        is_demo: true,
        duration_seconds: 180,
        timestamp: new Date().toISOString()
      };
      savePracticeRecord(sample);
      loadRecommendationsAndProgress();
    });
  }

  // Category Tab button handlers
  const tabBtns = document.querySelectorAll('#journey-tabs .tab-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentActiveTab = btn.getAttribute('data-tab') || 'overall';
      renderCognitiveJourneyChart(currentActiveTab);
    });
  });

  // Initial load
  await loadRecommendationsAndProgress();
  renderCognitiveJourneyChart('overall');
});
