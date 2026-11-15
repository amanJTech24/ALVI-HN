# Mini Timmy Companion & Cognitive Activities Design Notes

**Project:** ALVI Pocket Companion (Phase 12)  
**Character:** Mini Timmy (Embedded Visual & Emotional Companion)

---

## 1. Character Specification

Mini Timmy is an animated on-device character designed to provide comforting, empathetic, and non-judgmental presence during daily cognitive exercises.

Mini Timmy features:
- **Geometry:** Vertically oriented oval head drawn with double-outlined anti-aliased ellipse primitives (`fillEllipse` and `drawEllipse`).
- **Eyes:** Two large circular eyes with dark pupils and reflective specular highlights.
- **Eyebrows:** Dynamic brow angles reflecting emotional states (e.g., worried inward tilts for anxiety, soft raised arches for happiness).
- **Mouth:** Smooth bezier/arc curved mouth expressions reflecting emotional valence.
- **Animations:**
  - *Spontaneous Blinking:* Random intervals between 3.0 and 6.0 seconds (duration: 150 ms) with closed-lid graphics.
  - *Saccadic Glances:* Subtle left-to-right pupil glances every 4.0 to 9.0 seconds to give lifelike presence without distracting the user.
  - *Non-blocking Execution:* All animations are scheduled via `millis()` timer state machines without blocking the main event loop or user button presses.

---

## 2. Emotional Expressions & Mood Options

Mini Timmy presents 6 user-selected emotional check-in options:

| Mood | Enum Value | Facial Features | Supportive Micro-Message |
|:---|:---:|:---|:---|
| **Happy** | `MOOD_HAPPY` | Wide upward curving mouth, raised arched brows | *"Glad to see your smile!"* |
| **Calm** | `MOOD_CALM` | Gentle straight relaxed mouth, neutral brows | *"Peaceful moments help."* |
| **Tired** | `MOOD_TIRED` | Half-mast eyelids, gentle downturned mouth | *"Rest is brain medicine."* |
| **Sad** | `MOOD_SAD` | Downward curved frown, inverted angled brows | *"I'm right here with you."* |
| **Anxious** | `MOOD_ANXIOUS`| Wavy undulating mouth line, raised furrowed inner brows | *"Take a gentle breath."* |
| **Okay** | `MOOD_OKAY` | Slight subtle smile, neutral soft brows | *"Steady and strong."* |

---

## 3. Cognitive Tasks Specification

### A. Memory Sequence Game (`hw_memory_seq`)
- **Nature of Task:** 4-color pattern recall task.
- **Scoring Dimensions:**
  - `max_level`: Highest sequence length successfully reproduced.
  - `correct_count`: Cumulative count of correct color inputs.
  - `error_count`: Errors made before session conclusion.
  - `duration_ms`: Total session time.
- **Separation Notice:** This embedded task is assigned `activity_id = "hw_memory_seq"`. It is purposefully distinct from the narrative-based MindPlay browser games (`ch1`, `ch2`, `ch3`) to preserve clinical validity.

### B. Reaction Time Task (`hw_reaction_test`)
- **Nature of Task:** Visual stimulus latency task.
- **Timing Engine:** ESP32 hardware timer (`esp_timer_get_time()`) providing microsecond precision.
- **Protocol:**
  - 5 sequential trials.
  - Random preparatory delay (1,500 ms – 4,000 ms) to prevent anticipatory timing.
  - False-start detection: Any button press during the preparatory wait phase is flagged as a false start.
  - Plausibility threshold: Latencies under 150 ms are classified as premature anticipation.
  - Summary metric: Calculated statistical **median** reaction time (ms) to resist outlier contamination.
