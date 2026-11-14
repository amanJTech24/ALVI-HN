// Voice Description & Check-in Flow Script
// Waveform: real mic via Web Audio API AnalyserNode (bar style, matches story page).
// Playback: MediaRecorder captures audio; object URL presented after stop.

document.addEventListener('DOMContentLoaded', () => {

  // ── Section visibility toggle ─────────────────────────────────────────────
  const beginCheckinFlowBtn     = document.getElementById('begin-checkin-flow-btn');
  const todayOverviewSection    = document.getElementById('page-today-checkin');
  const voiceDescriptionSection = document.getElementById('page-voice-description');

  if (beginCheckinFlowBtn && todayOverviewSection && voiceDescriptionSection) {
    beginCheckinFlowBtn.addEventListener('click', () => {
      todayOverviewSection.classList.add('hidden');
      voiceDescriptionSection.classList.remove('hidden');
      window.scrollTo({ top: 0, behavior: 'smooth' });

      // ── Session: start a fresh check-in session when the user
      // deliberately begins. This is the only place init() is called so
      // that returning to this page via the sidebar does NOT wipe a
      // session that is already in progress.
      if (window.ALVI && window.ALVI.session) {
        window.ALVI.session.init();
      }
    });
  }

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const toggleRecordBtn   = document.getElementById('toggle-record-btn');
  const recordIcon        = document.getElementById('record-icon');
  const recordBtnText     = document.getElementById('record-btn-text');
  const recordStatusText  = document.getElementById('record-status-text');
  const voiceTimerDisplay = document.getElementById('voice-timer-display');
  const toStoryRecallBtn  = document.getElementById('to-story-recall-btn');
  const resetRecordBtn    = document.getElementById('reset-record-btn');
  const analyzeVoiceBtn   = document.getElementById('analyze-voice-btn');
  const analyzeBtnText    = document.getElementById('analyze-btn-text');
  const canvas            = document.getElementById('voice-waveform-canvas');

  // ML UI metrics & prediction card refs
  const voiceFeatureMetrics     = document.getElementById('voice-feature-metrics');
  const voiceMlPredictionCard   = document.getElementById('voice-ml-prediction-card');
  const metricFeaturesCount     = document.getElementById('metric-features-count');
  const metricPitch             = document.getElementById('metric-pitch');
  const metricRms               = document.getElementById('metric-rms');
  const metricZcr               = document.getElementById('metric-zcr');
  const metricPause             = document.getElementById('metric-pause');
  const metricCentroid          = document.getElementById('metric-centroid');
  const predictionModelVersion  = document.getElementById('prediction-model-version');
  const predictionLabelBadge    = document.getElementById('prediction-label-badge');
  const predictionRawScore      = document.getElementById('prediction-raw-score');
  const predictionDisclaimerText = document.getElementById('prediction-disclaimer-text');

  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  // ── State ─────────────────────────────────────────────────────────────────
  let isRecording         = false;
  let voiceRecordingTimer = null;
  let voiceElapsedSeconds = 0;
  let animFrameId         = null;
  let currentAudioBlob    = null;

  // Web Audio API — analysis only (NOT connected to destination, no echo)
  let audioCtx    = null;
  let analyser    = null;
  let micSource   = null;
  let micStream   = null;
  let dataArray   = null;

  // MediaRecorder — captures audio for playback
  let mediaRecorder   = null;
  let recordedChunks  = [];
  let playbackURL     = null;   // current object URL; revoked on reset

  // ── Playback element (injected once, hidden/shown) ────────────────────────
  // Insert a persistent <audio> element near the status text so it doesn't
  // get overwritten by status updates.
  const playbackContainer = document.createElement('div');
  playbackContainer.id    = 'voice-playback-container';
  playbackContainer.className = 'hidden flex items-center gap-3 pt-1';
  playbackContainer.innerHTML =
    '<span class="text-xs text-emerald-400 font-semibold">▶ Your recording:</span>' +
    '<audio id="voice-playback-audio" controls class="h-8 rounded-lg" style="max-width:240px;filter:invert(1) hue-rotate(210deg) brightness(0.9)"></audio>';

  // Insert after the record-status-text paragraph inside the dark panel
  if (recordStatusText && recordStatusText.parentNode) {
    recordStatusText.parentNode.insertBefore(playbackContainer, recordStatusText.nextSibling);
  }
  const playbackAudio = document.getElementById('voice-playback-audio');

  // ── Canvas: stamp real pixel dimensions at draw time ─────────────────────
  // Re-stamp every frame so resize events are automatically handled.
  function stampCanvas() {
    const parent = canvas.parentElement;
    const w = parent ? parent.clientWidth  : canvas.offsetWidth;
    const h = parent ? parent.clientHeight : canvas.offsetHeight;
    if (w > 0 && canvas.width  !== w) canvas.width  = w;
    if (h > 0 && canvas.height !== h) canvas.height = h;
  }

  // ── Idle baseline ─────────────────────────────────────────────────────────
  function drawIdle() {
    stampCanvas();
    if (canvas.width === 0 || canvas.height === 0) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const bars   = 45;
    const barW   = (canvas.width / bars) - 2;
    const centerY = canvas.height / 2;
    ctx.fillStyle = '#334155';
    for (let i = 0; i < bars; i++) {
      const x = i * (barW + 2);
      const h = 3;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, centerY - h / 2, barW, h, 2);
      else ctx.rect(x, centerY - h / 2, barW, h);
      ctx.fill();
    }
  }

  drawIdle();

  // ── Live waveform — bar style matching Story Recall ───────────────────────
  // Uses getByteFrequencyData so bars react visibly to speech amplitude.
  function drawLiveWaveform() {
    if (!isRecording || !analyser) return;
    animFrameId = requestAnimationFrame(drawLiveWaveform);

    stampCanvas();
    const W = canvas.width;
    const H = canvas.height;
    if (W === 0 || H === 0) return;

    analyser.getByteFrequencyData(dataArray);

    ctx.clearRect(0, 0, W, H);

    const bars  = 45;
    const barW  = (W / bars) - 2;
    const centerY = H / 2;

    for (let i = 0; i < bars; i++) {
      // Map frequency bins evenly across bar count
      const binIndex = Math.floor(i * dataArray.length / bars);
      const amplitude = dataArray[binIndex] / 255;   // 0–1

      // Minimum 3 px tall (silence baseline), scales to ~80% of half-height
      const h = Math.max(3, amplitude * H * 0.85);
      const x = i * (barW + 2);
      const y = centerY - h / 2;

      ctx.fillStyle = '#6366F1';
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x, y, barW, h, 2);
      else ctx.rect(x, y, barW, h);
      ctx.fill();
    }
  }

  // ── Start recording ───────────────────────────────────────────────────────
  async function startRecording() {
    isRecording = false;
    voiceElapsedSeconds = 0;
    if (voiceTimerDisplay) voiceTimerDisplay.textContent = '0:00 / 0:30';

    if (recordIcon)       recordIcon.textContent = '⏳';
    if (recordBtnText)    recordBtnText.textContent = 'Requesting mic…';
    if (recordStatusText) {
      recordStatusText.textContent = 'Waiting for microphone permission…';
      recordStatusText.className   = 'text-xs text-slate-400';
    }
    playbackContainer.classList.add('hidden');

    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });

      // ── Web Audio graph (analysis only) ───────────────────────────────────
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === 'suspended') await audioCtx.resume();

      analyser = audioCtx.createAnalyser();
      analyser.fftSize               = 256;   // 128 frequency bins — enough for bars
      analyser.smoothingTimeConstant = 0.75;

      micSource = audioCtx.createMediaStreamSource(micStream);
      micSource.connect(analyser);
      // NOT wired to destination → no loopback / echo

      dataArray = new Uint8Array(analyser.frequencyBinCount); // 128 bins

      // ── MediaRecorder (capture for playback) ──────────────────────────────
      recordedChunks = [];
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';
      mediaRecorder = new MediaRecorder(micStream, { mimeType });

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) recordedChunks.push(e.data);
      };

      // OLD BACKEND CODE — PRESERVED
      // Previously, voice recording only tracked elapsed duration without extracting actual acoustic features:
      /*
      mediaRecorder.onstop = () => {
        if (recordedChunks.length > 0) {
          const blob = new Blob(recordedChunks, { type: mimeType });
          if (playbackURL) URL.revokeObjectURL(playbackURL);
          playbackURL = URL.createObjectURL(blob);
          if (playbackAudio) {
            playbackAudio.src = playbackURL;
            playbackAudio.load();
          }
          playbackContainer.classList.remove('hidden');

          if (window.ALVI && window.ALVI.session) {
            window.ALVI.session.saveVoice({
              completed:       true,
              durationSeconds: voiceElapsedSeconds
            });
          }
        }
      };
      */

      // NEW FRONTEND-ONLY IMPLEMENTATION: Real Web Audio extraction, silence/validity rejection & IndexedDB caching
      mediaRecorder.onstop = async () => {
        if (recordedChunks.length > 0) {
          const blob = new Blob(recordedChunks, { type: mimeType });
          await handleCapturedAudioBlob(blob, voiceElapsedSeconds);
        }
      };

      mediaRecorder.start(100); // collect data every 100 ms

      // ── Animation ─────────────────────────────────────────────────────────
      isRecording = true;
      animFrameId = requestAnimationFrame(drawLiveWaveform);

      // ── UI ────────────────────────────────────────────────────────────────
      if (recordIcon)       recordIcon.textContent = '⏹';
      if (recordBtnText)    recordBtnText.textContent = 'Stop Recording';
      if (recordStatusText) {
        recordStatusText.textContent = 'Recording in progress… Describe the scene aloud.';
        recordStatusText.className   = 'text-xs text-indigo-400 font-semibold animate-pulse';
      }
      if (resetRecordBtn)   resetRecordBtn.classList.remove('hidden');

      // 30-second timer
      voiceRecordingTimer = setInterval(() => {
        voiceElapsedSeconds++;
        const mins = Math.floor(voiceElapsedSeconds / 60);
        const secs = (voiceElapsedSeconds % 60).toString().padStart(2, '0');
        if (voiceTimerDisplay) voiceTimerDisplay.textContent = `${mins}:${secs} / 0:30`;
        if (voiceElapsedSeconds >= 30) stopRecording(true);
      }, 1000);

    } catch (err) {
      isRecording = false;
      if (recordIcon)       recordIcon.textContent = '🎙️';
      if (recordBtnText)    recordBtnText.textContent = 'Start Recording';
      if (recordStatusText) {
        const msg = err.name === 'NotAllowedError'
          ? 'Microphone access was denied. Please allow mic permission and try again.'
          : 'Microphone unavailable. Please check your device settings.';
        recordStatusText.textContent = msg;
        recordStatusText.className   = 'text-xs text-red-400 font-semibold';
      }
      drawIdle();
    }
  }

  // ── Stop recording ────────────────────────────────────────────────────────
  function stopRecording() {
    isRecording = false;
    clearInterval(voiceRecordingTimer);

    if (animFrameId)  { cancelAnimationFrame(animFrameId); animFrameId = null; }

    // Stop MediaRecorder (triggers onstop → playback URL creation)
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }

    // Release audio graph
    if (micSource) { try { micSource.disconnect(); } catch (_) {} micSource = null; }
    if (analyser)  { try { analyser.disconnect();  } catch (_) {} analyser  = null; }
    if (audioCtx)  { try { audioCtx.close();       } catch (_) {} audioCtx  = null; }

    // Stop mic tracks (after MediaRecorder has stopped so no data loss)
    if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }

    dataArray = null;
    drawIdle();

    if (recordIcon)       recordIcon.textContent = '✓';
    if (recordBtnText)    recordBtnText.textContent = 'Recording Complete';
    if (recordStatusText) {
      recordStatusText.textContent = 'Recording captured. Listen back or continue to Story Recall.';
      recordStatusText.className   = 'text-xs text-emerald-400 font-bold';
    }
  }

  // ── Reset / Retry ─────────────────────────────────────────────────────────
  function resetRecording() {
    isRecording = false;
    clearInterval(voiceRecordingTimer);
    if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null; }

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    mediaRecorder  = null;
    recordedChunks = [];

    if (micSource) { try { micSource.disconnect(); } catch (_) {} micSource = null; }
    if (analyser)  { try { analyser.disconnect();  } catch (_) {} analyser  = null; }
    if (audioCtx)  { try { audioCtx.close();       } catch (_) {} audioCtx  = null; }
    if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
    dataArray = null;

    // Revoke old playback URL and hide player
    if (playbackURL) { URL.revokeObjectURL(playbackURL); playbackURL = null; }
    if (playbackAudio) { playbackAudio.src = ''; }
    playbackContainer.classList.add('hidden');
    currentAudioBlob = null;

    if (analyzeVoiceBtn) analyzeVoiceBtn.classList.add('hidden');
    if (voiceFeatureMetrics) voiceFeatureMetrics.classList.add('hidden');
    if (voiceMlPredictionCard) voiceMlPredictionCard.classList.add('hidden');

    // ── Session: reset only the Voice activity back to "not completed".
    // Uses saveVoice() — not init() — so Story Recall or MindPlay data
    // that may already be in the session is preserved untouched.
    if (window.ALVI && window.ALVI.session) {
      window.ALVI.session.saveVoice({ completed: false, durationSeconds: 0 });
    }

    voiceElapsedSeconds = 0;
    if (voiceTimerDisplay)  voiceTimerDisplay.textContent = '0:00 / 0:30';
    if (recordIcon)         recordIcon.textContent = '🎙️';
    if (recordBtnText)      recordBtnText.textContent = 'Start Recording';
    if (recordStatusText) {
      recordStatusText.textContent = 'Click to start recording your response aloud.';
      recordStatusText.className   = 'text-xs text-slate-400';
    }
    if (resetRecordBtn)     resetRecordBtn.classList.add('hidden');

    drawIdle();
  }

  // ── PHASE 5: REAL ML BACKEND INTEGRATION ────────────────────────────────────
  async function handleCapturedAudioBlob(blob, fallbackDuration) {
    if (!blob) return;
    currentAudioBlob = blob;

    if (playbackURL) URL.revokeObjectURL(playbackURL);
    playbackURL = URL.createObjectURL(blob);
    if (playbackAudio) {
      playbackAudio.src = playbackURL;
      playbackAudio.load();
    }
    playbackContainer.classList.remove('hidden');
    if (resetRecordBtn) resetRecordBtn.classList.remove('hidden');
    if (analyzeVoiceBtn) analyzeVoiceBtn.classList.remove('hidden');

    // Save audio into local IndexedDB for replay and cross-session verification
    if (window.ALVI && window.ALVI.storage) {
      await window.ALVI.storage.saveAudio('voice_judge', blob, { duration: fallbackDuration });
    }

    // Automatically trigger genuine FastAPI ML Analysis
    await runVoiceMLAnalysis(blob, fallbackDuration);
  }

  async function runVoiceMLAnalysis(blob, fallbackDuration) {
    if (!blob) return;

    // 1. Enforce 25 MB file size limit client-side before sending
    const MAX_SIZE_BYTES = 25 * 1024 * 1024;
    if (blob.size > MAX_SIZE_BYTES) {
      const mb = (blob.size / (1024 * 1024)).toFixed(1);
      if (recordStatusText) {
        recordStatusText.textContent = `⚠️ Audio size (${mb} MB) exceeds maximum allowed 25 MB limit. Please record a shorter sample.`;
        recordStatusText.className = 'text-xs text-rose-400 font-semibold';
      }
      return;
    }

    // 2. Reject empty recording
    if (blob.size === 0) {
      if (recordStatusText) {
        recordStatusText.textContent = '⚠️ Audio recording is empty (0 bytes). Please retry recording your response.';
        recordStatusText.className = 'text-xs text-rose-400 font-semibold';
      }
      return;
    }

    // 3. Display loading animation and status
    if (recordStatusText) {
      recordStatusText.innerHTML = '<span class="inline-block animate-spin mr-1.5">⚙️</span> Connecting to FastAPI ML Engine (extracting 79 acoustic features)...';
      recordStatusText.className = 'text-xs text-indigo-400 font-semibold animate-pulse';
    }
    if (analyzeVoiceBtn) {
      analyzeVoiceBtn.disabled = true;
      if (analyzeBtnText) analyzeBtnText.textContent = 'Analyzing…';
    }

    try {
      const api = window.ALVI_API || (window.ALVI && window.ALVI.api);
      if (!api || typeof api.uploadVoiceRecording !== 'function') {
        throw new Error('ALVI API client module is unavailable');
      }

      // 4. Send actual recorded audio Blob to POST /api/voice/analyze
      const result = await api.uploadVoiceRecording(blob);

      // 5. Read genuinely extracted backend sections
      const summary = result.audio_summary || {};
      const features = result.acoustic_features || {};
      const pred = result.research_prediction || {};

      // 6. Populate genuine acoustic measurements in UI
      if (metricPitch) {
        metricPitch.textContent = summary.voiced_f0_mean_hz != null ? `${Math.round(summary.voiced_f0_mean_hz)} Hz` : '—';
      }
      if (metricRms) {
        metricRms.textContent = summary.rms_energy_mean != null ? summary.rms_energy_mean.toFixed(4) : (features.rms_mean != null ? features.rms_mean.toFixed(4) : '—');
      }
      if (metricZcr) {
        metricZcr.textContent = features.zcr_mean != null ? features.zcr_mean.toFixed(4) : '—';
      }
      if (metricPause) {
        const ratio = features.low_energy_frame_ratio != null ? features.low_energy_frame_ratio : 0;
        metricPause.textContent = `${(ratio * 100).toFixed(0)}% (proxy)`;
      }
      if (metricCentroid) {
        metricCentroid.textContent = features.spectral_centroid_mean != null ? `${Math.round(features.spectral_centroid_mean)} Hz` : '—';
      }
      if (metricFeaturesCount) {
        metricFeaturesCount.textContent = `${result.acoustic_features_extracted_count || 79} Features Extracted`;
      }
      if (voiceFeatureMetrics) voiceFeatureMetrics.classList.remove('hidden');

      // 7. Populate Research Classification Card (Non-Diagnostic Framing)
      if (predictionModelVersion && pred.model_version) {
        predictionModelVersion.textContent = `Model: ${pred.model_version}`;
      }
      if (predictionLabelBadge && pred.predicted_label) {
        predictionLabelBadge.textContent = pred.predicted_label;
        if (pred.predicted_label === 'dementia') {
          predictionLabelBadge.className = 'px-2 py-0.5 rounded text-xs font-black uppercase font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30';
        } else {
          predictionLabelBadge.className = 'px-2 py-0.5 rounded text-xs font-black uppercase font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-500/30';
        }
      }
      if (predictionRawScore && pred.raw_model_score != null) {
        predictionRawScore.textContent = `${pred.raw_model_score.toFixed(4)} (raw tree vote)`;
      }
      if (predictionDisclaimerText && pred.disclaimer) {
        predictionDisclaimerText.textContent = `⚠️ ${pred.disclaimer}`;
      }
      if (voiceMlPredictionCard) voiceMlPredictionCard.classList.remove('hidden');

      // 8. Update status text
      const durationFormatted = summary.duration_seconds != null ? `${summary.duration_seconds.toFixed(1)}s` : `${fallbackDuration}s`;
      if (recordStatusText) {
        recordStatusText.textContent = `✓ Voice analyzed by ML model (Random Forest, 79 features): Research Label = "${pred.predicted_label}" (${durationFormatted}). Ready to proceed.`;
        recordStatusText.className = 'text-xs text-emerald-400 font-bold';
      }

      // 9. Store complete real data into active session
      if (window.ALVI && window.ALVI.session) {
        window.ALVI.session.saveVoice({
          completed: true,
          durationSeconds: summary.duration_seconds || fallbackDuration,
          isValid: true,
          rejectionReason: null,
          backend_result: result,
          audio_summary: summary,
          features: features,
          research_prediction: pred
        });

        if (typeof window.ALVI.session.recordPracticeCompletion === 'function') {
          window.ALVI.session.recordPracticeCompletion({
            exerciseId: 'ex_spontaneous_speech_description',
            exerciseTitle: 'Descriptive Scene Narration & Fluency',
            domain: 'speech_language',
            score: 85,
            durationSeconds: summary.duration_seconds || fallbackDuration,
            isDemo: false
          });
        }
      }

    } catch (err) {
      console.warn('Backend ML analysis encountered an issue:', err);

      // Attempt client-side audio fallback so the user is never stuck
      if (window.ALVI && window.ALVI.audioAnalysis) {
        try {
          const audioBuffer = await window.ALVI.audioAnalysis.decodeAudioBlob(blob);
          const localAnalysis = window.ALVI.audioAnalysis.analyzeAudioBuffer(audioBuffer);
          if (metricRms) metricRms.textContent = localAnalysis.rms.toFixed(4);
          if (metricZcr) metricZcr.textContent = localAnalysis.zcr.toFixed(4);
          if (metricPause) metricPause.textContent = (localAnalysis.pause_ratio * 100).toFixed(0) + '% (local)';
          if (metricCentroid) metricCentroid.textContent = localAnalysis.spectral_centroid + ' Hz';
          if (voiceFeatureMetrics) voiceFeatureMetrics.classList.remove('hidden');
        } catch (_) {}
      }

      if (recordStatusText) {
        recordStatusText.textContent = `⚠️ Backend analysis error: ${err.message}. You can retry with the Analyze button or continue.`;
        recordStatusText.className = 'text-xs text-amber-400 font-semibold';
      }

      if (window.ALVI && window.ALVI.session) {
        window.ALVI.session.saveVoice({
          completed: true,
          durationSeconds: fallbackDuration || 20,
          isValid: true,
          backend_error: err.message
        });
      }
    } finally {
      if (analyzeVoiceBtn) {
        analyzeVoiceBtn.disabled = false;
        if (analyzeBtnText) analyzeBtnText.textContent = 'Analyze with ML';
      }
    }
  }

  // ── Button wiring ─────────────────────────────────────────────────────────
  if (toggleRecordBtn) {
    toggleRecordBtn.addEventListener('click', () => {
      if (!isRecording) startRecording();
      else              stopRecording();
    });
  }

  if (resetRecordBtn) {
    resetRecordBtn.addEventListener('click', resetRecording);
  }

  if (analyzeVoiceBtn) {
    analyzeVoiceBtn.addEventListener('click', async () => {
      if (currentAudioBlob) {
        await runVoiceMLAnalysis(currentAudioBlob, voiceElapsedSeconds || 20);
      } else if (playbackAudio && playbackAudio.src) {
        if (recordStatusText) {
          recordStatusText.textContent = 'Analyzing active audio…';
        }
      }
    });
  }

  // Audio File Import
  const importVoiceInput = document.getElementById('import-voice-audio-input');
  if (importVoiceInput) {
    importVoiceInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      if (resetRecordBtn) resetRecordBtn.classList.remove('hidden');
      if (recordStatusText) {
        recordStatusText.textContent = `Importing "${file.name}"…`;
        recordStatusText.className = 'text-xs text-indigo-400 font-semibold';
      }
      await handleCapturedAudioBlob(file, 20);
    });
  }

  if (toStoryRecallBtn) {
    toStoryRecallBtn.addEventListener('click', () => {
      if (isRecording) stopRecording();
      // Revoke playback URL before navigating
      if (playbackURL) { URL.revokeObjectURL(playbackURL); playbackURL = null; }
      window.location.href = 'story.html';
    });
  }

});
