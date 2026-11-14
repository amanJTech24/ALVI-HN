// Story Recall Script
// Waveform: real mic via Web Audio API AnalyserNode (bar style).
// Playback: MediaRecorder captures audio; object URL presented after stop.

document.addEventListener('DOMContentLoaded', () => {

  // ── Story read-aloud (TTS) ────────────────────────────────────────────────
  const playStoryAudioBtn = document.getElementById('play-story-audio-btn');
  const audioPlayIcon     = document.getElementById('audio-play-icon');
  const audioPlayText     = document.getElementById('audio-play-text');

  let isPlayingTTS = false;

  if (playStoryAudioBtn) {
    playStoryAudioBtn.addEventListener('click', () => {
      if (!isPlayingTTS) {
        isPlayingTTS = true;
        if (audioPlayIcon) audioPlayIcon.textContent = '⏸';
        if (audioPlayText) audioPlayText.textContent = 'Playing Story...';

        if ('speechSynthesis' in window) {
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(
            'One rainy morning, Aarav left his home carrying a blue umbrella. ' +
            'He walked to the local market and bought three red apples. ' +
            'On his way back, he met his friend Meera and gave her one apple before returning home.'
          );
          utterance.rate = 0.9;
          utterance.onend = () => {
            isPlayingTTS = false;
            if (audioPlayIcon) audioPlayIcon.textContent = '▶';
            if (audioPlayText) audioPlayText.textContent = 'Listen to Story';
          };
          window.speechSynthesis.speak(utterance);
        } else {
          setTimeout(() => {
            isPlayingTTS = false;
            if (audioPlayIcon) audioPlayIcon.textContent = '▶';
            if (audioPlayText) audioPlayText.textContent = 'Listen to Story';
          }, 8000);
        }
      } else {
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        isPlayingTTS = false;
        if (audioPlayIcon) audioPlayIcon.textContent = '▶';
        if (audioPlayText) audioPlayText.textContent = 'Listen to Story';
      }
    });
  }

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const recordStoryBtn    = document.getElementById('record-story-btn');
  const storyRecordStatus = document.getElementById('story-record-status');
  const storyTimer        = document.getElementById('story-timer');
  const toMindplayBtn     = document.getElementById('to-mindplay-btn');
  const storyCanvas       = document.getElementById('story-waveform-canvas');

  if (!storyCanvas) return;
  const storyCtx = storyCanvas.getContext('2d');

  // ── State ─────────────────────────────────────────────────────────────────
  let isRecordingStory    = false;
  let storyTimerInterval  = null;
  let storyElapsed        = 0;
  let animFrameId         = null;

  // Web Audio API
  let audioCtx   = null;
  let analyser   = null;
  let micSource  = null;
  let micStream  = null;
  let dataArray  = null;

  // MediaRecorder
  let mediaRecorder  = null;
  let recordedChunks = [];
  let playbackURL    = null;

  // Story Recall NLP Evaluation State
  let recognition = null;
  let liveTranscript = '';
  let isEvaluatingNLP = false;

  /**
   * Evaluates participant recall transcript using the explainable FastAPI NLP engine.
   * Handles both voice Speech-to-Text and typed input modes.
   */
  async function scoreStoryRecall(transcriptText, timingSeconds, inputMode = 'voice') {
    const text = (transcriptText || '').trim();

    const scoreCard = document.getElementById('fact-scoring-card');
    const scoreHeading = document.getElementById('fact-score-heading');
    const scoreBadge = document.getElementById('fact-score-badge');
    const bandDesc = document.getElementById('fact-band-desc');
    const recalledList = document.getElementById('facts-recalled-list');
    const missedList = document.getElementById('facts-missed-list');
    const recalledCountPill = document.getElementById('recalled-count-pill');
    const missedCountPill = document.getElementById('missed-count-pill');
    const metricCompleteness = document.getElementById('metric-completeness');
    const metricSemantic = document.getElementById('metric-semantic');
    const metricSequence = document.getElementById('metric-sequence');
    const seqBox = document.getElementById('story-sequence-box');
    const seqText = document.getElementById('story-sequence-text');
    const intrusionsBox = document.getElementById('story-intrusions-box');
    const intrusionsText = document.getElementById('story-intrusions-text');
    const disclaimerEl = document.getElementById('story-scoring-disclaimer');

    if (!text) {
      if (scoreCard) scoreCard.classList.remove('hidden');
      if (scoreHeading) scoreHeading.textContent = 'No Recall Transcript Captured';
      if (scoreBadge) {
        scoreBadge.textContent = '0%';
        scoreBadge.className = 'text-xs font-bold px-3 py-1 rounded-full bg-slate-500 text-white';
      }
      if (bandDesc) bandDesc.textContent = 'Please record your speech or type what you remember from Aarav’s story.';
      if (recalledList) recalledList.innerHTML = '<li class="italic text-slate-400">No words detected</li>';
      if (missedList) missedList.innerHTML = '<li class="italic text-slate-400">All 8 facts missed (empty response)</li>';
      if (recalledCountPill) recalledCountPill.textContent = '0';
      if (missedCountPill) missedCountPill.textContent = '8';
      return null;
    }

    // 1. Enter Loading State
    isEvaluatingNLP = true;
    if (scoreCard) scoreCard.classList.remove('hidden');
    if (scoreHeading) scoreHeading.textContent = 'Evaluating narrative with NLP engine…';
    if (scoreBadge) {
      scoreBadge.textContent = '⏳';
      scoreBadge.className = 'text-xs font-bold px-3 py-1 rounded-full bg-purple-500 text-white animate-pulse';
    }
    if (bandDesc) bandDesc.textContent = 'Analyzing completeness, semantics, and chronology…';
    if (recalledList) recalledList.innerHTML = '<li class="italic text-purple-600 animate-pulse">Running semantic matching…</li>';
    if (missedList) missedList.innerHTML = '<li class="italic text-slate-400">Comparing with story bank…</li>';
    if (seqBox) seqBox.classList.add('hidden');
    if (intrusionsBox) intrusionsBox.classList.add('hidden');

    try {
      if (!window.ALVI_API || typeof window.ALVI_API.evaluateStoryRecall !== 'function') {
        throw new Error('ALVI_API client is not loaded. Please verify api.js inclusion.');
      }

      const result = await window.ALVI_API.evaluateStoryRecall({
        storyId: 'aarav_story_v1',
        transcript: text,
        inputMode: inputMode,
        timingSeconds: timingSeconds || 20
      });

      // 2. Render Real Backend NLP Results
      const recalledUnits = result.recalled_units || [];
      const missedUnits = result.missed_units || [];
      const totalUnits = (result.metrics && result.metrics.total_units_count) || 8;
      const composite = Math.round(result.composite_score || 0);

      if (scoreHeading) {
        scoreHeading.textContent = `Score: ${recalledUnits.length} / ${totalUnits} Units (${composite}%) — ${result.performance_band}`;
      }

      if (bandDesc) {
        bandDesc.textContent = result.band_description || '';
      }

      if (scoreBadge) {
        scoreBadge.textContent = `${composite}%`;
        scoreBadge.className = composite >= 85
          ? 'text-xs font-bold px-3 py-1 rounded-full bg-emerald-600 text-white'
          : (composite >= 65
            ? 'text-xs font-bold px-3 py-1 rounded-full bg-teal-600 text-white'
            : (composite >= 40
              ? 'text-xs font-bold px-3 py-1 rounded-full bg-amber-600 text-white'
              : 'text-xs font-bold px-3 py-1 rounded-full bg-purple-600 text-white'));
      }

      // Metrics Pills
      if (metricCompleteness && result.metrics) {
        metricCompleteness.textContent = `${result.metrics.completeness_score}%`;
      }
      if (metricSemantic && result.metrics) {
        metricSemantic.textContent = `${result.metrics.semantic_similarity_score}%`;
      }
      if (metricSequence && result.metrics) {
        metricSequence.textContent = `${result.metrics.sequence_accuracy_score}%`;
      }

      // Unit Detail Lists
      const unitDetails = result.information_units_detail || [];
      const matchedItems = unitDetails.filter(u => u.is_matched && !u.is_negated);
      const omittedItems = unitDetails.filter(u => !u.is_matched || u.is_negated);

      if (recalledCountPill) recalledCountPill.textContent = String(matchedItems.length);
      if (missedCountPill) missedCountPill.textContent = String(omittedItems.length);

      if (recalledList) {
        recalledList.innerHTML = matchedItems.length > 0
          ? matchedItems.map(u => {
              const badgeBg = u.match_type === 'exact'
                ? 'bg-emerald-100 text-emerald-800'
                : (u.match_type === 'paraphrase' ? 'bg-indigo-100 text-indigo-800' : 'bg-amber-100 text-amber-800');
              return `<li class="flex items-center justify-between text-xs py-0.5 border-b border-purple-100/50">
                <span class="flex items-center gap-1.5 font-semibold text-emerald-700">
                  <span>✓</span><span>${u.label}</span>
                </span>
                <span class="text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${badgeBg}">
                  ${u.match_type} (+${u.points_awarded})
                </span>
              </li>`;
            }).join('')
          : '<li class="italic text-slate-400">No key narrative units identified</li>';
      }

      if (missedList) {
        missedList.innerHTML = omittedItems.length > 0
          ? omittedItems.map(u => {
              const statusTag = u.is_negated
                ? '<span class="text-[9px] uppercase font-bold px-1.5 py-0.5 rounded bg-rose-100 text-rose-800">Negated</span>'
                : '<span class="text-[9px] text-slate-400 italic">Omitted</span>';
              return `<li class="flex items-center justify-between text-xs py-0.5 border-b border-slate-100">
                <span class="flex items-center gap-1.5 text-slate-500">
                  <span>${u.is_negated ? '⊘' : '✗'}</span><span>${u.label}</span>
                </span>
                ${statusTag}
              </li>`;
            }).join('')
          : '<li class="italic text-emerald-600 font-semibold">All units successfully recalled!</li>';
      }

      // Temporal Sequence Flow
      if (seqBox && seqText) {
        if (result.observed_sequence && result.observed_sequence.length > 1) {
          const invText = result.metrics.sequence_inversions === 0
            ? '✓ Preserved Chronology'
            : `(${result.metrics.sequence_inversions} temporal inversion${result.metrics.sequence_inversions > 1 ? 's' : ''})`;
          seqText.textContent = `${result.observed_sequence.join(' ➔ ')} · ${invText}`;
          seqBox.classList.remove('hidden');
        } else {
          seqBox.classList.add('hidden');
        }
      }

      // Narrative Intrusions Box
      if (intrusionsBox && intrusionsText) {
        if (result.intrusions_detected && result.intrusions_detected.length > 0) {
          intrusionsText.textContent = result.intrusions_detected.map(i => `"${i.concept}"`).join(', ');
          intrusionsBox.classList.remove('hidden');
        } else {
          intrusionsBox.classList.add('hidden');
        }
      }

      // Disclaimer
      if (disclaimerEl) {
        disclaimerEl.textContent = result.disclaimer || '';
      }

      // Save to Session
      if (window.ALVI && window.ALVI.session) {
        window.ALVI.session.saveStory({
          completed: true,
          durationSeconds: timingSeconds || 20,
          transcript: text,
          recalled_facts: recalledUnits,
          missed_facts: missedUnits,
          score_percent: composite,
          composite_score: result.composite_score,
          performance_band: result.performance_band,
          metrics: result.metrics,
          information_units_detail: result.information_units_detail,
          observed_sequence: result.observed_sequence,
          intrusions_detected: result.intrusions_detected,
          input_mode: inputMode,
          disclaimer: result.disclaimer
        });

        if (typeof window.ALVI.session.recordPracticeCompletion === 'function') {
          window.ALVI.session.recordPracticeCompletion({
            exerciseId: 'ex_narrative_retell_foundations',
            exerciseTitle: 'Narrative Recall & Anchor Retrieval',
            domain: 'memory',
            score: composite,
            durationSeconds: timingSeconds || 20,
            isDemo: false
          });
        }
      }

      return result;

    } catch (err) {
      console.error('[ALVI Story NLP] Evaluation error:', err);
      if (scoreHeading) scoreHeading.textContent = 'Story Evaluation Notice';
      if (scoreBadge) {
        scoreBadge.textContent = '!';
        scoreBadge.className = 'text-xs font-bold px-3 py-1 rounded-full bg-rose-600 text-white';
      }
      if (bandDesc) {
        bandDesc.textContent = `Backend NLP error: ${err.message}. Please verify the FastAPI backend is running on http://127.0.0.1:8765.`;
      }
      if (recalledList) {
        recalledList.innerHTML = `<li class="text-rose-600 text-xs">Could not reach NLP evaluation endpoint at port 8765.</li>`;
      }
      return null;
    } finally {
      isEvaluatingNLP = false;
    }
  }

  // ── Playback element (injected into the dark recording panel) ─────────────
  const playbackContainer = document.createElement('div');
  playbackContainer.id    = 'story-playback-container';
  playbackContainer.className = 'hidden flex items-center gap-3';
  playbackContainer.innerHTML =
    '<span class="text-xs text-emerald-400 font-semibold">▶ Your retell:</span>' +
    '<audio id="story-playback-audio" controls class="h-8 rounded-lg" style="max-width:220px;filter:invert(1) hue-rotate(270deg) brightness(0.85)"></audio>';

  // Insert after the status span, inside the dark panel's flex row
  const storyBtnRow = recordStoryBtn ? recordStoryBtn.parentNode : null;
  if (storyBtnRow) {
    storyBtnRow.parentNode.insertBefore(playbackContainer, storyBtnRow.nextSibling);
  }
  const playbackAudio = document.getElementById('story-playback-audio');

  // ── Canvas: stamp pixel dimensions every frame ────────────────────────────
  function stampCanvas() {
    const parent = storyCanvas.parentElement;
    const w = parent ? parent.clientWidth  : storyCanvas.offsetWidth;
    const h = parent ? parent.clientHeight : storyCanvas.offsetHeight;
    if (w > 0 && storyCanvas.width  !== w) storyCanvas.width  = w;
    if (h > 0 && storyCanvas.height !== h) storyCanvas.height = h;
  }

  // ── Idle bar baseline ─────────────────────────────────────────────────────
  function drawIdle() {
    stampCanvas();
    if (storyCanvas.width === 0 || storyCanvas.height === 0) return;
    storyCtx.clearRect(0, 0, storyCanvas.width, storyCanvas.height);
    const bars    = 45;
    const barW    = (storyCanvas.width / bars) - 2;
    const centerY = storyCanvas.height / 2;
    storyCtx.fillStyle = '#334155';
    for (let i = 0; i < bars; i++) {
      const x = i * (barW + 2);
      const h = 3;
      storyCtx.beginPath();
      if (storyCtx.roundRect) storyCtx.roundRect(x, centerY - h / 2, barW, h, 2);
      else storyCtx.rect(x, centerY - h / 2, barW, h);
      storyCtx.fill();
    }
  }

  drawIdle();

  // ── Live waveform loop (frequency bars, purple for story retell) ──────────
  function drawLiveWaveform() {
    if (!isRecordingStory || !analyser) return;
    animFrameId = requestAnimationFrame(drawLiveWaveform);

    stampCanvas();
    const W = storyCanvas.width;
    const H = storyCanvas.height;
    if (W === 0 || H === 0) return;

    analyser.getByteFrequencyData(dataArray);
    storyCtx.clearRect(0, 0, W, H);

    const bars    = 45;
    const barW    = (W / bars) - 2;
    const centerY = H / 2;

    for (let i = 0; i < bars; i++) {
      const binIndex = Math.floor(i * dataArray.length / bars);
      const amplitude = dataArray[binIndex] / 255;
      const h = Math.max(3, amplitude * H * 0.85);
      const x = i * (barW + 2);
      const y = centerY - h / 2;

      storyCtx.fillStyle = '#A855F7';   // purple — distinct from voice (indigo)
      storyCtx.beginPath();
      if (storyCtx.roundRect) storyCtx.roundRect(x, y, barW, h, 2);
      else storyCtx.rect(x, y, barW, h);
      storyCtx.fill();
    }
  }

  // ── Start retell recording ────────────────────────────────────────────────
  async function startStoryRecording() {
    isRecordingStory = false;
    storyElapsed     = 0;
    if (storyTimer) storyTimer.textContent = '0:00 / 0:45';

    // ── Session: clear any previously saved Story result so that a re-take
    // does not leave a stale "completed: true" from the previous attempt.
    // This is the Story equivalent of Retry — the user clicked Record Retell
    // again after already recording once. Voice and MindPlay data are
    // untouched because saveStory() only merges the story namespace.
    if (window.ALVI && window.ALVI.session) {
      window.ALVI.session.saveStory({ completed: false, durationSeconds: 0 });
    }

    if (recordStoryBtn) recordStoryBtn.textContent = '⏳ Requesting mic…';
    if (storyRecordStatus) {
      storyRecordStatus.textContent = 'Waiting for microphone permission…';
      storyRecordStatus.className   = 'text-xs text-slate-400';
    }
    playbackContainer.classList.add('hidden');

    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });

      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === 'suspended') await audioCtx.resume();

      analyser = audioCtx.createAnalyser();
      analyser.fftSize               = 256;
      analyser.smoothingTimeConstant = 0.75;

      micSource = audioCtx.createMediaStreamSource(micStream);
      micSource.connect(analyser);

      dataArray = new Uint8Array(analyser.frequencyBinCount);

      // NEW FRONTEND-ONLY IMPLEMENTATION: Browser speech-to-text
      liveTranscript = '';
      const transcriptEl = document.getElementById('stt-transcript-text');
      if (transcriptEl) {
        transcriptEl.textContent = 'Listening to retell… Speak clearly.';
        transcriptEl.className = 'text-xs text-purple-600 font-semibold animate-pulse';
      }

      if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
        try {
          const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
          recognition = new SpeechRec();
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = 'en-US';

          recognition.onresult = (evt) => {
            let str = '';
            for (let i = 0; i < evt.results.length; i++) {
              str += evt.results[i][0].transcript + ' ';
            }
            liveTranscript = str.trim();
            if (transcriptEl) {
              transcriptEl.textContent = liveTranscript || 'Listening…';
              transcriptEl.className = 'text-xs text-slate-800 font-medium';
            }
          };
          recognition.start();
        } catch (_) {}
      }

      // MediaRecorder for playback blob
      recordedChunks = [];
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';
      mediaRecorder = new MediaRecorder(micStream, { mimeType });

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) recordedChunks.push(e.data);
      };

      // OLD BACKEND CODE — PRESERVED
      // Previous simple duration save without speech transcription or transparent rule scoring
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
            window.ALVI.session.saveStory({
              completed:       true,
              durationSeconds: storyElapsed
            });
          }
        }
      };
      */

      // NEW FRONTEND-ONLY IMPLEMENTATION: Save to IndexedDB & evaluate transparent fact matching
      mediaRecorder.onstop = async () => {
        if (recordedChunks.length > 0) {
          const blob = new Blob(recordedChunks, { type: mimeType });
          if (playbackURL) URL.revokeObjectURL(playbackURL);
          playbackURL = URL.createObjectURL(blob);
          if (playbackAudio) {
            playbackAudio.src = playbackURL;
            playbackAudio.load();
          }
          playbackContainer.classList.remove('hidden');

          if (window.ALVI && window.ALVI.storage) {
            await window.ALVI.storage.saveAudio('story_judge', blob, { duration: storyElapsed });
          }

          const typedInput = document.getElementById('typed-retell-input');
          const textToScore = liveTranscript || (typedInput ? typedInput.value : '');
          await scoreStoryRecall(textToScore, storyElapsed, 'voice');
        }
      };

      mediaRecorder.start(100);

      isRecordingStory = true;
      animFrameId = requestAnimationFrame(drawLiveWaveform);

      if (recordStoryBtn) recordStoryBtn.textContent = '⏹ Stop Retell';
      if (storyRecordStatus) {
        storyRecordStatus.textContent = 'Recording retell… Speaking key story elements.';
        storyRecordStatus.className   = 'text-xs text-purple-400 font-semibold animate-pulse';
      }

      storyTimerInterval = setInterval(() => {
        storyElapsed++;
        const mins = Math.floor(storyElapsed / 60);
        const secs = (storyElapsed % 60).toString().padStart(2, '0');
        if (storyTimer) storyTimer.textContent = `${mins}:${secs} / 0:45`;
        if (storyElapsed >= 45) stopStoryRecording();
      }, 1000);

    } catch (err) {
      isRecordingStory = false;
      if (recordStoryBtn) recordStoryBtn.textContent = '🎙 Record Retell';
      if (storyRecordStatus) {
        const msg = err.name === 'NotAllowedError'
          ? 'Microphone access was denied. Please allow permission and try again.'
          : 'Microphone unavailable. Please check your device settings.';
        storyRecordStatus.textContent = msg;
        storyRecordStatus.className   = 'text-xs text-red-400 font-semibold';
      }
      drawIdle();
    }
  }

  // ── Stop retell recording ─────────────────────────────────────────────────
  function stopStoryRecording() {
    isRecordingStory = false;
    clearInterval(storyTimerInterval);

    if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null; }

    // Stop Speech Recognition if active
    if (recognition) {
      try { recognition.stop(); } catch (_) {}
      recognition = null;
    }

    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();

    if (micSource) { try { micSource.disconnect(); } catch (_) {} micSource = null; }
    if (analyser)  { try { analyser.disconnect();  } catch (_) {} analyser  = null; }
    if (audioCtx)  { try { audioCtx.close();       } catch (_) {} audioCtx  = null; }
    if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }

    dataArray = null;
    drawIdle();

    if (recordStoryBtn) recordStoryBtn.textContent = '✓ Retell Captured';
    if (storyRecordStatus) {
      storyRecordStatus.textContent = 'Retell captured. Listen back or continue to MindPlay.';
      storyRecordStatus.className   = 'text-xs text-emerald-400 font-bold';
    }
  }

  // ── Button wiring ─────────────────────────────────────────────────────────
  if (recordStoryBtn) {
    recordStoryBtn.addEventListener('click', () => {
      if (!isRecordingStory) startStoryRecording();
      else                   stopStoryRecording();
    });
  }

  // NEW FRONTEND-ONLY IMPLEMENTATION: Typed Fallback Controls
  const toggleTypedBtn = document.getElementById('toggle-typed-fallback-btn');
  const typedContainer = document.getElementById('typed-fallback-container');
  const sttContainer = document.getElementById('stt-live-container');
  const scoreTypedBtn = document.getElementById('score-typed-retell-btn');
  const typedInput = document.getElementById('typed-retell-input');

  if (toggleTypedBtn && typedContainer) {
    toggleTypedBtn.addEventListener('click', () => {
      const isHidden = typedContainer.classList.contains('hidden');
      if (isHidden) {
        typedContainer.classList.remove('hidden');
        if (sttContainer) sttContainer.classList.add('hidden');
        toggleTypedBtn.textContent = '🎙️ Switch to Voice Recording';
      } else {
        typedContainer.classList.add('hidden');
        if (sttContainer) sttContainer.classList.remove('hidden');
        toggleTypedBtn.textContent = '⌨️ Switch to Typed Retell';
      }
    });
  }

  if (scoreTypedBtn && typedInput) {
    scoreTypedBtn.addEventListener('click', async () => {
      const text = typedInput.value;
      if (!text || text.trim().length === 0) {
        alert('Please type what you remember from the story before evaluating.');
        return;
      }
      await scoreStoryRecall(text, 25, 'typed');
    });
  }

  if (toMindplayBtn) {
    toMindplayBtn.addEventListener('click', () => {
      if (isRecordingStory) stopStoryRecording();
      if (playbackURL) { URL.revokeObjectURL(playbackURL); playbackURL = null; }
      window.location.href = 'mindplay.html';
    });
  }

});
