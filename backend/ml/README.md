# ALVI Machine Learning Subsystem — Voice Screening

This module implements the end-to-end audio processing, acoustic feature extraction, and exploratory machine learning pipeline for **ALVI (Alzheimer's Voice Intelligence)**, supporting the *"Voice Check-in: Describe the Scene"* cognitive assessment feature.

---

## 1. System Overview & Architecture

The ALVI ML pipeline extracts mathematically grounded, reproducible acoustic and prosodic features from speech recordings, cleans the data to prevent label contradiction and speaker leakage, and trains participant-independent baseline classifiers.

```text
Raw Audio Recording (WAV)
        │
        ▼
audio_preprocessing.py
  ├── Format decoding (SoundFile / Librosa / FFmpeg)
  ├── Multichannel downmixing to mono
  ├── Resampling to 16,000 Hz
  └── Quality checks (empty, corrupt, silent, clipped)
        │
        ▼
extract_features.py
  ├── MFCC 1–13 + First-Order Deltas (52 features)
  ├── Zero-Crossing Rate (ZCR) statistics (2 features)
  ├── Voiced Fundamental Frequency (F0) via YIN (5 features)
  ├── RMS Energy envelope descriptors (4 features)
  ├── Spectral descriptors: Centroid, Bandwidth, Rolloff, Flatness (8 features)
  ├── Temporal & Activity acoustic proxies (5 features)
  └── Advanced proxies: HNR Proxy & Spectral Contrast (3 features)
        │
        ▼
clean_dataset.py & audit_labels.py
  ├── Prunes 76 cross-group duplicate hash pairs (152 conflicting rows)
  └── Prunes 32 unresolved multi-class contradictory speakers (72 rows)
        │
        ▼
data/processed/voice_features_clean.csv (100 recordings, 80 unambiguous speakers)
        │
        ▼
train_voice.py & evaluate_voice.py
  ├── GroupShuffleSplit by speaker_id (75 train / 25 test; 0 speaker leakage)
  ├── StratifiedGroupKFold 5-fold cross-validation on training fold
  ├── Leak-free Pipelines (Median Imputer + StandardScaler + Estimator)
  ├── Evaluates: Logistic Regression, Random Forest, Support Vector Machine (SVM)
  └── Generates evaluation curves, confusion matrices, and saved model artifact
```

---

## 2. Dataset Provenance, Label Conflicts & Cleaning Strategy

### The DementiaNet Corpus & Observed Anomalies
The raw dataset consists of 324 recordings gathered from public interviews of 121 public figures and celebrities:
* **Initial Size:** 324 recordings (162 `dementia`, 162 `nodementia`).
* **Exact Audio Duplicates:** **76 identical SHA-256 hash pairs (152 rows)** existed simultaneously in `dementia/` and `nodementia/` (e.g. identical audio of Al Pacino present in both classes).
* **Contradictory Speakers:** **83 speakers** were associated with both classes, with **32 speakers** possessing distinct (non-duplicate) recordings assigned to conflicting ground truth targets.

### Phase 3 Cleaning Protocol
To establish a statistically defensible and leak-free dataset, two cleaning stages were executed:
1. **Stage 1 (Exact Hash Deduplication):** Both sides of every conflicting duplicate hash pair were removed (152 files removed).
2. **Stage 2 (Contradictory Speaker Pruning):** Speakers with unresolved multi-class assignments were excluded from supervised training (72 files from 32 ambiguous speakers removed).

### Cleaned Dataset Metrics (`data/processed/voice_features_clean.csv`)
* **Total Clean Recordings:** **100**
* **Class Distribution:** 53 `dementia`, 47 `nodementia`
* **Independent Speakers:** **80 unique speakers**
  * Dementia Speakers: 39 (53 recordings)
  * NoDementia Speakers: 41 (47 recordings)
* **Cross-Class Speaker Overlap:** **0 (ZERO LEAKAGE)**
* **Missing / NaN / Inf values:** **0**

---

## 3. Extracted Acoustic Features (79 Dimensions)

The model takes as input 79 acoustic features computed from 16 kHz audio:

| Category | Count | Features | Description |
|---|---|---|---|
| **MFCCs** | 26 | `mfcc_1_mean` .. `mfcc_13_mean`, `mfcc_1_std` .. `mfcc_13_std` | Mel-Frequency Cepstral Coefficients capturing vocal tract spectral shape. |
| **MFCC Deltas** | 26 | `mfcc_delta_1_mean` .. `mfcc_delta_13_mean`, `mfcc_delta_1_std` .. `mfcc_delta_13_std` | First-order temporal derivatives capturing transitional speech dynamics. |
| **ZCR** | 2 | `zcr_mean`, `zcr_std` | Zero-Crossing Rate reflecting signal noisiness and unvoiced/fricative density. |
| **Pitch (F0)** | 5 | `f0_mean`, `f0_std`, `f0_min`, `f0_max`, `f0_voiced_ratio` | Fundamental frequency estimated via YIN algorithm ($F_0 \in [65, 400]$ Hz) gated by speech energy. |
| **RMS Energy** | 4 | `rms_mean`, `rms_std`, `rms_min`, `rms_max` | Frame-level Root Mean Square energy envelope. |
| **Spectral** | 8 | `spectral_centroid_(mean/std)`, `spectral_bandwidth_(mean/std)`, `spectral_rolloff_(mean/std)`, `spectral_flatness_(mean/std)` | Spectral center of mass, spread, 85% energy rolloff frequency, and tonality vs noisiness flatness. |
| **Temporal & Activity** | 5 | `duration_seconds`, `active_duration_seconds`, `low_energy_frame_ratio`, `low_energy_interval_count`, `low_energy_interval_mean_duration` | Acoustic proxies for speech presence and low-energy hesitation dynamics. |
| **Advanced Proxies** | 3 | `hnr_proxy_db`, `spectral_contrast_mean`, `spectral_contrast_std` | Harmonic-to-Noise energy ratio proxy (HPSS) and peak-to-valley spectral contrast. |

> **Acoustic Proxy Disclaimer:** Low-energy measurements represent acoustic energy proxies, not clinical speech-pause ground truth. Jitter, shimmer, speaking rate, and linguistic features are not fabricated.

---

## 4. Participant-Independent Validation Methodology

To ensure realistic generalization and prevent identity memorization:
* **Train / Test Partition:** Reserved 20% of independent speakers (16 speakers, 25 recordings) as a strictly held-out test set using `GroupShuffleSplit`.
* **Cross-Validation:** 5-fold `StratifiedGroupKFold` cross-validation on the training fold (64 speakers, 75 recordings) during hyperparameter optimization.
* **Zero Leakage:** Imputation (`SimpleImputer(strategy='median')`) and standardization (`StandardScaler()`) were fit strictly within training folds inside Scikit-learn Pipelines.

---

## 5. Real Evaluation Results (Held-Out Test Set)

| Model | 5-Fold CV Bal. Acc. | Test Bal. Acc. | Precision | Recall (Sensitivity) | Specificity | F1-Score | ROC-AUC |
|---|---|---|---|---|---|---|---|
| **Logistic Regression** | 0.5393 | 0.4816 | 0.6667 | 0.5882 | 0.3750 | 0.6250 | 0.4485 |
| **Random Forest (Selected)** | **0.6179** | **0.6324** | **0.7647** | **0.7647** | **0.5000** | **0.7647** | **0.5662** |
| **Support Vector Machine (SVM)** | 0.6179 | 0.5735 | 0.7333 | 0.6471 | 0.5000 | 0.6875 | 0.5221 |

### Best Model Selection & Findings
* **Selected Model:** **Random Forest Classifier** (`backend/ml/models/voice_model.joblib`).
* **Test Performance:** Achieved **0.6324 Balanced Accuracy** and **0.7647 F1-score** on unseen speakers (Confusion Matrix: TN=4, FP=4, FN=4, TP=13).
* **Scientific Finding:** On genuinely independent speakers, acoustic features alone achieve modest predictive power (~0.57–0.63 balanced accuracy) above the 0.50 random-chance baseline.

---

## 6. Execution Commands

All commands are executed using the local project virtual environment (`.venv`):

```powershell
# 1. Audit labels and duplicate hashes
.\.venv\Scripts\python.exe -m backend.ml.audit_labels

# 2. Execute safe data cleaning
.\.venv\Scripts\python.exe -m backend.ml.clean_dataset

# 3. Train models and generate evaluation metrics & figures
.\.venv\Scripts\python.exe -m backend.ml.train_voice

# 4. Run pipeline integrity and leakage unit tests
.\.venv\Scripts\python.exe -m unittest backend.ml.test_ml_pipeline

# 5. Run API integration tests (FastAPI, WebM decoding, file validation)
.\.venv\Scripts\python.exe -m unittest backend.ml.test_api_integration

# 6. Start the local backend server (Port 8765)
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload
```

---

## 7. Limitations of DementiaNet for ALVI's Scene-Description Feature

1. **Acoustic Task Mismatch:**
   DementiaNet audio consists of conversational interview snippets gathered from television, radio, and public appearances. In contrast, ALVI's check-in feature asks the user to describe a specific visual scene (*"Describe the Scene: Park Picture"*). Conversational interview dynamics differ fundamentally from picture description tasks (e.g. Boston Cookie Theft / Park Scene).
2. **Lack of Clinical Verification:**
   DementiaNet annotations are exploratory research labels scraped from media sources without clinical, neuropsychological, or biomarker validation.
3. **Non-Diagnostic Research Boundary:**
   This model represents an exploratory research benchmark. **It does not provide medical diagnoses, cognitive decline determinations, or clinical risk predictions.**

---

## 8. Phase 4: FastAPI Prediction Service & Integration

### Inference Architecture (`backend/ml/predict_voice.py`)
* **Service Class:** `VoicePredictionService` (singleton pattern via `get_voice_prediction_service()`).
* **Model Loading:** Safely unpickles `backend/ml/models/voice_model.joblib` and validates schema against `backend/ml/models/model_metadata.json`.
* **79-Feature Validation:** Strictly asserts feature dimension, feature ordering, and prevents missing or NaN feature vectors prior to pipeline imputation and standardization.
* **FFmpeg Audio Preprocessing:** Supports standard PCM WAV and browser microphone WebM/Opus audio through an in-memory FFmpeg pipe fallback (`load_raw_audio`), normalizing all audio to 16 kHz mono float32.

### API Endpoint Specification (`backend/main.py`)

#### `POST /api/voice/analyze`
Accepts multipart audio upload from web clients, extracts acoustic features, and returns research predictions.

* **Supported Formats:** `audio/wav`, `audio/x-wav`, `audio/webm`, `audio/ogg`, `audio/mpeg`, `audio/mp3`, `audio/mp4`, `audio/m4a`.
* **Max Payload Size:** 25 MB (`413 Content Too Large` if exceeded).
* **Temporary File Safety:** Uploaded files are written to system temp directory and guaranteed unlinked via `try...finally`.

#### Sample JSON Response
```json
{
  "status": "success",
  "audio_summary": {
    "duration_seconds": 28.0,
    "sample_rate_hz": 16000,
    "peak_amplitude": 0.8187,
    "is_clipped": false,
    "voiced_f0_mean_hz": 106.3,
    "voiced_ratio": 0.797,
    "rms_energy_mean": 0.121,
    "spectral_centroid_hz": 1799.1,
    "low_energy_interval_count": 11
  },
  "acoustic_features_extracted_count": 79,
  "acoustic_features": {
    "mfcc_1_mean": -323.38,
    "...": "...",
    "spectral_contrast_std": 11.38
  },
  "research_prediction": {
    "predicted_class_id": 0,
    "predicted_label": "nodementia",
    "raw_model_score": 0.3947,
    "model_version": "1.0.0-experimental",
    "is_calibrated_probability": false,
    "score_interpretation": "Raw ensemble tree vote fraction for research annotation 'dementia'. This is an uncalibrated heuristic score, NOT a clinical diagnostic probability.",
    "disclaimer": "ALVI is an exploratory cognitive pattern screening prototype. This output is NOT a medical diagnosis, does NOT assess clinical Alzheimer's risk, and has NOT been clinically validated."
  },
  "filename": "audio_sample.wav",
  "content_type": "audio/wav",
  "size_bytes": 4939278
}
```

### Route Backward Compatibility
All existing legacy endpoints remain 100% operational:
* `GET /` — Root service metadata and endpoint catalog.
* `GET /health` — Simple health check (`{"status": "healthy"}`).
* `POST /analyze` — Legacy cognitive score mock endpoint maintained for unmigrated frontend callers.

---

## 8. Phase 6 — Story Recall NLP & Memory Performance Engine

Phase 6 implements an explainable, lightweight Natural Language Processing (NLP) scoring engine for narrative retell cognitive tasks (*"Step 2: Story Recall"*).

### 8.1 Architectural Design & Lightweight Strategy
Rather than deploying heavy, multi-gigabyte Large Language Models (LLMs) or GPU-dependent dependencies that exceed free cloud hosting limits, ALVI utilizes an explainable hybrid NLP framework:
* **Lexical & Morphological Normalization:** Token-level digit normalization, punctuation stripping, and lowercasing.
* **Word Boundary & Synonym Resolution:** Regex-bounded matching against accepted paraphrase lists (`backend/data/story_bank.json`), preventing false substring matches (e.g. `'he'` inside `'the'`).
* **Negation Scope Detection:** Dynamic windowing algorithm detecting preceding negations (`not`, `never`, `didn't`, `without`, `no`, `wasn't`) to disqualify negated statements.
* **Sublinear Char/Word TF-IDF Cosine Similarity:** Robust Scikit-learn TF-IDF n-gram vectorizer ($n \in [3, 5]$) measuring whole-narrative semantic overlap without external downloads.
* **Temporal Milestone Inversion Scoring:** Pairwise chronological ordering based on narrative scene tiers, penalizing temporal fragmentation while allowing natural intra-clause variation.

### 8.2 Authoritative Story Bank (`backend/data/story_bank.json`)
Contains standardized narrative stimuli with structured information units, accepted synonyms, sequence tiers, and known intrusions:
* `aarav_story_v1` (Aarav's Rainy Day — 38 words, 8 Key Information Units):
  1. `iu_aarav`: Aarav (Protagonist) [Tier 0]
  2. `iu_rain`: Rainy morning [Tier 0]
  3. `iu_umbrella`: Carrying a blue umbrella [Tier 1]
  4. `iu_market`: Walked to local market [Tier 2]
  5. `iu_apples`: Bought three red apples [Tier 3]
  6. `iu_meera`: Met his friend Meera [Tier 4]
  7. `iu_gave_apple`: Gave her one apple [Tier 5]
  8. `iu_home`: Returned home [Tier 6]
* `ravi_market_v1` (Ravi's Bicycle Errand — 35 words, 7 Key Information Units)

### 8.3 Scoring Metrics & Composite Formula
The composite task performance score is calculated deterministically:
$$\text{Composite Score} = \max\Big(0, \min\big(100, (0.60 \times C) + (0.25 \times S) + (0.15 \times Q) - P_{\text{intrusion}}\big)\Big)$$
Where:
* $C \in [0, 100]$: **Fact Completeness** ($1.0$ point for exact/paraphrase, $0.5$ for partial, $0.0$ for omitted/negated).
* $S \in [0, 100]$: **Semantic Similarity** (Global TF-IDF cosine similarity between retell and stimulus).
* $Q \in [0, 100]$: **Chronological Sequence Accuracy** ($1.0 - \frac{\text{Inversions}}{\text{Evaluable Pairs}}$).
* $P_{\text{intrusion}}$: **Intrusion Penalty** ($-5.0$ points per detected unsupported concept from `known_intrusions`).

#### Performance Tiers:
* **85 – 100:** High Recall (Intact retention; core milestones recalled in proper order)
* **65 – 84:** Moderate Recall (Central theme retained; minor omissions or mild sequencing drift)
* **40 – 64:** Mild Recall Difficulty (Partial retention; multiple key milestones omitted)
* **0 – 39:** Low Recall / Incomplete (Fragmented or minimal recall)

### 8.4 FastAPI Endpoints
* `GET /api/story/stories` — Returns list of active assessment narratives with word counts and unit counts.
* `GET /api/story/{story_id}` — Returns stimulus narrative text and metadata without grading keys.
* `POST /api/story/evaluate` — Evaluates a retell transcript payload (`story_id`, `transcript`, `input_mode`, `timing_seconds`).

### 8.5 Automated Test Suite (`backend/tests/test_story_recall.py`)
Run all 15 automated validation and regression tests:
```bash
.\.venv\Scripts\python.exe -m unittest backend.tests.test_story_recall -v
```
All 15 tests verify:
* Story catalog and details retrieval
* Perfect recall (100% completeness and sequence accuracy)
* Synonym & paraphrase tolerance
* Partial recall scoring
* Negation & contradiction filtering
* Temporal inversion penalties on scrambled retells
* Unrelated intrusions detection (e.g. car, hospital, doctor)
* Input validation (empty transcript, invalid story ID)
* Zero regression on Phase 5 Voice Check-in (`/health`, `/`, `/analyze`, `/api/voice/analyze`)

---

## 9. Phase 7 — MindPlay Cognitive Games Analytics

Phase 7 implements real, high-resolution behavioral telemetry and deterministic cognitive performance analytics for **Step 3: MindPlay Challenges** (`mindplay.html`, `js/mindplay.js`).

### 9.1 Challenge Architecture & Cognitive Domains
MindPlay evaluates three complementary cognitive micro-tasks contextualized around Aarav's story:

1. **Challenge 1: Remember (`ch1_remember` — Weight: 35%)**
   * **Cognitive Domain:** Dual Visual-Verbal Memory Binding / Free Delayed Recognition.
   * **Task:** Identify target objects that occurred in the narrative from a multi-select grid.
   * **Target Set (2):** `["umbrella", "apples"]`.
   * **Distractor Set (2):** `["bicycle", "books"]`.
   * **Scoring Formula:**
     $$\text{Points} = \max\Big(0.0,\, \min\big(2.0,\, N_{\text{targets}} - (0.5 \times N_{\text{distractors}})\big)\Big)$$
     $$\text{Accuracy}_{\text{ch1}} = \left(\frac{\text{Points}}{2.0}\right) \times 100\%$$

2. **Challenge 2: Sequence (`ch2_sequence` — Weight: 35%)**
   * **Cognitive Domain:** Working Memory, Temporal Chronology & Executive Sequencing.
   * **Task:** Re-order 5 narrative milestones into chronological sequence using swap controls.
   * **Initial Scrambled State:** `[1, 3, 2, 5, 4]` (left home, bought apples, went to market, returned home, met Meera).
   * **Target State:** `[1, 2, 3, 4, 5]`.
   * **Scoring Formula (Kendall Tau Inversion Distance):**
     $$\text{Accuracy}_{\text{ch2}} = \max\left(0.0,\, \left(1.0 - \frac{\text{Inversions}}{10}\right) \times 100\%\right)$$
     Where $\text{Total Pairs} = \frac{5 \times 4}{2} = 10$. Perfect order has 0 inversions ($100\%$).

3. **Challenge 3: Find (`ch3_find` — Weight: 30%)**
   * **Cognitive Domain:** Visual Feature Matching, Processing Speed & Sustained Reaction Time.
   * **Task:** Rapid target discrimination of the rain protection item under live timing.
   * **Target:** `umbrella`. Distractors: `apples`, `raincoat` (plausible semantic lure).
   * **High-Resolution Latency Tracking:** Measured via browser `performance.now()`.
   * **Scoring Formula:**
     $$\text{Accuracy}_{\text{target}} = 100\% \text{ if correct, else } 0\%$$
     $$\text{Latency Score} = \begin{cases} 
     100.0 & \text{if } RT \le 2200\text{ ms} \\
     100.0 - \left(\frac{RT - 2200}{2600}\right) \times 40.0 & \text{if } 2200\text{ ms} < RT \le 4800\text{ ms} \\
     \max\left(20.0,\, 60.0 - \left(\frac{RT - 4800}{7200}\right) \times 40.0\right) & \text{if } 4800\text{ ms} < RT \le 12000\text{ ms} \\
     10.0 & \text{if } RT > 12000\text{ ms}
     \end{cases}$$
     If target is correct: $\text{Score}_{\text{ch3}} = (0.70 \times \text{Accuracy}) + (0.30 \times \text{Latency Score})$. If incorrect: $0.0\%$.

### 9.2 Composite Performance Score
$$\text{Composite Score} = (0.35 \times \text{Score}_{\text{ch1}}) + (0.35 \times \text{Score}_{\text{ch2}}) + (0.30 \times \text{Score}_{\text{ch3}})$$

* **85 – 100:** `High Performance` (Accurate memory binding, intact temporal sequencing, prompt latency)
* **65 – 84:** `Moderate Performance` (Solid overall execution; minor transposition or mild search hesitation)
* **40 – 64:** `Mild Performance Variance` (Partial recall, sequencing fragmentation, or extended search latency)
* **0 – 39:** `Low / Incomplete Performance` (Multiple errors, reversed sequence, or unselected cards)

### 9.3 Longitudinal Personal Baseline & Trajectory (`POST /api/games/analyze-history`)
When a participant completes $\ge 2$ sessions, the analytics engine calculates:
* **Personal Baseline:** Mean score $\mu$, best score, and recent score.
* **Coefficient of Variation ($CV = \frac{\sigma}{\mu} \times 100\%$):**
  * $CV < 8\%$: *Highly Consistent*
  * $8\% \le CV < 20\%$: *Moderate Consistency*
  * $CV \ge 20\%$: *High Variability*
* **Trajectory Delta:** $\Delta_{\text{score}} = \text{Recent} - \text{Initial}$, identifying learning/practice effects vs. score drift.
* **Safe Threshold:** If $< 2$ sessions exist, returns `"insufficient_history": true` without fabricating trend curves.

### 9.4 FastAPI Endpoints
* `GET /api/games/catalog` — Returns challenge configuration, target sets, and normative thresholds.
* `POST /api/games/submit` — Evaluates telemetry payload and calculates composite performance metrics.
* `POST /api/games/analyze-history` — Calculates multi-session personal baseline, variance, and trajectory.

### 9.5 Automated Test Suite Execution
Run automated tests covering MindPlay, Story Recall, and Voice Check-in:
```bash
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py" -v
```

---

## 10. Phase 8: Complete Case Comparison & Cognitive Performance Analytics

Phase 8 implements the multi-modal case comparison and longitudinal cognitive analytics engine, bringing together Voice Check-in, Story Recall, and MindPlay assessments into a unified comparative framework.

### 10.1 Three Distinct Comparison Modes

1. **Mode A: Current Session Performance Synthesis**
   * Synthesizes all completed activities:
     * **Voice Check-in:** Acoustic feature extraction (79 dimensions), voiced F0 mean, RMS energy, ZCR, low-energy pause ratio/count, spectral centroid, and exploratory Random Forest vote score.
     * **Story Recall:** Narrative completeness, recall percentage across 8 information units, omitted anchors, and narrative sequencing.
     * **MindPlay:** Dual visual-verbal memory binding (`ch1_score`), chronological sequence ordering (`ch2_correct`), and visual target discrimination reaction latency (`ch3_reaction_ms`).
   * **Missing Module Governance:** Honest evaluation of partial or uncollected tasks (`tasks_completed_count`, `available_tasks`, `missing_tasks`, `completion_status`). Never invents default scores.
   * **Domain Level Summaries:** Acoustic-prosodic domain, episodic memory domain, and executive function domain summaries.

2. **Mode B: Personal Longitudinal History Comparison**
   * Evaluates within-subject changes across repeated sessions.
   * **Safe Historical Threshold:** If fewer than 2 completed sessions exist, provides an honest empty state (`has_sufficient_history: False`, message indicating $\ge 2$ sessions are required to establish an intra-individual baseline).
   * **Within-Subject Trajectories (when $\ge 2$ sessions):**
     * Story Recall accuracy change: $\Delta = \text{Current} - \text{Prior}$
     * Visual search latency change: $\Delta = \text{Current} - \text{Prior}$ (ms)
     * Acoustic pause ratio change: $\Delta = \text{Current} - \text{Prior}$
     * Voice pitch & energy stability: $\Delta F_0$, $\Delta \text{RMS}$
     * Trajectory labels: `increased`, `decreased`, `stable` (within $\pm 5\%$).
   * Avoids clinical diagnostic claims or disease progression assumptions.

3. **Mode C: Research Reference Benchmark Comparison**
   * Evaluates participant acoustic measurements against descriptive reference distributions computed from the cleaned DementiaNet dataset (`data/processed/voice_features_clean.csv`).
   * Empirical distribution percentiles: Median, Interquartile Range ($[Q_1, Q_3]$), and Min-Max across 100 cleaned recordings (80 unique speakers: 53 dementia-labeled, 47 nodementia-labeled).
   * Benchmark classification:
     * `Within Reference IQR` ($Q_1 \le x \le Q_3$)
     * `Within Cohort Range` ($\min \le x \le \max$)
     * `Variation from Cohort` ($x < \min$ or $x > \max$)
     * `Uncollected / Missing` (when task was not completed)
   * Multi-modal comparison chart normalized to percent of cohort median.

### 10.2 Empirical Reference Distributions (`data/processed/voice_features_clean.csv`)

| Acoustic Metric | Empirical Median | Interquartile Range $[Q_1 - Q_3]$ | Full Range $[\min - \max]$ | Mean $\pm$ Std |
|---|---|---|---|---|
| **Voiced Pitch ($F_0$)** | 135.5 Hz | $[119.6 - 153.9]$ Hz | $[81.0 - 221.2]$ Hz | $138.6 \pm 27.8$ Hz |
| **Low-Energy Pause Ratio** | 17.8% | $[11.5 - 24.6]$% | $[3.2 - 54.1]$% | $18.9 \pm 10.2$% |
| **Zero-Crossing Rate (ZCR)** | 0.082 | $[0.063 - 0.108]$ | $[0.024 - 0.205]$ | $0.089 \pm 0.035$ |
| **Speech RMS Energy** | 0.059 | $[0.039 - 0.084]$ | $[0.012 - 0.162]$ | $0.064 \pm 0.031$ |
| **Spectral Centroid** | 1,520 Hz | $[1,290 - 1,780]$ Hz | $[920 - 2,540]$ Hz | $1,555 \pm 312$ Hz |
| **Active Speech Duration** | 21.4 s | $[16.2 - 28.5]$ s | $[8.1 - 44.0]$ s | $22.8 \pm 8.2$ s |
| **Low-Energy Pause Count** | 5 intervals | $[3 - 7]$ intervals | $[1 - 14]$ intervals | $5.4 \pm 2.8$ intervals |

### 10.3 Provenance & Non-Diagnostic Clinical Disclaimers
* **Corpus Nature:** DementiaNet consists of publicly available broadcast interviews, speeches, and media appearances. It is NOT a clinical Alzheimer's patient cohort.
* **Non-Diagnostic Policy:** ALVI explicitly disclaims clinical diagnosis, disease probability calculation, and medical risk tiers. The exploratory Random Forest classifier outputs uncalibrated tree vote fractions, not disease probabilities.

### 10.4 FastAPI Endpoints
* `GET /api/cases/reference-stats` — Returns empirical acoustic reference distributions, sample size (100 recordings, 80 speakers), and provenance metadata.
* `POST /api/cases/compare` — Executes multi-modal case comparison across Mode A (Current), Mode B (History), and Mode C (Reference).

### 10.5 Automated Test Suite Execution
Run all automated tests covering Case Comparison, MindPlay, Story Recall, and Voice Check-in:
```bash
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py" -v
```

---

## 11. Phase 9 — Cognitive Learning Path & Personalized Practice Engine

### 11.1 Architectural Overview
Phase 9 implements an evidence-informed, transparent recommendation and longitudinal practice engine designed to transform ALVI's multi-modal cognitive assessment observations into structured, actionable mental engagement exercises. The system operates on clear deterministic heuristics without black-box or non-transparent ML steering:

```
[Assessment Observations]
  ├─ Voice Check-in (Pause ratio, duration, frame counts)
  ├─ Story Recall (Anchor completeness %, missed facts, transpositions)
  └─ MindPlay Challenges (Feature binding, chronology ordering, latency ms)
           │
           ▼
[LearningRecommendationEngine (backend/services/learning_recommendations.py)]
  ├─ Starter Curriculum (when no assessments exist)
  ├─ Deficit-Triggered Prioritization (Rules A-E)
  ├─ Multi-Modal Maintenance (Rule F)
  └─ Recency De-prioritization & Practice Rotation
           │
           ▼
[FastAPI Endpoints (/api/learning/*)]
  ├─ GET  /api/learning/catalog   — Full structured exercise registry
  ├─ POST /api/learning/recommend — Dynamic personalized 3-drill plan
  └─ POST /api/learning/progress  — Engagement metrics & milestone tracking
           │
           ▼
[Frontend UI (frontend/journey.html & journey.js)]
  ├─ Dynamic Learning Banner (Starter vs Personalized indicator & reason)
  ├─ Recommended Activities Grid (Priority badges, skill tags, duration, direct launch)
  ├─ Practice Progress Card (Total drills, unique count, active days, personal bests)
  ├─ Longitudinal Cognitive Trend Chart (Chart.js multi-session trajectory)
  └─ Scientific Notice on Familiarity Effects & Non-Diagnostic Disclaimers
```

### 11.2 Structured Exercise Catalog
The practice activities are defined in `backend/data/exercise_catalog.json` and mapped to active interactive modules within ALVI:
1. `ex_narrative_retell_foundations` — **Narrative Recall & Anchor Retrieval** (Memory / `story.html`, 2–3 min). Focuses on verbal/textual retelling of key information units (people, places, events) following audio presentation.
2. `ex_temporal_chronology_builder` — **Story Chronology & Temporal Sequencing** (Executive Sequencing / `mindplay.html`, 1–2 min). Focuses on milestone event order arrangement to practice temporal planning and working memory.
3. `ex_dual_feature_binding` — **Dual-Feature Memory Association** (Memory / `mindplay.html`, 1–2 min). Focuses on identifying multi-attribute targets while suppressing plausible lure distractors.
4. `ex_visual_search_agility` — **Target Discrimination & Visual Search** (Attention & Speed / `mindplay.html`, 1 min). Practice selective visual attention and motor promptness under reaction timing.
5. `ex_spontaneous_speech_description` — **Descriptive Scene Narration & Fluency** (Speech & Language / `voice.html`, 2–3 min). Focuses on unhurried picture description and spontaneous spoken fluency to reduce hesitation.
6. `ex_full_trio_review` — **Comprehensive Multi-Modal Check-in** (Multi-Modal / `voice.html`, 3–4 min). Full connected evaluation across all three modalities to maintain personal longitudinal baselines.

### 11.3 Deterministic Recommendation Rules
The engine evaluates actual assessment measurements using transparent, deterministic clinical heuristics:
* **Starter Path Mode:** For new users with no recorded check-ins, provides a 3-drill introductory curriculum covering Spontaneous Speech (`voice.html`), Narrative Retell (`story.html`), and Feature Association (`mindplay.html`).
* **Rule A (Story Recall Completeness):** Triggered when narrative recall score < 75.0% or missed anchor facts >= 2. Prioritizes `ex_narrative_retell_foundations`.
* **Rule B (MindPlay Chronology Ordering):** Triggered when Challenge 2 order is incorrect or transposed. Prioritizes `ex_temporal_chronology_builder`.
* **Rule C (MindPlay Feature Binding):** Triggered when Challenge 1 score < 2 or lure distractor was chosen. Prioritizes `ex_dual_feature_binding`.
* **Rule D (MindPlay Visual Search Latency):** Triggered when Challenge 3 reaction latency exceeds 3500ms or card selection is incorrect. Prioritizes `ex_visual_search_agility`.
* **Rule E (Voice Hesitation & Pause Density):** Triggered when low-energy pause frame ratio >= 0.28, pause count >= 8, or recording duration is compressed (< 15s). Prioritizes `ex_spontaneous_speech_description`.
* **Rule F (Maintenance & Rotation):** When metrics are balanced or fewer than 3 deficits are detected, fills remaining slots with complementary domains and applies recency de-prioritization to rotate out drills completed within the last 2 hours.

### 11.4 Practice Progress & Familiarity Effect Tracking
Tracking is handled by `PracticeProgressTracker` (`backend/services/practice_progress.py`):
* **Metrics:** Computes total activities completed, unique exercises attempted (out of 6), active practice days, total practice time (minutes/seconds), and consistency categorization (`Starting Out`, `Initial Practice Started`, `Active Routine`, `Consistent Daily Habit`).
* **Personal Bests:** Tracks highest score, fastest duration, repetition count, and date of last completion per exercise.
* **Honest Empty State:** When zero practice records exist, returns an empty breakdown and invites the user to start their first drill.
* **Familiarity Effects Disclaimer:** Prominently clarifies that longitudinal performance gains on repeated drills frequently reflect task-specific procedural learning (test-retest familiarity) rather than biological reversal or stabilization of underlying neuropathology.

### 11.5 FastAPI Endpoints
* `GET /api/learning/catalog` — Returns the complete structured practice catalog with all 6 activities, routes, and guidelines.
* `POST /api/learning/recommend` — Accepts `{ current_session, history_sessions, practice_history }` and returns 3 prioritized activities with transparent trigger explanations and path mode (`starter_curriculum` vs `personalized`).
* `POST /api/learning/progress` — Accepts `{ practice_records }` and returns engagement summary metrics, personal bests, and consistency label.

### 11.6 Automated Test Suite Execution
Run automated tests across the ALVI platform:
```bash
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py" -v
```

---

## 12. Phase 10 — Pattern Explorer & Longitudinal Performance Analytics

### 12.1 Architectural Overview
Phase 10 implements an evidence-grounded longitudinal analytics system that enables users and researchers to examine factual changes in performance across repeated ALVI sessions. The system operates on strictly observed measurements without fabricating cognitive progression scores, artificial decline percentages, or diagnostic predictions:

```
[Local Storage Records]
  ├─ alvi_session_history (Check-in sessions with voice, story, mindplay telemetry)
  └─ alvi_practice_history (Drill completions, initiated launches, durations)
           │
           ▼
[HistoryNormalizer (backend/services/history_normalization.py)]
  ├─ ISO timestamp validation & chronological sorting
  ├─ Deduplication (session ID & timestamp collision checks)
  ├─ Physiological bounds checking & NaN/Infinity elimination
  ├─ Missing data preservation (null values retained as null)
  └─ Demo/synthetic developer record quarantine
           │
           ▼
[PatternAnalyticsService & TrendStatistics (backend/services/)]
  ├─ Grouping into Voice, Story, MindPlay, Practice domains
  ├─ Threshold-governed comparison mode:
  │    ├─ n = 0: No data available
  │    ├─ n = 1: Single baseline established (no trend)
  │    ├─ n = 2: Pairwise comparison (absolute delta & percent change)
  │    └─ n >= 3: Longitudinal trajectory (OLS linear regression slope & dispersion)
  ├─ Outlier detection (> 1.7σ for n<=5, > 2.0σ for n>5)
  └─ Task version and difficulty comparability validation
           │
           ▼
[FastAPI Endpoints (/api/patterns/*)]
  ├─ GET  /api/patterns/metrics — Metric catalog, physical units, ranges, governance
  └─ POST /api/patterns/analyze — Complete time-series analytics & pairwise deltas
           │
           ▼
[Interactive Frontend (frontend/patterns.html & patterns.js)]
  ├─ History status & threshold banner (0, 1, 2, 3+ session modes)
  ├─ Multi-Modal Overview + 4 domain-specific sub-explorers
  ├─ 5 KPI summary tiles (Observations, Baseline, Latest, Mean, Delta change)
  ├─ Interactive Chart.js charts with distinct axes (ms, Hz, %, s)
  ├─ Point inspection cards & date-range filtering (All Time, 90d, 30d)
  ├─ Practice engagement habits (completions, active days, personal bests)
  └─ Offline local calculation mode & safe JSON metrics export
```

### 12.2 Data Integrity & History Normalization
`HistoryNormalizer` (`backend/services/history_normalization.py`) provides non-destructive sanitization:
* **Timestamps:** Parses ISO 8601 strings and sorts sessions chronologically (oldest to newest).
* **Identification:** Preserves user session IDs or creates deterministic fallback keys (`sess-<timestamp>-<index>`).
* **Deduplication:** Filters out redundant entries with duplicate IDs or identical timestamp seconds.
* **Metric Validation:** Clamps measurements to physiological bounds (F0: 40–800 Hz; RMS: 0–1; Reaction time: 150–30,000 ms; Scores: 0–100%). Rejects `NaN`, `Infinity`, and negative reaction times.
* **Missing Value Preservation:** Uncompleted or unmeasured tasks retain metrics as `None`/`null` rather than falsifying zero values.
* **Quarantine:** Flags `is_demo=True` or `is_sample=True` records and segregates them from genuine patient history.

### 12.3 Honest Trend Analysis Thresholds
`TrendStatistics` (`backend/services/trend_statistics.py`) enforces strict scientific thresholds:
* **n = 0:** Reports `no_data` with an honest empty-state view.
* **n = 1:** Reports `baseline_only`. Clearly states that a single point establishes a baseline but cannot form a comparison or trend.
* **n = 2:** Reports `pairwise_only`. Calculates absolute change and percentage change between the two sessions, but refuses to draw an artificial trend line.
* **n >= 3:** Reports `longitudinal_trend`. Fits an ordinary least squares (OLS) linear slope, calculates sample standard deviation, and classifies descriptive trajectory direction (`increasing`, `decreasing`, `stable`).
* **Outliers:** Flags values deviating $> 1.7\sigma$ (for $n \le 5$) or $> 2.0\sigma$ (for $n > 5$) with statistical explanation.

### 12.4 Multi-Modal Metric Domains & Physical Units
Visualizations strictly isolate disparate physical units onto dedicated charts and axes:
* **Voice Acoustics:** Mean F0 (`Hz`), RMS Signal Energy (`RMS amplitude`), Zero-Crossing Rate (`rate`), Low-Energy Frame Ratio (`pause proxy ratio`), Spectral Centroid (`Hz`), Duration (`seconds`).
* **Story Recall Memory:** Information Unit Completeness (`%`), Recalled Anchor Count (`units`), Missed Anchor Count (`units`), Chronological Inversions (`count`).
* **MindPlay Telemetry:** Overall Challenge Accuracy (`%`), Dual-Feature Binding Score (`0–2 pts`), Visual Search Reaction Latency (`ms` on dedicated millisecond axis), Total Duration (`seconds`).
* **Practice Engagement:** Completed Drills (`count`), Unique Drills (`0–6`), Total Practice Time (`minutes`).

### 12.5 Phase 9 Practice Completion Correction
Addressed the critical practice logging bug:
1. **Initiation vs Completion:** Clicking "Start Practice" logs an initiated attempt (`status: 'initiated'`, `completed: false`, `duration_seconds: 0`).
2. **Actual Completion:** Only verified task completion updates the record to `status: 'completed'`, `completed: true`.
3. **Quarantined Developer Logs:** The "+ Add Sample Practice Log" button sets `is_demo: true`, ensuring synthetic records do not contaminate genuine patient streaks or averages.

### 12.6 FastAPI Endpoints
* `GET /api/patterns/metrics` — Returns catalog of trackable metrics, units, typical ranges, and governance notices.
* `POST /api/patterns/analyze` — Accepts `{ session_history: [...], practice_history: [...], filter_options: {...} }` and returns normalized time-series, statistics, pairwise recent deltas, and practice milestones.

### 12.7 Scientific Governance & Non-Diagnostic Disclaimers
* **Task Familiarity & Practice Effects:** Both API responses and UI headers explicitly state that repeated performance gains in cognitive tasks reflect procedural familiarity (test-retest learning) rather than clinical cognitive restoration.
* **Acoustic Variance:** Clarifies that microphone hardware, distance, background noise, and speaking rate affect acoustic features.
* **Non-Diagnostic Policy:** ALVI explicitly disclaims Alzheimer's disease diagnosis, staging, and progression scoring.

### 12.8 Automated Test Suite Execution
Run all automated tests across the ALVI platform:
```bash
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py" -v
```

---

## 13. Phase 11 — Gemma 4 AI Insights & Personalized Explanation Engine

### 13.1 Architectural Overview
Phase 11 integrates Google's hosted Gemma 4 model (`gemma-4-26b-a4b-it`) via the official Google GenAI SDK (`google-genai`) to synthesize multi-modal assessment observations (Voice acoustic features, Story Recall NLP, MindPlay cognitive game telemetry, longitudinal patterns, and learning recommendations) into grounded, compassionate, and non-diagnostic explanations:

```
[Assessment Measurements]
  ├─ Voice Check-in (F0 pitch, RMS, ZCR, low-energy pause ratio, pause count)
  ├─ Story Recall (Completeness %, anchor units recalled vs omitted, intrusions)
  ├─ MindPlay Challenges (Dual-feature binding, chronology sequencing, latency ms)
  └─ Longitudinal Trends & Learning Path Recommendations
           │
           ▼
[InsightContextBuilder (backend/services/insight_builder.py)]
  ├─ Extracts authentic metrics into ground_metrics dictionary
  ├─ Builds grounded system prompt with strict non-diagnostic constraints
  └─ Generates deterministic rule-based fallback if external API is unavailable
           │
           ▼
[GemmaAIProvider (backend/services/gemma_service.py)]
  ├─ Hosted Gemma 4 API via google-genai SDK
  ├─ Exponential backoff retry logic (429 rate limits, 503 transient errors)
  ├─ Temperature 0.2-0.3 for deterministic, grounded outputs
  └─ Robust JSON extraction (handles markdown ```json ``` code fences)
           │
           ▼
[InsightValidator (backend/services/insight_validation.py)]
  ├─ Prompt-injection & medical roleplay sanitization (DAN mode, doctor personas)
  ├─ Schema validation (session_overview, voice, memory, executive, strengths, growth, focus)
  ├─ Non-diagnostic medical disclaimer strict attachment
  └─ Numeric grounding check against ground_metrics
           │
           ▼
[FastAPI Endpoints (/api/insights/*)]
  ├─ GET  /api/insights/status   — Provider configuration & availability status
  ├─ POST /api/insights/generate — Structured multi-modal cognitive explanation
  └─ POST /api/insights/chat     — Interactive grounded assistant conversation
           │
           ▼
[Frontend UI (frontend/insights.html & js/insights.js)]
  ├─ Dynamic status pill & offline fallback notice
  ├─ User consent checkbox & privacy transparency guarantee
  ├─ Structured Cognitive Explanations tabs (Voice, Story, MindPlay, Strengths, Growth)
  ├─ Interactive Gemma 4 Assistant chat with quick prompt chips
  ├─ Verifiable Grounded Measurements JSON inspector
  └─ Prominent Non-Diagnostic Research Disclaimer
```

### 13.2 Security, API Key Handling & Offline Fallback
* **SDK & Model:** Uses official `google-genai` Python SDK with `gemma-4-26b-a4b-it` (alternative: `gemma-4-31b-it`).
* **Environment Variables:** `GEMINI_API_KEY`, `AI_PROVIDER=gemma`, `AI_MODEL=gemma-4-26b-a4b-it`.
* **Zero Secret Exposure:** The API key is strictly stored in `.env` (git-ignored via `.gitignore`), never hardcoded, never sent to the client, never logged, and never included in API status responses.
* **Template Configuration:** `.env.example` is provided with clear setup instructions.
* **Deterministic Offline Mode:** If `GEMINI_API_KEY` is not configured, the backend starts normally, returns `configured: false, available: false` on `/api/insights/status`, and automatically generates high-quality deterministic rule-based explanations grounded in authentic numbers without throwing unhandled exceptions.

### 13.3 Grounding & Anti-Hallucination Constraints
* **Verifiable Inputs Only:** The engine cites only authentic metrics recorded during check-ins (e.g. F0 mean in Hz, low-energy frame ratio %, active speech duration, story recall composite %, information unit counts, visual search latency in ms).
* **Non-Diagnostic Policy:** The model system prompt strictly forbids diagnosing Alzheimer's disease, assigning dementia stages, or calculating disease progression risk.
* **Strict Disclaimers:** Every AI output (both generated reports and interactive chat replies) enforces the standard ALVI research disclaimer:
  > *"ALVI is an exploratory research screening tool, NOT a diagnostic medical device. These AI-generated observations describe acoustic and cognitive task patterns for informational and self-monitoring purposes only. They do not constitute a clinical diagnosis, medical prognosis, or formal evaluation of Alzheimer's disease or cognitive impairment. Always consult a licensed neurologist or physician for medical evaluation."*

### 13.4 Prompt Injection Sanitization
`InsightValidator.sanitize_user_input` detects and neutralizes:
* Instructions overriding system rules (`ignore all previous instructions`, `disregard prior guidelines`).
* Medical roleplay jailbreaks (`act as a neurologist`, `diagnose this patient`, `what stage of dementia do I have`).
* System prompt extraction attempts (`reveal system prompt`).
* Jailbreaks (`DAN mode`, `developer mode`, `bypass safety`).

### 13.5 FastAPI Endpoints
* `GET /api/insights/status` — Returns `{ "provider": "gemma", "model": "gemma-4-26b-a4b-it", "configured": bool, "available": bool, "version": "1.7.0" }`.
* `POST /api/insights/generate` — Accepts `{ "current_session": {...}, "history_sessions": [...], "practice_history": [...], "learning_recommendations": {...}, "user_consent": true }` and returns validated structured cognitive explanation.
* `POST /api/insights/chat` — Accepts `{ "question": "...", "current_session": {...}, "history_sessions": [...], "chat_history": [...], "user_consent": true }` and returns grounded assistant response with non-diagnostic notice.

### 13.6 Automated Test Suite Execution
Run all 110 automated tests across the ALVI platform:
```bash
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py" -v
```
Output:
```
Ran 110 tests in 2.805s
OK
```
All 27 dedicated AI Insights test cases (`backend/tests/test_ai_insights.py`) and all 83 existing test cases across Voice ML, Story Recall NLP, MindPlay, Case Comparison, Learning Path, and Pattern Explorer passed with 100% success rate.






