// ─────────────────────────────────────────────────────────────────────────────
// ALVI Pattern Explorer & Longitudinal Analytics Controller — js/patterns.js
// ─────────────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  let patternChartInstance = null;
  let cachedAnalyticsResult = null;
  let cachedMetricsCatalog = null;
  let currentDomain = 'overview';
  let currentMetricKey = 'f0_mean_hz';
  let currentDateFilter = 'all';

  // ── 1. Storage Helpers ──────────────────────────────────────────────────────
  function getSessionHistory() {
    let list = [];
    try {
      const stored = localStorage.getItem('alvi_session_history');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) list = parsed;
      }
    } catch (_) {}

    // Check if current active session exists and is not yet in history
    if (window.ALVI && window.ALVI.session && typeof window.ALVI.session.get === 'function') {
      const current = window.ALVI.session.get();
      if (current && current.sessionId) {
        const alreadyIn = list.some(s => s.sessionId === current.sessionId);
        const hasWork = (current.voice?.completed || current.story?.completed || current.mindplay?.completed);
        if (!alreadyIn && hasWork) {
          list.push(current);
        }
      }
    }
    return list;
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

  // ── 2. Data Fetching & Analytics Engine Invocation ──────────────────────────
  async function loadPatternAnalytics() {
    const api = window.ALVI_API || (window.ALVI && window.ALVI.api);
    const sessions = getSessionHistory();
    const practices = getPracticeHistory();

    // Date filter calculation
    let startDate = null;
    if (currentDateFilter === '30d') {
      const d = new Date();
      d.setDate(d.getDate() - 30);
      startDate = d.toISOString().slice(0, 10);
    } else if (currentDateFilter === '90d') {
      const d = new Date();
      d.setDate(d.getDate() - 90);
      startDate = d.toISOString().slice(0, 10);
    }

    const filterOptions = {
      start_date: startDate,
      include_demo: false
    };

    let result = null;
    const offlineAlert = document.getElementById('offline-mode-alert');

    // 1. Try Backend FastAPI
    if (api && typeof api.analyzePatterns === 'function') {
      try {
        result = await api.analyzePatterns({
          sessionHistory: sessions,
          practiceHistory: practices,
          filterOptions
        });
        if (offlineAlert) offlineAlert.classList.add('hidden');
      } catch (err) {
        console.warn('FastAPI Pattern Explorer unavailable, activating client fallback:', err);
      }
    }

    // 2. Client-side Fallback if Backend Offline
    if (!result) {
      if (offlineAlert) offlineAlert.classList.remove('hidden');
      result = computeClientSideFallbackAnalytics(sessions, practices, filterOptions);
    }

    cachedAnalyticsResult = result;

    // Render UI Components
    renderHistoryStatusBanner(result.history_summary);
    renderMetricSelectorRibbon();
    renderActiveMetricChart();
    renderRecentDeltaComparison(result.recent_vs_previous_comparison);
    renderPracticeEngagement(result.practice_engagement);
  }

  // ── 3. History Status & Threshold Banner ───────────────────────────────────
  function renderHistoryStatusBanner(summary) {
    if (!summary) return;

    const headingEl = document.getElementById('banner-heading');
    const badgeEl = document.getElementById('banner-threshold-badge');
    const descEl = document.getElementById('banner-description');
    const countPillEl = document.getElementById('banner-sessions-count-pill');
    const iconEl = document.getElementById('banner-icon');

    const count = summary.valid_sessions_analyzed || 0;
    if (countPillEl) {
      countPillEl.textContent = `${count} ${count === 1 ? 'Session' : 'Sessions'} Analyzed`;
    }

    const status = summary.history_threshold_status;

    if (status === 'no_history' || count === 0) {
      if (iconEl) iconEl.textContent = '🌱';
      if (headingEl) headingEl.textContent = 'No Check-in History Recorded';
      if (badgeEl) {
        badgeEl.textContent = 'Awaiting Check-in';
        badgeEl.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-slate-700 text-slate-300 border border-slate-600';
      }
      if (descEl) descEl.textContent = 'Complete your first Voice Check-in, Story Recall, or MindPlay session to begin logging longitudinal data.';
    } else if (status === 'single_baseline' || count === 1) {
      if (iconEl) iconEl.textContent = '📍';
      if (headingEl) headingEl.textContent = 'Single Baseline Established';
      if (badgeEl) {
        badgeEl.textContent = 'Baseline (1 Point)';
        badgeEl.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-indigo-500/30 text-indigo-200 border border-indigo-400/30';
      }
      if (descEl) descEl.textContent = 'One valid session recorded. Pairwise session-to-session delta comparison will unlock upon your next check-in.';
    } else if (status === 'pairwise_comparison' || count === 2) {
      if (iconEl) iconEl.textContent = '⚖️';
      if (headingEl) headingEl.textContent = 'Pairwise Session Comparison Active';
      if (badgeEl) {
        badgeEl.textContent = 'Pairwise (2 Points)';
        badgeEl.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-500/30 text-amber-200 border border-amber-400/30';
      }
      if (descEl) descEl.textContent = 'Two sessions recorded. Direct performance deltas are available below. Longitudinal trend trajectory modeling unlocks with 3+ sessions.';
    } else {
      if (iconEl) iconEl.textContent = '📈';
      if (headingEl) headingEl.textContent = 'Longitudinal Performance Trajectory Active';
      if (badgeEl) {
        badgeEl.textContent = `Trajectory (${count} Points)`;
        badgeEl.className = 'px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/30 text-emerald-200 border border-emerald-400/30';
      }
      if (descEl) descEl.textContent = `Analyzing observational trends across ${count} distinct check-in snapshots recorded between ${summary.date_range?.earliest || 'earlier'} and ${summary.date_range?.latest || 'today'}.`;
    }
  }

  // ── 4. Metric Selector Ribbon ───────────────────────────────────────────────
  const domainMetricConfigs = {
    'overview': [
      { key: 'composite_accuracy_percent', label: 'MindPlay Accuracy', unit: '%', domain: 'mindplay' },
      { key: 'score_percent', label: 'Story Recall Completeness', unit: '%', domain: 'story' },
      { key: 'low_energy_frame_ratio', label: 'Speech Pause Ratio', unit: 'Ratio', domain: 'voice' },
      { key: 'ch3_reaction_ms', label: 'Reaction Latency', unit: 'ms', domain: 'mindplay' }
    ],
    'voice': [
      { key: 'f0_mean_hz', label: 'Mean Pitch (F0)', unit: 'Hz', domain: 'voice' },
      { key: 'rms_energy', label: 'RMS Signal Energy', unit: 'RMS', domain: 'voice' },
      { key: 'zero_crossing_rate', label: 'Zero-Crossing Rate', unit: 'Rate', domain: 'voice' },
      { key: 'low_energy_frame_ratio', label: 'Low-Energy Frame Ratio', unit: 'Ratio', domain: 'voice' },
      { key: 'spectral_centroid_hz', label: 'Spectral Centroid', unit: 'Hz', domain: 'voice' },
      { key: 'duration_seconds', label: 'Recording Duration', unit: 's', domain: 'voice' }
    ],
    'story': [
      { key: 'score_percent', label: 'Recall Completeness', unit: '%', domain: 'story' },
      { key: 'recalled_facts_count', label: 'Recalled Anchors', unit: 'units', domain: 'story' },
      { key: 'missed_facts_count', label: 'Missed Anchors', unit: 'units', domain: 'story' },
      { key: 'chronological_inversions', label: 'Chronological Inversions', unit: 'count', domain: 'story' }
    ],
    'mindplay': [
      { key: 'composite_accuracy_percent', label: 'Overall Challenge Accuracy', unit: '%', domain: 'mindplay' },
      { key: 'ch1_score', label: 'Dual-Feature Binding', unit: 'pts', domain: 'mindplay' },
      { key: 'ch3_reaction_ms', label: 'Visual Search Reaction Latency', unit: 'ms', domain: 'mindplay' },
      { key: 'total_time_seconds', label: 'Total Duration', unit: 's', domain: 'mindplay' }
    ],
    'practice': [
      { key: 'cumulative_practice_minutes', label: 'Total Practice Time', unit: 'min', domain: 'practice' },
      { key: 'total_completed_count', label: 'Drills Completed', unit: 'count', domain: 'practice' }
    ]
  };

  function renderMetricSelectorRibbon() {
    const container = document.getElementById('metric-buttons-container');
    const domainLabel = document.getElementById('metric-domain-label');
    if (!container) return;

    const domainNames = {
      'overview': 'Multi-Modal Overview',
      'voice': 'Voice Check-in Acoustics',
      'story': 'Story Recall Memory',
      'mindplay': 'MindPlay Challenge Telemetry',
      'practice': 'Practice Engagement'
    };

    if (domainLabel) {
      domainLabel.textContent = domainNames[currentDomain] || 'Longitudinal Metrics';
    }

    const metrics = domainMetricConfigs[currentDomain] || domainMetricConfigs['overview'];

    // Ensure currentMetricKey belongs to this domain
    const hasCurrent = metrics.some(m => m.key === currentMetricKey);
    if (!hasCurrent) {
      currentMetricKey = metrics[0].key;
    }

    container.innerHTML = metrics.map(m => {
      const isActive = m.key === currentMetricKey;
      return `
        <button
          class="metric-btn px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
            isActive
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200/60'
          }"
          data-metric="${escapeHtml(m.key)}"
          data-domain="${escapeHtml(m.domain)}">
          ${escapeHtml(m.label)} (${escapeHtml(m.unit)})
        </button>
      `;
    }).join('');

    container.querySelectorAll('.metric-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        currentMetricKey = btn.getAttribute('data-metric');
        renderMetricSelectorRibbon();
        renderActiveMetricChart();
      });
    });
  }

  // ── 5. Primary Interactive Chart & Statistics Panel ─────────────────────────
  function getActiveMetricData() {
    if (!cachedAnalyticsResult) return null;

    if (currentDomain === 'practice') {
      const pEng = cachedAnalyticsResult.practice_engagement;
      const series = (pEng?.cumulative_series || []).map(p => ({
        date: p.date,
        session_id: p.exercise_id,
        value: currentMetricKey === 'total_completed_count' ? 1 : p.cumulative_minutes
      }));
      return {
        metric_name: currentMetricKey === 'total_completed_count' ? 'Drills Completed' : 'Cumulative Practice Minutes',
        unit: currentMetricKey === 'total_completed_count' ? 'drills' : 'min',
        data_points_count: series.length,
        comparison_mode: series.length >= 3 ? 'longitudinal_trend' : (series.length === 2 ? 'pairwise_only' : (series.length === 1 ? 'baseline_only' : 'no_data')),
        baseline_value: series.length > 0 ? series[0].value : null,
        latest_value: series.length > 0 ? series[series.length - 1].value : null,
        absolute_change: series.length > 1 ? series[series.length - 1].value - series[0].value : null,
        percent_change: null,
        mean: series.length > 0 ? Math.round(series.reduce((a, b) => a + b.value, 0) / series.length * 10) / 10 : null,
        scientific_note: 'Practice milestones reflect personal engagement and routine consistency.',
        series
      };
    }

    // Check across metrics_domains
    const domains = cachedAnalyticsResult.metrics_domains || {};
    for (const dKey of ['voice', 'story', 'mindplay']) {
      if (domains[dKey] && domains[dKey][currentMetricKey]) {
        return domains[dKey][currentMetricKey];
      }
    }
    return null;
  }

  function renderActiveMetricChart() {
    const metricData = getActiveMetricData();
    const ctx = document.getElementById('pattern-explorer-chart');
    const overlay = document.getElementById('chart-empty-state-overlay');
    if (!ctx) return;

    // Header updates
    const titleEl = document.getElementById('active-metric-title');
    const unitBadge = document.getElementById('active-metric-unit-badge');
    const modeBadge = document.getElementById('active-metric-mode-badge');
    const noteEl = document.getElementById('metric-scientific-note-text');

    if (metricData) {
      if (titleEl) titleEl.textContent = metricData.metric_name;
      if (unitBadge) unitBadge.textContent = metricData.unit;
      if (modeBadge) {
        const modeLabels = {
          'no_data': 'No Observations',
          'baseline_only': 'Single Baseline',
          'pairwise_only': 'Pairwise Delta',
          'longitudinal_trend': 'Longitudinal Trajectory'
        };
        modeBadge.textContent = modeLabels[metricData.comparison_mode] || 'Observational';
      }
      if (noteEl) {
        noteEl.textContent = metricData.scientific_note || 'Factual observational measurement across recorded check-ins.';
      }
    }

    // Update 5 KPI summary tiles
    updateSummaryKpis(metricData);

    // If no data points
    if (!metricData || metricData.data_points_count === 0 || !metricData.series || metricData.series.length === 0) {
      if (overlay) overlay.classList.remove('hidden');
      if (patternChartInstance) {
        patternChartInstance.destroy();
        patternChartInstance = null;
      }
      return;
    }

    if (overlay) overlay.classList.add('hidden');

    if (patternChartInstance) {
      patternChartInstance.destroy();
    }

    const series = metricData.series;
    const labels = series.map(s => {
      const d = s.date ? new Date(s.date) : new Date();
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    const values = series.map(s => s.value);

    // Compute simple linear regression line if n >= 3
    let trendLineValues = null;
    if (metricData.data_points_count >= 3 && metricData.mean != null) {
      const n = values.length;
      const xMean = (n - 1) / 2.0;
      const yMean = metricData.mean;
      let num = 0, den = 0;
      for (let i = 0; i < n; i++) {
        num += (i - xMean) * (values[i] - yMean);
        den += (i - xMean) * (i - xMean);
      }
      if (den > 0) {
        const slope = num / den;
        const intercept = yMean - slope * xMean;
        trendLineValues = values.map((_, i) => Math.round((intercept + slope * i) * 100) / 100);
      }
    }

    const datasets = [
      {
        label: `Personal Observations (${metricData.unit})`,
        data: values,
        borderColor: '#4F46E5',
        backgroundColor: 'rgba(79, 70, 229, 0.08)',
        borderWidth: 3,
        pointBackgroundColor: values.map(v => '#4F46E5'),
        pointBorderColor: '#FFFFFF',
        pointBorderWidth: 2,
        pointRadius: 6,
        pointHoverRadius: 9,
        tension: 0.25,
        fill: false
      }
    ];

    if (trendLineValues) {
      datasets.push({
        label: 'Descriptive Linear Trajectory',
        data: trendLineValues,
        borderColor: 'rgba(139, 92, 246, 0.45)',
        borderWidth: 2,
        borderDash: [5, 5],
        pointRadius: 0,
        tension: 0,
        fill: false
      });
    }

    // Determine Y-axis padding
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal;
    let yMin = range > 0 ? Math.max(0, minVal - range * 0.2) : Math.max(0, minVal * 0.8);
    let yMax = range > 0 ? maxVal + range * 0.2 : minVal * 1.2 + 1;

    // For percentages (0-100)
    if (metricData.unit === '%') {
      yMin = Math.max(0, Math.min(yMin, 50));
      yMax = 100;
    }

    patternChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        onClick: (event, elements) => {
          if (elements.length > 0) {
            const idx = elements[0].index;
            const pt = series[idx];
            updatePointInspection(pt, metricData);
          }
        },
        plugins: {
          legend: {
            display: datasets.length > 1,
            position: 'top',
            labels: { boxWidth: 12, font: { size: 11, weight: '600' } }
          },
          tooltip: {
            backgroundColor: '#0F172A',
            padding: 10,
            cornerRadius: 10,
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y} ${metricData.unit}`
            }
          }
        },
        scales: {
          y: {
            min: Math.floor(yMin),
            max: Math.ceil(yMax),
            grid: { color: '#F1F5F9' },
            ticks: {
              callback: (val) => `${val} ${metricData.unit}`,
              font: { size: 11, weight: '600' },
              color: '#64748B'
            }
          },
          x: {
            grid: { display: false },
            ticks: { font: { size: 11, weight: '700' }, color: '#1E293B' }
          }
        }
      }
    });

    // Auto-inspect the latest point
    if (series.length > 0) {
      updatePointInspection(series[series.length - 1], metricData);
    }
  }

  function updateSummaryKpis(metricData) {
    const ptsEl = document.getElementById('stat-points-count');
    const baseEl = document.getElementById('stat-baseline-val');
    const latestEl = document.getElementById('stat-latest-val');
    const meanEl = document.getElementById('stat-mean-val');
    const rangeEl = document.getElementById('stat-range-val');
    const deltaEl = document.getElementById('stat-delta-val');
    const deltaPctEl = document.getElementById('stat-delta-pct');

    if (!metricData || metricData.data_points_count === 0) {
      if (ptsEl) ptsEl.textContent = '0';
      if (baseEl) baseEl.textContent = '—';
      if (latestEl) latestEl.textContent = '—';
      if (meanEl) meanEl.textContent = '—';
      if (rangeEl) rangeEl.textContent = 'Range: —';
      if (deltaEl) deltaEl.textContent = '—';
      if (deltaPctEl) deltaPctEl.textContent = 'vs baseline';
      return;
    }

    if (ptsEl) ptsEl.textContent = metricData.data_points_count;
    if (baseEl) baseEl.textContent = `${metricData.baseline_value} ${metricData.unit}`;
    if (latestEl) latestEl.textContent = `${metricData.latest_value} ${metricData.unit}`;
    if (meanEl) meanEl.textContent = `${metricData.mean} ${metricData.unit}`;
    if (rangeEl) {
      rangeEl.textContent = metricData.min != null ? `Min: ${metricData.min} · Max: ${metricData.max}` : 'Single point';
    }

    if (deltaEl && deltaPctEl) {
      if (metricData.absolute_change != null) {
        const sign = metricData.absolute_change > 0 ? '+' : '';
        deltaEl.textContent = `${sign}${metricData.absolute_change} ${metricData.unit}`;
        if (metricData.percent_change != null) {
          const pctSign = metricData.percent_change > 0 ? '+' : '';
          deltaPctEl.textContent = `${pctSign}${metricData.percent_change}% vs baseline`;
        } else {
          deltaPctEl.textContent = 'Absolute delta';
        }
      } else {
        deltaEl.textContent = 'Baseline';
        deltaPctEl.textContent = 'Initial point';
      }
    }
  }

  function updatePointInspection(pt, metricData) {
    const titleEl = document.getElementById('inspect-point-title');
    const detailEl = document.getElementById('inspect-point-detail');
    const badgeEl = document.getElementById('inspect-point-badge');

    if (!pt || !metricData) return;

    if (titleEl) titleEl.textContent = `${pt.date.toUpperCase()} · ${metricData.metric_name}`;
    if (detailEl) {
      detailEl.textContent = `Measured Value: ${pt.value} ${metricData.unit} · Session ID: ${pt.session_id || 'Recorded Check-in'}`;
    }
    if (badgeEl) {
      badgeEl.textContent = `${pt.value} ${metricData.unit}`;
      badgeEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30';
    }
  }

  // ── 6. Multi-Modal Recent Delta Comparison ─────────────────────────────────
  function renderRecentDeltaComparison(comp) {
    const grid = document.getElementById('recent-delta-grid');
    const datesEl = document.getElementById('recent-delta-dates');
    if (!grid) return;

    if (!comp || !comp.metrics_deltas || Object.keys(comp.metrics_deltas).length === 0) {
      grid.innerHTML = `
        <div class="col-span-full p-6 rounded-2xl bg-slate-50 border border-slate-200 text-center space-y-1">
          <p class="text-xs font-semibold text-slate-700">Pairwise Comparison Requires At Least Two Completed Sessions</p>
          <p class="text-[11px] text-slate-400">Complete another check-in to observe direct pairwise performance deltas.</p>
        </div>
      `;
      if (datesEl) datesEl.textContent = 'Awaiting second check-in';
      return;
    }

    if (datesEl) {
      datesEl.textContent = `Comparing ${comp.previous_session_date} vs ${comp.current_session_date}`;
    }

    const deltas = comp.metrics_deltas;
    const cards = [];

    // Voice Pause Ratio
    if (deltas.voice_pause_ratio) {
      const d = deltas.voice_pause_ratio;
      const sign = d.delta > 0 ? '+' : '';
      cards.push(`
        <div class="p-4 rounded-2xl bg-slate-50 border border-slate-100 space-y-2">
          <div class="flex items-center justify-between text-[11px] font-bold text-slate-500 uppercase">
            <span>🎙️ Voice Pause Ratio</span>
            <span class="text-indigo-600 font-semibold">${d.unit}</span>
          </div>
          <div class="flex items-baseline justify-between">
            <div>
              <p class="text-xl font-extrabold text-slate-900">${d.current}</p>
              <p class="text-[10px] text-slate-400">Previous: ${d.previous}</p>
            </div>
            <span class="text-xs font-bold px-2 py-0.5 rounded-full ${d.delta <= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}">
              ${sign}${d.delta}
            </span>
          </div>
        </div>
      `);
    }

    // Story Recall Completeness
    if (deltas.story_recall_percent) {
      const d = deltas.story_recall_percent;
      const sign = d.delta > 0 ? '+' : '';
      cards.push(`
        <div class="p-4 rounded-2xl bg-slate-50 border border-slate-100 space-y-2">
          <div class="flex items-center justify-between text-[11px] font-bold text-slate-500 uppercase">
            <span>📖 Story Recall</span>
            <span class="text-indigo-600 font-semibold">%</span>
          </div>
          <div class="flex items-baseline justify-between">
            <div>
              <p class="text-xl font-extrabold text-slate-900">${d.current}%</p>
              <p class="text-[10px] text-slate-400">Previous: ${d.previous}%</p>
            </div>
            <span class="text-xs font-bold px-2 py-0.5 rounded-full ${d.delta >= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}">
              ${sign}${d.delta}%
            </span>
          </div>
        </div>
      `);
    }

    // MindPlay Latency / Accuracy
    if (deltas.mindplay_latency_ms) {
      const d = deltas.mindplay_latency_ms;
      const sign = d.delta > 0 ? '+' : '';
      cards.push(`
        <div class="p-4 rounded-2xl bg-slate-50 border border-slate-100 space-y-2">
          <div class="flex items-center justify-between text-[11px] font-bold text-slate-500 uppercase">
            <span>🎮 Search Latency</span>
            <span class="text-indigo-600 font-semibold">ms</span>
          </div>
          <div class="flex items-baseline justify-between">
            <div>
              <p class="text-xl font-extrabold text-slate-900">${Math.round(d.current)} ms</p>
              <p class="text-[10px] text-slate-400">Previous: ${Math.round(d.previous)} ms</p>
            </div>
            <span class="text-xs font-bold px-2 py-0.5 rounded-full ${d.delta <= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}">
              ${sign}${Math.round(d.delta)} ms
            </span>
          </div>
        </div>
      `);
    }

    grid.innerHTML = cards.join('');
  }

  // ── 7. Practice Engagement & Repetitions ────────────────────────────────────
  function renderPracticeEngagement(pEng) {
    if (!pEng) return;

    const totalEl = document.getElementById('practice-stat-total');
    const uniqueEl = document.getElementById('practice-stat-unique');
    const daysEl = document.getElementById('practice-stat-days');
    const timeEl = document.getElementById('practice-stat-time');
    const badgeEl = document.getElementById('practice-consistency-badge');
    const listEl = document.getElementById('practice-bests-list');

    if (totalEl) totalEl.textContent = pEng.total_completed || 0;
    if (uniqueEl) uniqueEl.textContent = `${pEng.unique_exercises_count || 0} / 6`;
    if (daysEl) daysEl.textContent = pEng.active_practice_days || 0;
    if (timeEl) timeEl.textContent = `${Math.round(pEng.total_practice_minutes || 0)}m`;

    if (badgeEl) {
      const label = pEng.practice_consistency_label || 'Starting Out';
      badgeEl.textContent = label;
      if (label.includes('Consistent') || label.includes('Daily')) {
        badgeEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200';
      } else if (label.includes('Routine') || label.includes('Active')) {
        badgeEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-200';
      } else {
        badgeEl.className = 'px-3 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200';
      }
    }

    if (listEl) {
      const bests = pEng.personal_bests || {};
      const keys = Object.keys(bests);

      if (keys.length === 0) {
        listEl.innerHTML = `
          <div class="p-4 rounded-2xl bg-slate-50 border border-slate-100 text-center text-xs text-slate-400">
            No completed practice drills logged yet. Completed sessions will show exercise milestones here.
          </div>
        `;
      } else {
        listEl.innerHTML = keys.map(k => {
          const item = bests[k];
          const dStr = item.last_completed ? new Date(item.last_completed).toLocaleDateString() : 'Recent';
          return `
            <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-between text-xs">
              <div class="flex items-center space-x-2.5">
                <span class="w-6 h-6 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold text-[11px]">✓</span>
                <div>
                  <p class="font-bold text-slate-800">${escapeHtml(item.exercise_title || k)}</p>
                  <p class="text-[10px] text-slate-400">Total sessions: ${item.completions} · Last practiced: ${dStr}</p>
                </div>
              </div>
              <div class="flex items-center space-x-3">
                <span class="text-slate-500 font-semibold">${Math.round(item.total_seconds / 60)} min spent</span>
                ${item.best_score != null ? `
                  <span class="px-2 py-0.5 rounded-full font-bold bg-indigo-50 text-indigo-700 border border-indigo-100 text-[11px]">
                    Score: ${item.best_score}%
                  </span>
                ` : ''}
              </div>
            </div>
          `;
        }).join('');
      }
    }
  }

  // ── 8. Client-side Fallback Analytics Generator (Offline Mode) ───────────────
  function computeClientSideFallbackAnalytics(sessions, practices, filters) {
    const validSessions = [];
    const seenIds = new Set();

    (sessions || []).forEach(s => {
      if (s && s.sessionId && !seenIds.has(s.sessionId) && !s.is_demo) {
        seenIds.add(s.sessionId);
        const dtStr = s.startedAt || s.timestamp || new Date().toISOString();
        const date = dtStr.slice(0, 10);
        if (filters.start_date && date < filters.start_date) return;
        validSessions.push({
          session_id: s.sessionId,
          date: date,
          timestamp: dtStr,
          voice: s.voice || {},
          story: s.story || {},
          mindplay: s.mindplay || {}
        });
      }
    });

    validSessions.sort((a, b) => a.date.localeCompare(b.date));

    // Extract helper
    function getSeries(extractor) {
      const res = [];
      validSessions.forEach(s => {
        const val = extractor(s);
        if (val != null && !isNaN(val)) {
          res.push({ session_id: s.session_id, date: s.date, timestamp: s.timestamp, value: val });
        }
      });
      return res;
    }

    function buildStat(series, name, unit) {
      const n = series.length;
      if (n === 0) {
        return { metric_name: name, unit, data_points_count: 0, comparison_mode: 'no_data', series: [] };
      }
      const vals = series.map(s => s.value);
      const first = vals[0];
      const latest = vals[n - 1];
      const sum = vals.reduce((a, b) => a + b, 0);
      return {
        metric_name: name,
        unit,
        data_points_count: n,
        comparison_mode: n >= 3 ? 'longitudinal_trend' : (n === 2 ? 'pairwise_only' : 'baseline_only'),
        baseline_value: first,
        latest_value: latest,
        absolute_change: n > 1 ? Math.round((latest - first) * 100) / 100 : null,
        percent_change: (n > 1 && first !== 0) ? Math.round(((latest - first) / Math.abs(first)) * 1000) / 10 : null,
        mean: Math.round((sum / n) * 100) / 100,
        min: Math.min(...vals),
        max: Math.max(...vals),
        series
      };
    }

    const voiceF0 = getSeries(s => s.voice.features?.mean_f0 || s.voice.metrics?.f0_mean_hz);
    const voicePause = getSeries(s => s.voice.features?.low_energy_frame_ratio || s.voice.metrics?.low_energy_frame_ratio);
    const storyScore = getSeries(s => s.story.score_percent);
    const mpAcc = getSeries(s => s.mindplay.composite_accuracy_percent || (s.mindplay.ch1_score != null ? (s.mindplay.ch1_score / 2) * 100 : null));
    const mpRx = getSeries(s => s.mindplay.ch3_reactionMs || s.mindplay.ch3_reaction_ms);

    return {
      status: 'offline_fallback',
      history_summary: {
        valid_sessions_analyzed: validSessions.length,
        history_threshold_status: validSessions.length >= 3 ? 'longitudinal_trend_available' : (validSessions.length === 2 ? 'pairwise_comparison' : (validSessions.length === 1 ? 'single_baseline' : 'no_history')),
        timeline_labels: validSessions.map(s => s.date),
        date_range: {
          earliest: validSessions[0]?.date,
          latest: validSessions[validSessions.length - 1]?.date
        }
      },
      metrics_domains: {
        voice: {
          f0_mean_hz: buildStat(voiceF0, 'Mean Pitch (F0)', 'Hz'),
          low_energy_frame_ratio: buildStat(voicePause, 'Low-Energy Frame Ratio', 'Ratio')
        },
        story: {
          score_percent: buildStat(storyScore, 'Recall Completeness', '%')
        },
        mindplay: {
          composite_accuracy_percent: buildStat(mpAcc, 'Challenge Accuracy', '%'),
          ch3_reaction_ms: buildStat(mpRx, 'Visual Search Reaction Latency', 'ms')
        }
      },
      practice_engagement: {
        total_completed: (practices || []).filter(p => !p.is_demo && p.status === 'completed').length,
        unique_exercises_count: new Set((practices || []).map(p => p.exercise_id)).size,
        active_practice_days: new Set((practices || []).map(p => (p.timestamp || '').slice(0, 10))).size,
        total_practice_minutes: Math.round((practices || []).reduce((a, b) => a + (b.duration_seconds || 180), 0) / 60),
        practice_consistency_label: 'Offline Local Record',
        personal_bests: {}
      }
    };
  }

  // ── 9. Export Functionality (Safe Local JSON) ────────────────────────────────
  const exportBtn = document.getElementById('btn-export-patterns');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      if (!cachedAnalyticsResult) {
        alert('No analytics data available to export.');
        return;
      }
      const exportPayload = {
        export_date: new Date().toISOString(),
        application: 'ALVI Pattern Explorer',
        version: '1.6.0',
        notice: 'Non-sensitive longitudinal performance metric export.',
        history_summary: cachedAnalyticsResult.history_summary,
        metrics_domains: cachedAnalyticsResult.metrics_domains,
        practice_engagement: cachedAnalyticsResult.practice_engagement
      };

      const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportPayload, null, 2));
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute('href', dataStr);
      downloadAnchor.setAttribute('download', `alvi-pattern-metrics-${new Date().toISOString().slice(0, 10)}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    });
  }

  // ── 10. Event Listeners ─────────────────────────────────────────────────────
  // Domain tab buttons
  const domainTabs = document.querySelectorAll('#domain-tabs .domain-tab-btn');
  domainTabs.forEach(btn => {
    btn.addEventListener('click', () => {
      domainTabs.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentDomain = btn.getAttribute('data-domain') || 'overview';
      renderMetricSelectorRibbon();
      renderActiveMetricChart();
    });
  });

  // Date filter select
  const dateSelect = document.getElementById('date-range-filter');
  if (dateSelect) {
    dateSelect.addEventListener('change', (e) => {
      currentDateFilter = e.target.value;
      loadPatternAnalytics();
    });
  }

  // Refresh button
  const refreshBtn = document.getElementById('btn-refresh-patterns');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadPatternAnalytics();
    });
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

  // Initial load
  await loadPatternAnalytics();
});
