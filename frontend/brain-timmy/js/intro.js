/* ═══════════════════════════════════════════════════════════════════════════
   ALVI — Cinematic Introduction Controller
   Dual Mode: Direct Windows File Explorer (file:///) & GitHub Pages (https://)
   Approved 437-Structure Layered Anatomical Brain Sequence
   ═══════════════════════════════════════════════════════════════════════════ */

window.startAlviCinematicIntro = function(THREE, GLTFLoader, DRACOLoader) {
  'use strict';
/* ═══════════════════════════════════════════════════════════════════════════
   ALVI — Cinematic Introduction Controller  (Milestone 4)
   Approved 437-Structure Layered Anatomical Brain Sequence

   Choreography:
   - Scene 1 (0.0 – 0.7s): Giant Brain Emergence in center
   - Scene 2 (0.7 – 3.0s): Full 360° anatomical rotation (continuous, no slerp)
   - Scene 3 (3.0 – 4.0s): Brain shrinks 62% & glides right (viewport-safe)
   - Scene 4 (3.5 – 4.3s): Large ALVI wordmark reveal (middle-left)
   - Scene 5 (4.0 – 5.3s): Final composition hold with ambient drift
   - 5.3s → Transition to Timmy (normal mode) / hold forever (preview=1)
   ═══════════════════════════════════════════════════════════════════════════ */




  // ── Configuration ────────────────────────────────────────────────────────
  const CONFIG = {
    modelPath: 'assets/models/anatomical_brain.glb',
    manifestPath: 'assets/models/manifest.json',
    dracoDecoderPath: 'https://www.gstatic.com/draco/versioned/decoders/1.5.7/',
    bgColor: 0x020810,

    // Timeline Keyframes (seconds) — Milestone 4 / Full 360° rotation
    tEmergenceStart: 0.0,
    tEmergenceEnd: 0.7,     // 0–0.7s : Brain emerges, centered
    tRotateStart: 0.7,    // 0.7–3.0s: ONE complete 360° Y-axis rotation (continuous)
    tRotateEnd: 3.0,
    tTransitStart: 3.0,    // 3.0–4.0s: Shrink to 62% + glide right
    tTransitEnd: 4.0,
    tBrandReveal: 3.5,    // 3.5s   : ALVI wordmark reveal (mid Scene 3)
    tHoldEnd: 5.3,    // 4.0–5.3s: Final composition hold
    tNormalExit: 5.3,    // 5.3s   : Transition to Timmy (normal mode only)

    // Visual Palette (approved from lab)
    cortexBase: new THREE.Color(0x041838),      // Deep sapphire
    cortexMid: new THREE.Color(0x0a3c7c),       // Cobalt blue
    cortexRim: new THREE.Color(0x00c8f8),       // Luminous cyan contour
    cortexGlint: new THREE.Color(0xd6f4ff),

    ventricleColor: new THREE.Color(0xffffff),  // Hot white ventricular core
    ventricleGlow: new THREE.Color(0x00e5ff),   // Luminous cyan

    deepGreyColor: new THREE.Color(0x00c4f0),   // Basal ganglia & thalamus
    deepGreyCore: new THREE.Color(0x70e6ff),

    tractColor: new THREE.Color(0x28b8f0),      // White-matter tracts
    stemColor: new THREE.Color(0x06244f),       // Cerebellum & brainstem

    // Approved constant visual state — locked 100% stable without changes
    cortexOpacityRest: 0.95,
    internalIntensityRest: 0.12,
  };

  // ── DOM References ───────────────────────────────────────────────────────
  const container = document.getElementById('scene-container');
  const brandHero = document.getElementById('brand-hero');
  const skipBtn = document.getElementById('skip-intro');
  const loaderEl = document.getElementById('load-overlay');
  const loadStatus = document.getElementById('load-status');
  const previewPanel = document.getElementById('preview-panel');
  const previewReplay = document.getElementById('preview-replay');
  const previewPause = document.getElementById('preview-pause');
  const previewTimer = document.getElementById('preview-timer');

  // ── Mode & Accessibility Flags ───────────────────────────────────────────
  const isPreviewMode = window.location.search.includes('preview=1');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  if (isPreviewMode && previewPanel) {
    previewPanel.classList.add('is-active');
  }

  // ── Three.js Scene Setup ─────────────────────────────────────────────────
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(CONFIG.bgColor, 1);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.35;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(CONFIG.bgColor);

  const camera = new THREE.PerspectiveCamera(
    36,
    window.innerWidth / window.innerHeight,
    0.1,
    60
  );
  camera.position.set(0, 0, 4.4);
  camera.lookAt(0, 0, 0);

  // ── Lighting Setup ───────────────────────────────────────────────────────
  const keyLight = new THREE.DirectionalLight(0x70b4ff, 2.8);
  keyLight.position.set(4, 5, 5);
  scene.add(keyLight);

  const rimLight = new THREE.DirectionalLight(0x00d8ff, 4.5);
  rimLight.position.set(-3, 4, -5);
  scene.add(rimLight);

  const fillLight = new THREE.DirectionalLight(0x0a2244, 1.4);
  fillLight.position.set(0, -4, 3);
  scene.add(fillLight);

  const ambientLight = new THREE.AmbientLight(0x06142c, 0.9);
  scene.add(ambientLight);

  // ── Group Hierarchy for Cinematic Articulation ───────────────────────────
  const sceneRoot = new THREE.Group();
  scene.add(sceneRoot);

  const brainMainGroup = new THREE.Group();
  sceneRoot.add(brainMainGroup);

  // Sub-groups for anatomical hemisphere opening
  const leftHemiGroup = new THREE.Group();
  const rightHemiGroup = new THREE.Group();
  const internalCoreGroup = new THREE.Group();

  brainMainGroup.add(leftHemiGroup);
  brainMainGroup.add(rightHemiGroup);
  brainMainGroup.add(internalCoreGroup);

  // ── State Variables ──────────────────────────────────────────────────────
  let nodeLookup = new Map();
  const cortexMaterials = [];
  const internalMaterials = [];
  let modelLoaded = false;
  let timelineStart = 0;
  let isPaused = false;
  let pausedElapsed = 0;
  let hasNavigated = false;
  let baseEmergenceScale = 1;
  let rightwardOffsetTarget = 1.5;

  function extras(o) {
    if (o.userData && o.userData.bx_cat != null) return o.userData;
    if (o.parent && o.parent.userData && o.parent.userData.bx_cat != null) return o.parent.userData;
    return o.userData || {};
  }

  // ── Shaders (Exact Approved Formulation from Lab) ─────────────────────────
  function createCortexMaterial() {
    const mat = new THREE.ShaderMaterial({
      vertexShader: `
        varying vec3 vNormal;
        varying vec3 vViewPosition;
        varying vec3 vWorldNormal;

    void main() {
          vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
      vViewPosition = -mvPosition.xyz;
      vNormal = normalize(normalMatrix * normal);
      vWorldNormal = normalize((modelMatrix * vec4(normal, 0.0)).xyz);
      gl_Position = projectionMatrix * mvPosition;
    }
    `,
      fragmentShader: `
        uniform vec3 uBaseColor;
        uniform vec3 uMidColor;
        uniform vec3 uRimColor;
        uniform vec3 uGlintColor;
        uniform float uOpacity;
        uniform float uTime;

        varying vec3 vNormal;
        varying vec3 vViewPosition;
        varying vec3 vWorldNormal;

        void main() {
          vec3 normal = normalize(vNormal);
          vec3 viewDir = normalize(vViewPosition);
          vec3 worldNorm = normalize(vWorldNormal);
          
          float NdotV = abs(dot(normal, viewDir));
          float fresnel = 1.0 - NdotV;
          float rim = pow(fresnel, 2.5);
          float sharpEdge = pow(fresnel, 5.5);
          
          vec3 lightDir = normalize(vec3(0.5, 0.8, 0.4));
          float diff = max(0.0, dot(worldNorm, lightDir)) * 0.5 + 0.5;
          
          vec3 baseColor = mix(uBaseColor, uMidColor, diff);
          vec3 rimGlow = uRimColor * rim * 1.6;
          vec3 glint = uGlintColor * sharpEdge * 0.8;
          
          vec3 finalRGB = baseColor + rimGlow + glint;
          
          float alpha = uOpacity * (0.35 + rim * 0.65);
          gl_FragColor = vec4(finalRGB, clamp(alpha, 0.0, 1.0));
        }
      `,
      uniforms: {
        uBaseColor: { value: CONFIG.cortexBase },
        uMidColor: { value: CONFIG.cortexMid },
        uRimColor: { value: CONFIG.cortexRim },
        uGlintColor: { value: CONFIG.cortexGlint },
        uOpacity: { value: CONFIG.cortexOpacityRest },
        uTime: { value: 0 },
      },
      transparent: true,
      side: THREE.FrontSide,
      depthWrite: false,
      depthTest: true,
      blending: THREE.NormalBlending,
    });
    cortexMaterials.push(mat);
    return mat;
  }

  function createInternalMaterial(type = 'deep_grey') {
    let baseCol = CONFIG.deepGreyColor;
    let coreCol = CONFIG.deepGreyCore;
    let baseIntensity = CONFIG.internalIntensityRest;

    if (type === 'ventricles') {
      baseCol = CONFIG.ventricleGlow;
      coreCol = CONFIG.ventricleColor;
      baseIntensity = CONFIG.internalIntensityRest * 1.4;
    } else if (type === 'tracts') {
      baseCol = CONFIG.tractColor;
      coreCol = new THREE.Color(0xd2f6ff);
      baseIntensity = CONFIG.internalIntensityRest * 0.9;
    }

    const mat = new THREE.ShaderMaterial({
      vertexShader: `
        varying vec3 vNormal;
        varying vec3 vViewPosition;
        
        void main() {
          vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
          vViewPosition = -mvPosition.xyz;
          vNormal = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        uniform vec3 uBaseColor;
        uniform vec3 uCoreColor;
        uniform float uIntensity;
        uniform float uTime;
        
        varying vec3 vNormal;
        varying vec3 vViewPosition;
        
        void main() {
          vec3 normal = normalize(vNormal);
          vec3 viewDir = normalize(vViewPosition);
          
          float NdotV = abs(dot(normal, viewDir));
          float core = pow(NdotV, 1.2);
          float rim = pow(1.0 - NdotV, 3.0);
          
          vec3 col = mix(uBaseColor, uCoreColor, core * 0.6) + uCoreColor * rim * 0.5;
          col *= uIntensity;
          
          gl_FragColor = vec4(col, 0.95);
        }
      `,
      uniforms: {
        uBaseColor: { value: baseCol },
        uCoreColor: { value: coreCol },
        uIntensity: { value: baseIntensity },
        uTime: { value: 0 },
      },
      transparent: true,
      depthWrite: true,
      depthTest: true,
      side: THREE.DoubleSide,
    });
    internalMaterials.push(mat);
    return mat;
  }

  function createStemMaterial() {
    return new THREE.MeshStandardMaterial({
      color: CONFIG.stemColor,
      roughness: 0.35,
      metalness: 0.1,
      transparent: true,
      opacity: 0.8,
      depthWrite: true,
    });
  }

  // ── Mathematical Easing Helpers ────────────────────────────────────────────
  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }
  function easeInOutCubic(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function easeInOutSine(t) { return -(Math.cos(Math.PI * t) - 1) / 2; }
  function easeOutQuart(t) { return 1 - Math.pow(1 - t, 4); }
  function clamp01(v) { return Math.max(0.0, Math.min(1.0, v)); }

  // ── Calculate Frustum Bounds for Rightward Placement ─────────────────────
  function updateFramingBounds() {
    const aspect = window.innerWidth / window.innerHeight;
    const vFovRad = (camera.fov * Math.PI) / 180;
    const dist = camera.position.z;
    const visibleHalfHeight = dist * Math.tan(vFovRad / 2);
    const visibleHalfWidth = visibleHalfHeight * aspect;

    // Radius of scaled model is approximately 0.9 in final stage
    const brainRadius = 0.85;

    // Ensure the rightmost edge stays at least 6% inside the screen boundary
    const maxAllowedRightX = visibleHalfWidth - (visibleHalfWidth * 0.06) - brainRadius;

    // On wide desktop screens, comfortably position rightward; on mobile, center or subtle offset
    if (window.innerWidth <= 768) {
      rightwardOffsetTarget = 0.0; // Center brain on mobile beneath ALVI
    } else {
      rightwardOffsetTarget = Math.max(0.7, Math.min(maxAllowedRightX, visibleHalfWidth * 0.44));
    }
  }

  // ── Model & Manifest Loading ─────────────────────────────────────────────
  async function loadAnatomicalModel() {
    try {
      if (loadStatus) loadStatus.textContent = 'Loading manifest…';
      let manifestData = null;
      if (window.ALVI_MANIFEST) {
        manifestData = window.ALVI_MANIFEST;
      } else {
        const manifestRes = await fetch(CONFIG.manifestPath);
        manifestData = await manifestRes.json();
      }

      if (manifestData && manifestData.nodes) {
        manifestData.nodes.forEach((n, idx) => {
          nodeLookup.set(n.name, n);
          nodeLookup.set(String(n.id), n);
          nodeLookup.set(String(idx), n);
        });
      }

      if (loadStatus) loadStatus.textContent = 'Initializing Draco decompression…';
      const dracoLoader = new DRACOLoader();
      dracoLoader.setDecoderPath(CONFIG.dracoDecoderPath);
      dracoLoader.setDecoderConfig({ type: 'js' });

      const gltfLoader = new GLTFLoader();
      gltfLoader.setDRACOLoader(dracoLoader);

      if (loadStatus) loadStatus.textContent = 'Decompressing 437 anatomical meshes…';
      const onModelSuccess = (gltf) => {
          const coreBox = new THREE.Box3();
          const meshesToSort = [];

          gltf.scene.traverse((o) => {
            if (!o.isMesh) return;
            const ex = extras(o);
            const cat = ex.bx_cat || 'cortex';
            const id = ex.bx_id != null ? ex.bx_id : null;
            const meta = (id != null ? nodeLookup.get(String(id)) : null) || nodeLookup.get(o.name) || {};
            o.userData.meta = meta;

            // Filter out peripheral descending structures and opaque dura meninges
            const isDescending = !ex.bx_core && (cat === 'cranial_nerves' || cat === 'arteries' || cat === 'veins_sinuses');
            const isMeninges = cat === 'meninges_dura' || o.name.toLowerCase().includes('falx') || o.name.toLowerCase().includes('tentorium');
            if (isDescending || isMeninges) {
              o.visible = false;
              return;
            }

            // Assign shader materials
            if (cat === 'cortex') {
              o.material = createCortexMaterial();
              o.renderOrder = 2;
            } else if (cat === 'ventricles') {
              o.material = createInternalMaterial('ventricles');
              o.renderOrder = 1;
            } else if (['deep_grey', 'diencephalon', 'white_matter'].includes(cat)) {
              o.material = createInternalMaterial('deep_grey');
              o.renderOrder = 1;
            } else if (cat === 'tracts') {
              o.material = createInternalMaterial('tracts');
              o.renderOrder = 1;
            } else if (['cerebellum', 'brainstem'].includes(cat)) {
              o.material = createStemMaterial();
              o.renderOrder = 1;
            } else {
              o.material = createInternalMaterial('tracts');
              o.renderOrder = 1;
            }

            meshesToSort.push({ mesh: o, cat, meta, name: o.name });

            if (ex.bx_core === 1 || ex.bx_core === true || cat === 'cortex') {
              coreBox.expandByObject(o);
            }
          });

          // Compute core center to normalize model origin
          const center = coreBox.getCenter(new THREE.Vector3());
          const sphere = coreBox.getBoundingSphere(new THREE.Sphere());
          const radius = sphere.radius || 1.0;
          baseEmergenceScale = 2.15 / radius; // ~75% viewport fill in center

          // Sort meshes into articulated left/right hemisphere groups and internal core
          let leftCount = 0;
          let rightCount = 0;
          let coreCount = 0;

          meshesToSort.forEach(({ mesh, cat, meta, name }) => {
            // Apply center translation to vertices / local coordinates
            mesh.position.sub(center);

            if (cat === 'cortex') {
              const side = (meta?.side || '').toLowerCase();
              const metaName = (meta?.name || name || '').trim().toLowerCase();

              // Check metadata side, naming conventions (.l / .r), or geometric X center
              let isLeft = side === 'left' || metaName.endsWith('.l') || metaName.includes('.l.') || metaName.endsWith('_l');
              let isRight = side === 'right' || metaName.endsWith('.r') || metaName.includes('.r.') || metaName.endsWith('_r');

              if (!isLeft && !isRight) {
                mesh.geometry.computeBoundingBox();
                const meshCenterWorldX = (mesh.geometry.boundingBox.min.x + mesh.geometry.boundingBox.max.x) / 2;
                if (meshCenterWorldX < center.x) isLeft = true;
                else isRight = true;
              }

              if (isLeft) {
                leftHemiGroup.add(mesh);
                leftCount++;
              } else if (isRight) {
                rightHemiGroup.add(mesh);
                rightCount++;
              } else {
                internalCoreGroup.add(mesh);
                coreCount++;
              }
            } else {
              internalCoreGroup.add(mesh);
              coreCount++;
            }
          });
          console.log(`[ALVI Intro] Articulated meshes: Left Hemi=${leftCount}, Right Hemi=${rightCount}, Core=${coreCount}`);

          // Orientation: Z-Anatomy anterior faces camera gracefully
          brainMainGroup.rotation.y = Math.PI - 0.25;
          brainMainGroup.scale.setScalar(0.001); // start in darkness

          updateFramingBounds();

          // Hide loader overlay
          if (loaderEl) {
            loaderEl.classList.add('is-hidden');
            setTimeout(() => { loaderEl.style.display = 'none'; }, 600);
          }

          modelLoaded = true;
          startCinematicSequence();
        };

      const onModelProgress = (progress) => {
        if (progress.total > 0 && loadStatus) {
          const pct = Math.round((progress.loaded / progress.total) * 100);
          loadStatus.textContent = `Preparing visualization… ${pct}%`;
        }
      };

      const onModelError = (err) => {
        console.error('[ALVI Intro] GLTF load error:', err);
        if (loadStatus) loadStatus.textContent = 'Error loading anatomical model.';
        if (loaderEl) loaderEl.classList.add('is-error');
      };

      if (window.ALVI_BRAIN_MODEL_BASE64) {
        try {
          const binStr = atob(window.ALVI_BRAIN_MODEL_BASE64);
          const len = binStr.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {
            bytes[i] = binStr.charCodeAt(i);
          }
          gltfLoader.parse(bytes.buffer, '', onModelSuccess, onModelError);
        } catch (b64Err) {
          console.warn('[ALVI Intro] Base64 decoding failed, falling back to fetch load:', b64Err);
          gltfLoader.load(CONFIG.modelPath, onModelSuccess, onModelProgress, onModelError);
        }
      } else {
        gltfLoader.load(CONFIG.modelPath, onModelSuccess, onModelProgress, onModelError);
      }
    } catch (e) {
      console.error('Anatomical setup error:', e);
      if (loaderEl) loaderEl.classList.add('is-error');
    }
  }

  // ── Start Cinematic Sequence ─────────────────────────────────────────────
  function startCinematicSequence() {
    if (reduceMotion.matches) {
      jumpToFinalComposition();
      return;
    }

    timelineStart = performance.now();
    isPaused = false;
    pausedElapsed = 0;

    if (skipBtn) {
      setTimeout(() => { skipBtn.classList.add('is-visible'); }, 500);
    }
  }

  // ── Jump to Final Composition (Reduced Motion / Fast) ────────────────────
  function jumpToFinalComposition() {
    const startAngle = Math.PI - 0.20;
    const finalAngle = startAngle + Math.PI * 2 + 0.65;

    brainMainGroup.scale.setScalar(baseEmergenceScale * 0.62);
    brainMainGroup.position.set(rightwardOffsetTarget, -0.05, 0);
    brainMainGroup.rotation.set(0.08, finalAngle, 0);

    leftHemiGroup.position.set(0, 0, 0);
    rightHemiGroup.position.set(0, 0, 0);

    updateUniforms(CONFIG.cortexOpacityRest, CONFIG.internalIntensityRest);

    if (brandHero) brandHero.classList.add('is-revealed');
    if (skipBtn) skipBtn.classList.add('is-visible');
  }

  // ── Uniform Update Helper ────────────────────────────────────────────────
  function updateUniforms(cortexOpacity, internalIntensity) {
    cortexMaterials.forEach(m => {
      if (m.uniforms?.uOpacity) m.uniforms.uOpacity.value = cortexOpacity;
    });
    internalMaterials.forEach(m => {
      if (m.uniforms?.uIntensity) m.uniforms.uIntensity.value = internalIntensity;
    });
  }

  // ── Timeline Orchestration Tick ──────────────────────────────────────────
  function updateTimeline(now) {
    if (!modelLoaded || isPaused) return;

    const t = (now - timelineStart) / 1000;

    if (previewTimer) {
      previewTimer.textContent = `${t.toFixed(1)}s`;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // SCENE 1 (0.0s – 0.7s): Complete Intact Brain Emergence in Center
    // Stable approved appearance — no shader changes whatsoever
    // ─────────────────────────────────────────────────────────────────────────
    if (t < CONFIG.tEmergenceEnd) {
      const prog = clamp01(t / CONFIG.tEmergenceEnd);
      const ease = easeOutQuart(prog);

      brainMainGroup.scale.setScalar(baseEmergenceScale * Math.max(0.001, ease));
      brainMainGroup.position.set(0, 0, 0);
      // Start from anterior-facing orientation
      brainMainGroup.rotation.set(0.05, Math.PI - 0.20, 0);

      leftHemiGroup.position.set(0, 0, 0);
      rightHemiGroup.position.set(0, 0, 0);

      updateUniforms(CONFIG.cortexOpacityRest, CONFIG.internalIntensityRest);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // SCENE 2 (0.7s – 3.0s): ONE FULL 360° Rotation Around Vertical Axis
    //
    // Key design constraint: We CANNOT use lerp(A, B) for a full turn because
    // any angle difference > π causes slerp/lerp to take the short path.
    // Instead we accumulate angle directly: start angle + (progress × 2π).
    // The brain makes exactly one complete forward revolution.
    // ─────────────────────────────────────────────────────────────────────────
    else if (t < CONFIG.tRotateEnd) {
      brainMainGroup.scale.setScalar(baseEmergenceScale);
      brainMainGroup.position.set(0, 0, 0);

      const rotDuration = CONFIG.tRotateEnd - CONFIG.tRotateStart;
      const subT = clamp01((t - CONFIG.tRotateStart) / rotDuration);
      // Cinematic ease: slow start, holds speed mid-turn, slow finish
      const easedRot = easeInOutSine(subT);

      // Start angle = Math.PI - 0.20 (anterior-facing).
      // Travel exactly 2π (one full revolution) forward.
      const startAngle = Math.PI - 0.20;
      const currentRotY = startAngle + easedRot * Math.PI * 2;
      const currentRotX = 0.05 + easedRot * 0.03; // subtle tilt during spin

      brainMainGroup.rotation.set(currentRotX, currentRotY, 0);

      leftHemiGroup.position.set(0, 0, 0);
      rightHemiGroup.position.set(0, 0, 0);

      updateUniforms(CONFIG.cortexOpacityRest, CONFIG.internalIntensityRest);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // SCENE 3 (3.0s – 4.0s): Shrink & Glide Rightward (Zero Clipping)
    // Brain smoothly reduces to 62% and glides to right; ALVI wordmark at 3.5s
    // ─────────────────────────────────────────────────────────────────────────
    else if (t < CONFIG.tTransitEnd) {
      leftHemiGroup.position.set(0, 0, 0);
      rightHemiGroup.position.set(0, 0, 0);

      const transitDuration = CONFIG.tTransitEnd - CONFIG.tTransitStart;
      const subT = clamp01((t - CONFIG.tTransitStart) / transitDuration);
      const easedTransit = easeInOutCubic(subT);

      // Scale down to 62%
      const currentScale = THREE.MathUtils.lerp(baseEmergenceScale, baseEmergenceScale * 0.62, easedTransit);
      brainMainGroup.scale.setScalar(currentScale);

      // Glide rightward to calculated safe boundary with padding
      const currentX = THREE.MathUtils.lerp(0, rightwardOffsetTarget, easedTransit);
      const currentY = THREE.MathUtils.lerp(0, -0.05, easedTransit);
      brainMainGroup.position.set(currentX, currentY, 0);

      // After completing full 360°, the angle is startAngle + 2π = same anterior view.
      // Now rotate to a pleasing 3/4 final angle during transit.
      const startAngle = Math.PI - 0.20;
      const finalAngle = startAngle + Math.PI * 2 + 0.65; // ≈3/4 turn past front
      const rotY = THREE.MathUtils.lerp(startAngle + Math.PI * 2, finalAngle, easedTransit);
      brainMainGroup.rotation.set(0.08, rotY, 0);

      // Trigger ALVI wordmark reveal
      if (t >= CONFIG.tBrandReveal && brandHero && !brandHero.classList.contains('is-revealed')) {
        brandHero.classList.add('is-revealed');
      }

      updateUniforms(CONFIG.cortexOpacityRest, CONFIG.internalIntensityRest);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // SCENE 4 (4.0s – 5.3s): Finished Composition Hold & Transition to Timmy
    // ─────────────────────────────────────────────────────────────────────────
    else {
      leftHemiGroup.position.set(0, 0, 0);
      rightHemiGroup.position.set(0, 0, 0);

      // Settle into final composition
      brainMainGroup.scale.setScalar(baseEmergenceScale * 0.62);
      brainMainGroup.position.set(rightwardOffsetTarget, -0.05, 0);

      // Gentle ambient breathing drift
      const restT = t - CONFIG.tTransitEnd;
      const startAngle = Math.PI - 0.20;
      const finalAngle = startAngle + Math.PI * 2 + 0.65;
      brainMainGroup.rotation.set(0.08, finalAngle + restT * 0.025, 0);

      updateUniforms(CONFIG.cortexOpacityRest, CONFIG.internalIntensityRest);

      // Ensure ALVI wordmark is revealed
      if (brandHero && !brandHero.classList.contains('is-revealed')) {
        brandHero.classList.add('is-revealed');
      }

      // Normal mode: auto-transition to Timmy at tNormalExit
      if (!isPreviewMode && t >= CONFIG.tNormalExit && !hasNavigated) {
        hasNavigated = true;
        transitionToTimmy();
      }
    }
  }

  // ── Navigation Transition (Normal Mode: to Timmy) ────────────────────────
  function transitionToTimmy() {
    if (typeof window.ALVI_INTRO_ON_COMPLETE === 'function') {
      window.ALVI_INTRO_ON_COMPLETE();
      return;
    }
    const overlay = document.createElement('div');
    overlay.className = 'transition-overlay';
    document.body.appendChild(overlay);

    overlay.offsetHeight; // force reflow
    overlay.classList.add('is-active');

    setTimeout(() => {
      window.location.href = 'timmy.html';
    }, 1100);
  }

  function skipImmediately() {
    hasNavigated = true;
    if (typeof window.ALVI_INTRO_ON_SKIP === 'function') {
      window.ALVI_INTRO_ON_SKIP();
      return;
    }
    window.location.href = 'timmy.html';
  }

  if (skipBtn) {
    skipBtn.addEventListener('click', skipImmediately);
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' || (e.key === ' ' && !e.target.closest('button, input'))) {
      if (!isPreviewMode) {
        e.preventDefault();
        skipImmediately();
      }
    }
  });

  // ── Preview Mode Controls ────────────────────────────────────────────────
  if (previewReplay) {
    previewReplay.addEventListener('click', () => {
      // Complete reset of state
      timelineStart = performance.now();
      isPaused = false;
      pausedElapsed = 0;
      hasNavigated = false;

      if (brandHero) brandHero.classList.remove('is-revealed');
      if (previewPause) previewPause.textContent = '⏸ Pause';

      brainMainGroup.scale.setScalar(0.001);
      brainMainGroup.position.set(0, 0, 0);
      brainMainGroup.rotation.set(0.05, Math.PI - 0.20, 0);

      leftHemiGroup.position.set(0, 0, 0);
      rightHemiGroup.position.set(0, 0, 0);

      updateUniforms(CONFIG.cortexOpacityRest, CONFIG.internalIntensityRest);
    });
  }
  if (previewPause) {
    previewPause.addEventListener('click', () => {
      if (!isPaused) {
        isPaused = true;
        pausedElapsed = performance.now() - timelineStart;
        previewPause.textContent = '▶ Resume';
      } else {
        isPaused = false;
        timelineStart = performance.now() - pausedElapsed;
        previewPause.textContent = '⏸ Pause';
      }
    });
  }

  // ── Animation Loop ───────────────────────────────────────────────────────
  const clock = new THREE.Clock();

  function animate() {
    requestAnimationFrame(animate);

    const now = performance.now();
    const elapsed = clock.getElapsedTime();

    // Pulse time uniforms for shaders
    cortexMaterials.forEach(m => { if (m.uniforms?.uTime) m.uniforms.uTime.value = elapsed; });
    internalMaterials.forEach(m => { if (m.uniforms?.uTime) m.uniforms.uTime.value = elapsed; });

    updateTimeline(now);

    renderer.render(scene, camera);
  }

  animate();

  // ── Responsive Resize ────────────────────────────────────────────────────
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    updateFramingBounds();
  });

  // Initialize model load
  loadAnatomicalModel();


};