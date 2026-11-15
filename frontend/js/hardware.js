// hardware.js — ALVI Pocket Companion Dashboard Integration
// Polls /api/hardware/status and /api/hardware/sessions every 2 seconds

const ALVI_HW = {
    BASE: "http://127.0.0.1:8765/api/hardware",

    async fetchStatus() {
        try {
            const r = await fetch(`${this.BASE}/status`);
            return r.ok ? await r.json() : null;
        } catch { return null; }
    },

    async fetchRecentSessions(deviceId = null, limit = 20) {
        try {
            const url = deviceId
                ? `${this.BASE}/sessions?device_id=${encodeURIComponent(deviceId)}&limit=${limit}`
                : `${this.BASE}/sessions?limit=${limit}`;
            const r = await fetch(url);
            return r.ok ? await r.json() : [];
        } catch { return []; }
    },

    async fetchLatestMood(deviceId) {
        try {
            const r = await fetch(`${this.BASE}/latest-mood/${encodeURIComponent(deviceId)}`);
            return r.ok ? await r.json() : null;
        } catch { return null; }
    },

    async pairDevice(deviceId, deviceName) {
        try {
            const r = await fetch(`${this.BASE}/pair`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({device_id: deviceId, device_name: deviceName})
            });
            return r.ok ? await r.json() : null;
        } catch { return null; }
    }
};

// Canonical activity-id aliases (standalone sketch may use different names)
function canonicalActivityId(id, summary) {
    if (!id && summary) {
        try {
            const s = typeof summary === 'string' ? JSON.parse(summary) : (summary || {});
            if ('max_level' in s) return 'hw_memory_seq';
            if ('median_rt_ms' in s || 'median_rt' in s) return 'hw_reaction_test';
            if ('mood_name' in s || 'mood_code' in s) return 'hw_mood';
            if ('duration_ms' in s || 'assessment_id' in s) return 'hw_neuropen';
        } catch {}
    }
    const aliases = {
        'hw_timmy_mood': 'hw_mood',
        'hw_neuropen_clock': 'hw_neuropen',
    };
    return aliases[id] || id || '';
}

function formatActivityName(id, rawSummary) {
    const actId = canonicalActivityId(id, rawSummary);
    const map = {
        'hw_memory_seq':    '🧠 Memory Sequence',
        'hw_reaction_test': '⚡ Reaction Test',
        'hw_mood':          '😊 Mood Check-in',
        'hw_reminder':      '⏰ Practice Reminder',
        'hw_voice_status':  '🎙️ Voice Status',
        'hw_neuropen':      '✏️ NeuroPen Clock',
        'hw_activity':      '📋 Activity',
    };
    return map[actId] || actId || 'Cognitive Activity';
}

function summarizeSession(s) {
    try {
        const summary = typeof s.summary === 'string' ? JSON.parse(s.summary) : (s.summary || {});
        const actId = canonicalActivityId(s.activity_id, summary);
        if (actId === 'hw_memory_seq') {
            const lvl = summary.max_level !== undefined ? `Level ${summary.max_level}` : '';
            const corr = summary.correct_count !== undefined ? `(${summary.correct_count} correct)` : '';
            return `${lvl} ${corr}`.trim();
        }
        if (actId === 'hw_reaction_test') {
            const rt = summary.median_rt_ms !== undefined ? summary.median_rt_ms : summary.median_rt;
            return rt !== undefined ? `${rt} ms` : '';
        }
        if (actId === 'hw_mood') {
            return summary.mood_name || 'Recorded';
        }
        if (actId === 'hw_neuropen') {
            const dur = summary.duration_ms !== undefined ? `${(summary.duration_ms/1000).toFixed(1)}s` : '';
            const status = summary.status || '';
            return [dur, status].filter(Boolean).join(' · ');
        }
        return '';
    } catch { return ''; }
}

// ── Render helpers ──────────────────────────────────────────────────────────

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>'"]/g,
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag));
}

function renderMoodMetric(event) {
    if (!event) return '<span style="color:#94a3b8; font-weight:400; font-size:1rem;">—</span>';
    const payload = typeof event.payload === 'string' ? JSON.parse(event.payload || '{}') : (event.payload || {});
    const moodName = payload.mood_name || 'Recorded';
    return `<span style="color:#7e22ce;">${escapeHtml(moodName)}</span>`;
}

function renderMemoryMetric(event) {
    if (!event) return '<span style="color:#94a3b8; font-weight:400; font-size:1rem;">—</span>';
    const payload = typeof event.payload === 'string' ? JSON.parse(event.payload || '{}') : (event.payload || {});
    const level = payload.max_level !== undefined ? payload.max_level : '—';
    return `<span style="color:#16a34a;">Level ${escapeHtml(String(level))}</span>`;
}

function renderReactionMetric(event) {
    if (!event) return '<span style="color:#94a3b8; font-weight:400; font-size:1rem;">—</span>';
    const payload = typeof event.payload === 'string' ? JSON.parse(event.payload || '{}') : (event.payload || {});
    const rt = payload.median_rt_ms !== undefined ? payload.median_rt_ms : (payload.median_rt !== undefined ? payload.median_rt : null);
    if (rt === null) return '<span style="color:#94a3b8; font-weight:400; font-size:1rem;">—</span>';
    return `<span style="color:#ea580c;">${escapeHtml(String(rt))} ms</span>`;
}

function renderNeuropenMetric(sessions) {
    const npSessions = sessions.filter(s => canonicalActivityId(s.activity_id, s.summary) === 'hw_neuropen');
    if (!npSessions.length) return '<span style="color:#94a3b8; font-weight:400; font-size:1rem;">—</span>';
    const latest = npSessions[0];
    const summary = typeof latest.summary === 'string' ? JSON.parse(latest.summary || '{}') : (latest.summary || {});
    const dur = summary.duration_ms ? `${(summary.duration_ms/1000).toFixed(1)}s` : '—';
    return `<span style="color:#0ea5e9;">${escapeHtml(dur)}</span>`;
}

