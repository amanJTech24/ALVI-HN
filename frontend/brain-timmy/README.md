# ALVI — Brain Intro & Timmy (GitHub & Direct File Ready)

Self-contained frontend package containing the approved **ALVI 3D Anatomical Brain Cinematic Intro** and **Timmy Wellness Companion**.

---

## 🌟 Dual Opening Modes Supported

### 1. Direct Double-Click in Windows File Explorer (`file:///`)
- Simply double-click `index.html` or `intro.html` directly from File Explorer.
- **No localhost or command-line server is required!**
- The 3D brain model and anatomical manifest are embedded into high-speed local data scripts (`js/brain_model_data.js` and `js/manifest_data.js`), bypassing standard browser `file:///` CORS blocking.

### 2. GitHub Pages / HTTPS Hosting (`https://`)
- Upload the contents of this folder directly to your GitHub repository.
- Under **Settings -> Pages**, set source to `main` branch `/ (root)`.
- Visitors can view `https://<your-username>.github.io/<repo>/` directly in any modern browser on desktop or mobile.

---

## 🧠 Sequence Overview

1. **Scene 1 (0.0s – 0.7s):** Emergence of the approved 437-structure layered anatomical brain in the center of the viewport.
2. **Scene 2 (0.7s – 3.0s):** Full 360° continuous anatomical rotation with sapphire cortex, luminous cyan contours, and hot-white ventricular glow.
3. **Scene 3 (3.0s – 4.0s):** Brain scales down to 62% and glides rightward to an anatomically safe anchor position.
4. **Scene 4 (3.5s – 4.3s):** Large typographic **ALVI** wordmark with mask reveal and tagline on the left.
5. **Scene 5 (4.0s – 5.3s):** Ambient floating hold.
6. **Scene 6 (5.3s):** Seamless cinematic transition directly to **Timmy** (`timmy.html`).

---

## 📂 File Structure

```
ALVI_BRAIN_TIMMY_GITHUB_READY/
├── index.html                  # Entry point for GitHub Pages & direct double-clicking
├── intro.html                  # Dedicated intro page (identical entry point)
├── timmy.html                  # Interactive Timmy Companion with cursor-tracking eyes
├── README.md                   # Setup and usage guide
├── css/
│   ├── intro.css               # Cinematic intro styles, typography & animations
│   ├── timmy.css               # Timmy SVG styling & layout
│   └── timmy-alvi-theme.css    # Light ice-blue & navy brand palette for Timmy
├── js/
│   ├── intro.js                # Three.js 3D brain choreography controller
│   ├── timmy.js                # Timmy eye-tracking, blink & mood selection logic
│   ├── manifest_data.js        # Embedded 437-mesh anatomical manifest
│   └── brain_model_data.js     # Embedded Draco GLB geometry in Base64
└── assets/
    └── models/
        ├── anatomical_brain.glb # Approved 437-mesh GLB model
        └── manifest.json        # Anatomical node metadata
```

---

## ⚡ Technical Highlights

- **Zero-CORS Architecture:** Employs Base64 in-memory ArrayBuffer parsing (`GLTFLoader.parse`) and script-tag manifest loading to allow seamless offline or direct-file inspection.
- **Draco Acceleration:** Decodes 437 intricate anatomical meshes in <1 second via Google's WebAssembly Draco decoder.
- **Three.js r170:** Standard ESM CDN importmap for modern browser performance and lightweight deployment.
