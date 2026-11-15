/**
 * ALVI — Unified Introduction Flow Controller
 * Orchestrates: Stage 1 (3D Anatomical Brain) → Stage 2 (Timmy Companion) → Stage 3 (Dashboard)
 */

(function () {
  'use strict';

  // ── DOM References ──
  const stageBrain = document.getElementById('stage-brain');
  const stageTimmy = document.getElementById('stage-timmy');
  const btnSkipToTimmy = document.getElementById('skip-to-timmy');
  const btnSkipToDash = document.getElementById('skip-to-dashboard');
  const btnVoiceSpeak = document.getElementById('timmy-voice-btn');
  const btnReplayIntro = document.getElementById('intro-replay');

  // Timmy Elements
  const timmySvg = document.getElementById('timmy-svg');
  const bodyPath = document.getElementById('timmy-body');
  const pupilL = document.getElementById('timmy-pupil-l');
  const pupilR = document.getElementById('timmy-pupil-r');
  const mouthEl = document.getElementById('timmy-mouth');
  const thinkBbl = document.getElementById('timmy-think');
  const responseEl = document.getElementById('timmy-response');
  const continueBtn = document.getElementById('timmy-continue');
  const moodPills = document.querySelectorAll('.mood-pill');

  // State
  let currentStage = 1; // 1: Brain, 2: Timmy
  let isSpeaking = false;
  const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Eye tracking constants (viewBox 460x460)
  const L_EYE = { x: 158, y: 218 };
  const R_EYE = { x: 285, y: 224 };
  const L_MAX = { x: 18, y: 24 };
  const R_MAX = { x: 20, y: 22 };

  let currentL = { x: 0, y: 0 };
  let currentR = { x: 0, y: 0 };
  let targetL = { x: 0, y: 0 };
  let targetR = { x: 0, y: 0 };
  let eyeRafId = null;
  let blinkTimer = null;

  const MOOD_DATA = {
    happy: {
      response: 'Glad to hear that! Positive energy brings wonderful cognitive clarity.',
      mouth: 'M 193,336 Q 220,352 247,336',
      speech: "Glad to hear that! Positive energy brings wonderful cognitive clarity."
    },
    calm: {
      response: 'A calm, centered breath is the perfect place to begin your session.',
      mouth: 'M 196,340 Q 220,347 244,340',
      speech: "A calm, centered breath is the perfect place to begin your session."
    },
    tired: {
      response: 'Take it gently today. There is absolutely no rush in your assessment.',
      mouth: 'M 198,342 L 242,342',
      speech: "Take it gently today. There is absolutely no rush in your assessment."
    },
    sad: {
      response: "Thank you for sharing. We're here with you, at your own pace.",
      mouth: 'M 196,344 Q 220,337 244,344',
      speech: "Thank you for sharing. We're here with you, at your own pace."
    },
    anxious: {
      response: 'Take a slow, deep breath. There are no right or wrong answers here.',
      mouth: 'M 196,342 Q 207,338 220,343 Q 233,339 244,342',
      speech: "Take a slow, deep breath. There are no right or wrong answers here."
    },
    okay: {
      response: "Steady and balanced. Let's take today's cognitive journey together.",
      mouth: 'M 196,340 Q 220,346 244,340',
      speech: "Steady and balanced. Let's take today's cognitive journey together."
    }
  };

  // ── Hook into Brain Animation Completion ──
  window.ALVI_INTRO_ON_COMPLETE = function () {
    if (currentStage === 1) {
      switchToTimmy();
    }
  };

  window.ALVI_INTRO_ON_SKIP = function () {
    if (currentStage === 1) {
      switchToTimmy();
    }
  };

  // ── Stage 1 → Stage 2 Transition ──
  function switchToTimmy() {
    if (currentStage === 2) return;
    currentStage = 2;

    stageBrain.classList.add('stage-hidden');
    stageTimmy.classList.add('stage-active');

    // Start Timmy animations
    initTimmyDrawOn();
    initEyeTracking();
    scheduleBlink();

    // Trigger introductory speech (friendly, safe, non-blocking)
    setTimeout(() => {
      speakGreeting("Hello! I'm Timmy, your ALVI companion. Let's explore your cognitive wellness journey!");
    }, 600);
  }

  // ── Replay Function ──
  function replayBrain() {
    currentStage = 1;
    stageTimmy.classList.remove('stage-active');
    stageBrain.classList.remove('stage-hidden');

    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    cancelAnimationFrame(eyeRafId);
    clearTimeout(blinkTimer);

    // If 3D controller has replay button or method, trigger it
    const previewReplay = document.getElementById('preview-replay');
    if (previewReplay) {
      previewReplay.click();
    } else {
      window.location.reload();
    }
  }

  // ── Timmy SVG Draw-on ──
  function initTimmyDrawOn() {
    if (!bodyPath) return;

    if (isReducedMotion) {
      bodyPath.style.strokeDasharray = 'none';
      bodyPath.style.strokeDashoffset = '0';
      return;
    }

    try {
      const len = bodyPath.getTotalLength() || 1350;
      bodyPath.style.strokeDasharray = len;
      bodyPath.style.strokeDashoffset = len;
      bodyPath.getBoundingClientRect(); // force reflow

      bodyPath.style.transition = 'stroke-dashoffset 1.1s cubic-bezier(0.25, 1, 0.5, 1)';
      bodyPath.style.strokeDashoffset = '0';
    } catch (_) {
      bodyPath.style.strokeDasharray = 'none';
      bodyPath.style.strokeDashoffset = '0';
    }
  }

  // ── Timmy Eye Tracking ──
  function initEyeTracking() {
    if (isReducedMotion) return;

    function onPointerMove(e) {
      if (currentStage !== 2 || !timmySvg) return;

      const rect = timmySvg.getBoundingClientRect();
      if (!rect.width || !rect.height) return;

      const clientX = e.clientX || (e.touches && e.touches[0] ? e.touches[0].clientX : window.innerWidth / 2);
      const clientY = e.clientY || (e.touches && e.touches[0] ? e.touches[0].clientY : window.innerHeight / 2);

      // SVG coordinate projection
      const scaleX = 460 / rect.width;
      const scaleY = 460 / rect.height;
      const svgX = (clientX - rect.left) * scaleX;
      const svgY = (clientY - rect.top) * scaleY;

      const dxL = svgX - L_EYE.x;
      const dyL = svgY - L_EYE.y;
      const distL = Math.hypot(dxL, dyL) || 1;
      const factorL = Math.min(1, distL / 140);
      targetL.x = (dxL / distL) * L_MAX.x * factorL;
      targetL.y = (dyL / distL) * L_MAX.y * factorL;

      const dxR = svgX - R_EYE.x;
      const dyR = svgY - R_EYE.y;
      const distR = Math.hypot(dxR, dyR) || 1;
      const factorR = Math.min(1, distR / 140);
      targetR.x = (dxR / distR) * R_MAX.x * factorR;
      targetR.y = (dyR / distR) * R_MAX.y * factorR;
    }

    window.addEventListener('mousemove', onPointerMove, { passive: true });
    window.addEventListener('touchmove', onPointerMove, { passive: true });

    function renderEyes() {
      if (currentStage === 2) {
        currentL.x += (targetL.x - currentL.x) * 0.16;
        currentL.y += (targetL.y - currentL.y) * 0.16;
        currentR.x += (targetR.x - currentR.x) * 0.16;
        currentR.y += (targetR.y - currentR.y) * 0.16;

        if (pupilL) pupilL.style.transform = `translate(${currentL.x.toFixed(2)}px, ${currentL.y.toFixed(2)}px)`;
        if (pupilR) pupilR.style.transform = `translate(${currentR.x.toFixed(2)}px, ${currentR.y.toFixed(2)}px)`;
      }
      eyeRafId = requestAnimationFrame(renderEyes);
    }

    eyeRafId = requestAnimationFrame(renderEyes);
  }

  // ── Timmy Blinking ──
  function scheduleBlink() {
    if (isReducedMotion) return;
    blinkTimer = setTimeout(() => {
      const scene = document.querySelector('.timmy-scene');
      if (scene) {
        scene.classList.add('blinking');
        setTimeout(() => {
          scene.classList.remove('blinking');
          scheduleBlink();
        }, 120);
      } else {
        scheduleBlink();
      }
    }, 4000 + Math.random() * 3500);
  }

  // ── Mood Selection Interaction ──
  moodPills.forEach(pill => {
    pill.addEventListener('click', () => {
      const moodKey = pill.getAttribute('data-mood');
      const data = MOOD_DATA[moodKey];
      if (!data) return;

      moodPills.forEach(p => {
        p.setAttribute('aria-pressed', p === pill ? 'true' : 'false');
        p.classList.toggle('selected', p === pill);
      });

      if (mouthEl) {
        mouthEl.setAttribute('d', data.mouth);
      }

      if (responseEl) {
        responseEl.textContent = data.response;
        responseEl.classList.remove('visible');
        void responseEl.offsetWidth; // force reflow
        responseEl.classList.add('visible');
      }

      // Highlight continue button
      if (continueBtn) {
        continueBtn.classList.add('active');
        continueBtn.focus();
      }

      // Speak response gently
      speakGreeting(data.speech);

      // Persist mood to sessionStorage
      try {
        sessionStorage.setItem('alvi_user_mood', moodKey);
        sessionStorage.setItem('alvi_mood_timestamp', new Date().toISOString());
      } catch (_) {}
    });
  });

  // ── Speech Synthesis (Optional, Safe, Non-Blocking) ──
  function speakGreeting(text) {
    if (!('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 1.0;
      u.pitch = 1.12;

      const voices = window.speechSynthesis.getVoices();
      const gentleVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha') || v.name.includes('Jenny')));
      if (gentleVoice) u.voice = gentleVoice;

      u.onstart = () => {
        isSpeaking = true;
        btnVoiceSpeak && btnVoiceSpeak.classList.add('is-speaking');
      };
      u.onend = u.onerror = () => {
        isSpeaking = false;
        btnVoiceSpeak && btnVoiceSpeak.classList.remove('is-speaking');
      };

      window.speechSynthesis.speak(u);
    } catch (err) {
      console.warn('Speech synthesis error:', err);
    }
  }

  // ── Navigation & Persistence ──
  function markIntroCompleted() {
    try {
      sessionStorage.setItem('alvi_intro_completed', 'true');
    } catch (_) {}
  }

  if (continueBtn) {
    continueBtn.addEventListener('click', markIntroCompleted);
  }

  if (btnSkipToTimmy) {
    btnSkipToTimmy.addEventListener('click', (e) => {
      e.preventDefault();
      switchToTimmy();
    });
  }

  if (btnSkipToDash) {
    btnSkipToDash.addEventListener('click', markIntroCompleted);
  }

  if (btnVoiceSpeak) {
    btnVoiceSpeak.addEventListener('click', () => {
      speakGreeting("Hello! I'm Timmy, your ALVI companion. Let's explore your cognitive wellness journey!");
    });
  }

  if (btnReplayIntro) {
    btnReplayIntro.addEventListener('click', (e) => {
      e.preventDefault();
      replayBrain();
    });
  }

  // Keyboard accessibility
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (currentStage === 1) {
        switchToTimmy();
      }
    }
  });

})();