// ── Main render ─────────────────────────────────────────────────────────────

function renderHardwareStatus(container, status, sessions) {
    if (!status) {
        container.innerHTML = `
            <div class="hw-disconnected">
                <div class="hw-status-row">
                    <span class="hw-status-dot disconnected"></span>
                    <span class="hw-device-name">Hardware Service Offline</span>
                </div>
                <p class="hw-hint">Ensure the ALVI FastAPI backend is running on <code>http://127.0.0.1:8765</code>.</p>
            </div>`;
        return;
    }

    const device = status.device || status.latest_device || {};
    const hasDevice = Boolean(device && device.device_id);
    const connected = Boolean(status.connected);
    const latestMood = status.latest_mood;
    const latestMemory = status.latest_memory;
    const latestReaction = status.latest_reaction;

    if (!hasDevice) {
        container.innerHTML = `
            <div class="hw-disconnected">
                <div class="hw-status-row">
                    <span class="hw-status-dot disconnected"></span>
                    <span class="hw-device-name">No Companion Device Paired</span>
                </div>
                <p class="hw-hint">Connect your ALVI Pocket Companion via USB and start the serial bridge:<br>
                <code>python -m backend.hardware.bridge_service --port COM8</code></p>
            </div>`;
        return;
    }

    const lastSyncDisplay = device.last_seen
        ? new Date(device.last_seen).toLocaleString()
        : 'Never';

    const statusBadge = connected
        ? '<span style="color:#16a34a; font-weight:700; font-size:0.85rem;">● Live Connected</span>'
        : '<span style="color:#64748b; font-weight:600; font-size:0.85rem;">○ Standby / Offline</span>';

    // Build activity feed (last 20 sessions, deduplicated by session_id)
    const seen = new Set();
    const uniqueSessions = sessions.filter(s => {
        if (seen.has(s.session_id)) return false;
        seen.add(s.session_id);
        return true;
    });

    const activityFeed = uniqueSessions.slice(0, 10).map(s => {
        const actName = formatActivityName(s.activity_id, s.summary);
        const sumText = summarizeSession(s);
        const timeStr = s.started_at ? new Date(s.started_at).toLocaleString() : '';
        return `
            <div class="hw-session-row">
                <span class="hw-session-activity" style="color:#1e293b; font-weight:600;">${actName}</span>
                <span class="hw-session-summary" style="color:#475569;">${escapeHtml(sumText)}</span>
                <span class="hw-session-time" style="color:#94a3b8; font-size:0.78rem;">${escapeHtml(timeStr)}</span>
            </div>`;
    }).join('');

    container.innerHTML = `
        <div class="hw-status-row">
            <span class="hw-status-dot ${connected ? 'connected' : 'disconnected'}"></span>
            <span class="hw-device-name" style="color:#1e293b;">${escapeHtml(device.device_name || 'ALVI Pocket Companion')}</span>
            <span class="hw-device-id" style="color:#64748b; font-size:0.78rem;">${escapeHtml(device.device_id || '')}</span>
            <span style="margin-left:auto;">${statusBadge}</span>
        </div>
        <div class="hw-last-sync" style="color:#475569;">Last synchronized: <strong style="color:#1e293b;">${escapeHtml(lastSyncDisplay)}</strong></div>

        <div class="hw-metrics-row">
            <div class="hw-metric">
                <span class="hw-metric-label" style="color:#475569;">Latest Mood</span>
                <span class="hw-metric-value">${renderMoodMetric(latestMood)}</span>
            </div>
            <div class="hw-metric">
                <span class="hw-metric-label" style="color:#475569;">Memory Level</span>
                <span class="hw-metric-value">${renderMemoryMetric(latestMemory)}</span>
            </div>
            <div class="hw-metric">
                <span class="hw-metric-label" style="color:#475569;">Reaction Latency</span>
                <span class="hw-metric-value">${renderReactionMetric(latestReaction)}</span>
            </div>
            <div class="hw-metric">
                <span class="hw-metric-label" style="color:#475569;">NeuroPen Time</span>
                <span class="hw-metric-value">${renderNeuropenMetric(sessions)}</span>
            </div>
        </div>

        <div class="hw-sessions" id="hw-activity-feed">
            <h4 style="color:#1e293b;">Recent Companion Activities (${uniqueSessions.length})</h4>
            ${uniqueSessions.length === 0
                ? '<p class="hw-hint" style="color:#64748b;">No completed activities recorded for this device yet.</p>'
                : activityFeed}
        </div>`;
}

// ── Auto-update every 2 seconds ─────────────────────────────────────────────
let _hwPollInterval = null;
let _hwLastEventTime = null;

function startHardwareDashboard() {
    const container = document.getElementById('hw-dashboard-content');
    if (!container) return;

    async function update() {
        const status = await ALVI_HW.fetchStatus();
        // Accept both device_id formats: "esp32-XXXX-XXXXXXXX" (standalone) and others
        const deviceId = status?.device?.device_id || status?.latest_device?.device_id;
        const sessions = deviceId ? await ALVI_HW.fetchRecentSessions(deviceId, 20) : [];
        renderHardwareStatus(container, status, sessions);
    }

    update();
    if (!_hwPollInterval) {
        _hwPollInterval = setInterval(update, 2000);  // 2-second live refresh
    }
}

// Initialize when DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startHardwareDashboard);
} else {
    startHardwareDashboard();
}
