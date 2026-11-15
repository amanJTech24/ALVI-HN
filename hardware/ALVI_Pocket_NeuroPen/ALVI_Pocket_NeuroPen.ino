/*
  ALVI Pocket Companion -- standalone Arduino IDE demonstration firmware.
  ESP32 Dev Module + ST7735 128x160 SPI screen in landscape (160x128).
  Libraries: Adafruit GFX, Adafruit ST7735/ST7789, ArduinoJson >= 7.

  BACK  = GPIO25 -> GND   UP     = GPIO26 -> GND
  DOWN  = GPIO27 -> GND   SELECT = GPIO32 -> GND
  TFT SCK=18, MOSI=23, CS=21, DC/A0=16, RESET=17
  TFT VCC=3V3, GND=GND; TFT LED only after checking its circuit.
  Status LED GPIO22 through a 220-ohm resistor.
  Optional buzzer on GPIO33 disabled by default: confirm driver/current first.

  IMPORTANT: Serial JSON messages, including NeuroPen START/FINISH, are
  functional on-device but the schema MUST be matched to your ALVI Python
  bridge before claiming end-to-end backend compatibility.
  The ESP32 does not capture camera video or speech. Use a phone/laptop.
*/
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <math.h>
#include <time.h>

#define TFT_CS       21
#define TFT_DC       16
#define TFT_RST      17
#define BTN_BACK     25
#define BTN_UP       26
#define BTN_DOWN     27
#define BTN_SELECT   32
#define STATUS_LED   22
#define BUZZER_PIN   33
#define ENABLE_BUZZER 0   // Change to 1 ONLY with a safe driver/module

Adafruit_ST7735 tft(TFT_CS, TFT_DC, TFT_RST);
Preferences prefs;
const uint16_t BG = 0x0824;
const uint16_t ACCENT = 0x23B6;
const uint16_t PALE = ST77XX_WHITE;
const uint8_t pins[4] = {BTN_BACK, BTN_UP, BTN_DOWN, BTN_SELECT};
const char* menuItems[7] = {"Timmy & Mood", "Memory Game", "Reaction Test",
                             "Voice Check-in", "Reminders", "Device Sync", "NeuroPen"};
const char* moods[6] = {"Happy", "Calm", "Tired", "Sad", "Anxious", "Okay"};
const char* colors[4] = {"RED", "GREEN", "BLUE", "YELLOW"};
const uint16_t colorCode[4] = {ST77XX_RED, ST77XX_GREEN, ST77XX_BLUE, ST77XX_YELLOW};

// Each click is accepted on the stable HIGH->LOW transition.
bool lastRaw[4] = {HIGH, HIGH, HIGH, HIGH};
bool stable[4]  = {HIGH, HIGH, HIGH, HIGH};
uint32_t changedAt[4] = {0, 0, 0, 0};
int buttonEvent() {
  int event = -1;
  uint32_t now = millis();
  for (int i = 0; i < 4; ++i) {
    bool raw = digitalRead(pins[i]);
    if (raw != lastRaw[i]) changedAt[i] = now;
    if (raw != stable[i] && now - changedAt[i] >= 35) {
      stable[i] = raw;
      if (raw == LOW && event < 0) event = i;
    }
    lastRaw[i] = raw;
  }
  return event;
}

void activityBeep() {
  digitalWrite(STATUS_LED, HIGH);
#if ENABLE_BUZZER
  digitalWrite(BUZZER_PIN, HIGH);
#endif
}
uint32_t feedbackUntil = 0;
void shortFeedback() {
  activityBeep();
  feedbackUntil = millis() + 65;
}
void feedbackTick() {
  if (feedbackUntil && (int32_t)(millis() - feedbackUntil) >= 0) {
    digitalWrite(STATUS_LED, LOW);
#if ENABLE_BUZZER
    digitalWrite(BUZZER_PIN, LOW);
#endif
    feedbackUntil = 0;
  }
}

// ----- Persistent settings and USB JSON event queue -----
const int QUEUE_LIMIT = 12;
String deviceId, pairedSession, serialInput;
int pendingSlot = -1, retryCount = 0;
uint32_t lastSend = 0, lastAck = 0;
uint32_t syncEpoch = 0, syncUptime = 0; // UTC seconds, if TIME_SYNC received
String currentVoiceStatus = "Use laptop mic";
bool voiceDirty = false;

String newUUID() {
  uint8_t v[16];
  for (int i = 0; i < 16; i += 4) {
    uint32_t r = esp_random();
    memcpy(v + i, &r, 4);
  }
  v[6] = (v[6] & 0x0F) | 0x40;
  v[8] = (v[8] & 0x3F) | 0x80;
  char out[37];
  snprintf(out, sizeof(out),
    "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
    v[0],v[1],v[2],v[3],v[4],v[5],v[6],v[7],v[8],v[9],v[10],v[11],v[12],v[13],v[14],v[15]);
  return String(out);
}
String qKey(int i) { return "evt" + String(i); }
int queuedCount() {
  int n = 0;
  for (int i = 0; i < QUEUE_LIMIT; ++i) if (prefs.getString(qKey(i).c_str(), "").length()) ++n;
  return n;
}
bool savePacket(const String &packet) {
  for (int i = 0; i < QUEUE_LIMIT; ++i) {
    if (prefs.getString(qKey(i).c_str(), "").isEmpty()) {
      return prefs.putString(qKey(i).c_str(), packet) == packet.length();
    }
  }
  return false;  // Never claim that unsaved data was synchronized.
}
void fillEvent(JsonDocument &j, const char *type, const char *activity) {
  j["protocol_version"] = "1.0";
  j["type"] = type;
  j["message_type"] = type;
  j["device_id"] = deviceId;
  j["event_id"] = newUUID();
  j["session_id"] = pairedSession;
  j["activity_id"] = activity;
  j["uptime_ms"] = millis();
  if (syncEpoch) {
    time_t ts = (time_t)(syncEpoch + (millis() - syncUptime) / 1000UL);
    struct tm utc;
    gmtime_r(&ts, &utc);
    char iso[25];
    strftime(iso, sizeof(iso), "%Y-%m-%dT%H:%M:%SZ", &utc);
    j["timestamp"] = iso;
  }
}
bool queueEvent(JsonDocument &event) {
  String out;
  serializeJson(event, out);
  bool ok = savePacket(out);
  if (ok) { pendingSlot = -1; retryCount = 0; }
  return ok;
}
void sendHello() {
  JsonDocument j;
  j["protocol_version"] = "1.0";
  j["type"] = "HELLO";
  j["message_type"] = "HELLO";
  j["device_id"] = deviceId;
  j["firmware"] = "alvi-pocket-1.0";
  j["pending_count"] = queuedCount();
  serializeJson(j, Serial); Serial.println();
}
void resendPending(bool manual = false) {
  uint32_t now = millis();
  if (manual) { pendingSlot = -1; retryCount = 0; }
  if (pendingSlot >= 0 && now - lastSend < 3500) return;
  if (pendingSlot >= 0 && retryCount >= 3) return; // Keep event stored for next manual retry/reboot.
  if (pendingSlot < 0) {
    for (int i = 0; i < QUEUE_LIMIT; ++i) {
      if (!prefs.getString(qKey(i).c_str(), "").isEmpty()) {
        pendingSlot = i; retryCount = 0; break;
      }
    }
  }
  if (pendingSlot >= 0) {
    String packet = prefs.getString(qKey(pendingSlot).c_str(), "");
    if (!packet.isEmpty()) {
      Serial.println(packet);
      retryCount++;
      lastSend = now;
    }
  }
}
void readSerialLine(const String &line) {
  JsonDocument j;
  if (deserializeJson(j, line)) return;
  const char* typ = j["type"] | "";
  if (!typ[0]) typ = j["message_type"] | "";
  String type(typ);
  if (type == "SYNC_ACK") {
    String ack = j["event_id"] | "";
    if (pendingSlot >= 0 && !ack.isEmpty()) {
      JsonDocument sent;
      if (!deserializeJson(sent, prefs.getString(qKey(pendingSlot).c_str(), "")) &&
          ack == String(sent["event_id"] | "")) {
        prefs.remove(qKey(pendingSlot).c_str());
        pendingSlot = -1; retryCount = 0; lastAck = millis();
      }
    }
  } else if (type == "PAIR_REQUEST") {
    String id = j["session_id"] | "";
    if (!id.isEmpty() && id.length() <= 64) {
      pairedSession = id;
      prefs.putString("session", pairedSession);
      sendHello();
    }
  } else if (type == "HELLO_ACK" || type == "DEVICE_ACK") {
    lastAck = millis();
  } else if (type == "TIME_SYNC") {
    uint32_t ts = j["epoch"] | 0UL;
    if (ts > 1600000000UL) { syncEpoch = ts; syncUptime = millis(); }
  } else if (type == "VOICE_STATUS" || type == "VOICE_RESULT") {
    currentVoiceStatus = String(j["status"] | "Update received");
    if (currentVoiceStatus.length() > 24) currentVoiceStatus.remove(24);
    voiceDirty = true;
    lastAck = millis();
  }
}
void serialTick() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') { readSerialLine(serialInput); serialInput = ""; }
    else if (c != '\r' && serialInput.length() < 1024) serialInput += c;
    else if (serialInput.length() >= 1024) serialInput = "";
  }
  resendPending();
}

// ----- Screen drawing -----
enum Page {WELCOME, MAIN_MENU, TIMMY, CONFIRMED, MEMORY, REACTION,
           VOICE, REMINDERS, SYNC, NEUROPEN, REMINDER_ALERT};
Page page = WELCOME;
int menuIndex = 0, moodIndex = 0;
bool previousBlink = false;
int previousGlance = 0;
uint32_t lastFaceDraw = 0;

void header(const char *text) {
  tft.setTextSize(1); tft.setTextColor(ST77XX_CYAN);
  tft.setCursor(4, 5); tft.print(text);
  tft.drawFastHLine(0, 18, 160, ACCENT);
}
void baseScreen(const char *text) {
  tft.fillScreen(BG);
  tft.setTextWrap(false);
  header(text);
}
void lineText(int x, int y, const String &s, uint16_t color = ST77XX_WHITE) {
  tft.setTextSize(1); tft.setTextColor(color);
  tft.setCursor(x, y); tft.print(s);
}
void oval(int cx, int cy, int rx, int ry, uint16_t color) {
  int lastX = cx + rx, lastY = cy;
  for (int d = 6; d <= 360; d += 6) {
    float a = d * PI / 180.0f;
    int x = cx + roundf(rx * cosf(a));
    int y = cy + roundf(ry * sinf(a));
    tft.drawLine(lastX, lastY, x, y, color);
    lastX = x; lastY = y;
  }
}
void face(int cx, int cy, int rx, int ry, bool blink, int glance) {
  tft.fillRect(cx-rx-2, cy-ry-2, rx*2+5, ry*2+5, BG);
  oval(cx, cy, rx, ry, ST77XX_WHITE);
  int ex = rx / 3, ey = cy - 7;
  for (int s = -1; s <= 1; s += 2) {
    int x = cx+s*ex;
    if (blink || moodIndex == 2) tft.drawFastHLine(x-8, ey, 16, PALE);
    else {
      tft.fillCircle(x, ey, 9, PALE);
      tft.fillCircle(x+glance*2, ey, 4, ST77XX_BLACK);
      tft.fillCircle(x+glance*2+1, ey-2, 1, PALE);
    }
  }
  int y = cy + ry/2;
  if (moodIndex == 0) { // smile
    tft.drawLine(cx-10,y-2,cx-5,y+4,ST77XX_CYAN);
    tft.drawFastHLine(cx-5,y+4,10,ST77XX_CYAN);
    tft.drawLine(cx+5,y+4,cx+10,y-2,ST77XX_CYAN);
  } else if (moodIndex == 3) {
    tft.drawLine(cx-9,y+3,cx,y-3,PALE); tft.drawLine(cx,y-3,cx+9,y+3,PALE);
  } else if (moodIndex == 4) tft.drawCircle(cx,y,4,PALE);
  else tft.drawFastHLine(cx-8,y,16,PALE);
}
void drawFace(bool blink, int glance) {
  if (page == WELCOME) face(80,66,35,39,blink,glance);
  if (page == TIMMY) face(42,68,29,35,blink,glance);
  if (page == CONFIRMED) face(80,61,34,37,blink,glance);
}
void renderHome() {
  baseScreen("ALVI POCKET LAB"); drawFace(false,0);
  lineText(24,115,"SELECT to start",ST77XX_CYAN);
}
void renderMenu() {
  baseScreen("ALVI - MAIN MENU");
  int first = menuIndex >= 5 ? menuIndex-4 : 0;
  for (int i=0; i<5; ++i) {
    int item=first+i; if (item>=7) break;
    int y=24+i*17;
    if (item==menuIndex) tft.fillRoundRect(3,y,154,16,3,ACCENT);
    lineText(8,y+4,String(item==menuIndex?"> ":"  ")+menuItems[item]);
  }
  lineText(4,116,"UP/DN SELECT BACK",ST77XX_CYAN);
}
void renderTimmy() {
  baseScreen("TIMMY - MOOD CHECK"); drawFace(false,0);
  lineText(87,42,"I feel:"); lineText(87,60,moods[moodIndex],ST77XX_CYAN);
  lineText(86,83,"UP / DOWN"); lineText(86,95,"SELECT");
  lineText(5,116,"BACK = MENU",ST77XX_CYAN);
}
void renderConfirmed() {
  baseScreen("TIMMY - SAVED"); drawFace(false,0);
  lineText(28,104,"Mood: " + String(moods[moodIndex]),ST77XX_GREEN);
  lineText(5,117,"BACK:MENU SELECT:EDIT");
}

// ----- Memory game: five real rounds of four-color sequence recall -----
enum MemoryPhase {MEM_READY, MEM_SHOW, MEM_GAP, MEM_INPUT, MEM_RESULT, MEM_FINISHED};
MemoryPhase memPhase = MEM_READY;
uint8_t sequence[6];
int memRound=0, memShowing=0, memInputPos=0, memChoice=0;
int memCorrect=0, memErrors=0, memPerfectMax=0, memRoundErrors=0;
uint32_t memSince=0, memStart=0;
bool memStored = true;

void renderMemory() {
  baseScreen("ALVI MEMORY CHALLENGE");
  if (memPhase == MEM_READY) {
    lineText(9,39,"Remember color order");
    lineText(9,57,"5 rounds: 2 to 6");
    lineText(9,82,"SELECT = Start",ST77XX_CYAN);
    lineText(9,116,"BACK = Menu");
  } else if (memPhase == MEM_SHOW) {
    lineText(10,28,"WATCH - Round " + String(memRound+1));
    tft.fillRoundRect(49,46,62,45,7,colorCode[sequence[memShowing]]);
    lineText(59,99,String(memShowing+1)+" / "+String(memRound+2));
  } else if (memPhase == MEM_GAP) {
    lineText(10,39,"Remember the order...");
    lineText(65,75,"...",ST77XX_CYAN);
  } else if (memPhase == MEM_INPUT) {
    lineText(8,26,"RECALL " + String(memInputPos+1)+" / "+String(memRound+2));
    tft.fillRoundRect(40,42,80,47,6,colorCode[memChoice]);
    lineText(57,96,colors[memChoice]);
    lineText(5,115,"UP/DN  SELECT  BACK");
  } else if (memPhase == MEM_RESULT) {
    lineText(11,46,memRoundErrors ? "Round complete" : "Perfect round!",ST77XX_CYAN);
    lineText(11,66,"Correct: " + String(memCorrect));
    lineText(11,83,"Mistakes: " + String(memErrors));
  } else {
    lineText(10,35,"5 ROUNDS COMPLETE",ST77XX_GREEN);
    lineText(10,55,"Correct: " + String(memCorrect));
    lineText(10,69,"Mistakes: " + String(memErrors));
    lineText(10,83,"Best level: " + String(memPerfectMax));
    lineText(10,98,memStored ? "Result saved locally" : "QUEUE FULL: not saved",memStored?ST77XX_CYAN:ST77XX_RED);
    lineText(6,117,"BACK:MENU SELECT:AGAIN");
  }
}
void beginMemoryRound() {
  memShowing = 0; memInputPos=0; memChoice=0; memRoundErrors=0;
  memPhase=MEM_SHOW; memSince=millis(); renderMemory();
}
void startMemory() {
  memRound=0; memCorrect=0; memErrors=0; memPerfectMax=0;
  for (int i=0; i<6; ++i) sequence[i] = (uint8_t)random(0,4);
  memStart=millis(); beginMemoryRound();
}
void finishMemory() {
  memPhase=MEM_FINISHED;
  JsonDocument j; fillEvent(j,"MEMORY_RESULT","hw_memory_seq");
  JsonObject p=j["payload"].to<JsonObject>();
  p["max_level"]=memPerfectMax;
  p["correct_count"]=memCorrect;
  p["error_count"]=memErrors;
  p["rounds_completed"]=5;
  p["duration_ms"]=(uint32_t)(millis()-memStart);
  p["completed"]=true;
  memStored=queueEvent(j); renderMemory();
}
void memoryTick() {
  uint32_t now=millis();
  if (page != MEMORY) return;
  if (memPhase==MEM_SHOW && now-memSince>=750) {
    memPhase=MEM_GAP; memSince=now; renderMemory();
  } else if (memPhase==MEM_GAP && now-memSince>=260) {
    memShowing++;
    if (memShowing >= memRound+2) {memPhase=MEM_INPUT;memChoice=0;}
    else memPhase=MEM_SHOW;
    memSince=now; renderMemory();
  } else if (memPhase==MEM_RESULT && now-memSince>=900) {
    if (memRound>=5) finishMemory();
    else beginMemoryRound();
  }
}
void memoryButton(int b) {
  if (b==0) {page=MAIN_MENU;renderMenu();return;}
  if (memPhase==MEM_READY || memPhase==MEM_FINISHED) {
    if (b==3) startMemory(); return;
  }
  if (memPhase!=MEM_INPUT) return;
  if (b==1) memChoice=(memChoice+3)%4;
  else if (b==2) memChoice=(memChoice+1)%4;
  else if (b==3) {
    if (memChoice==sequence[memInputPos]) memCorrect++;
    else {memErrors++;memRoundErrors++;}
    memInputPos++; shortFeedback();
    if (memInputPos>=memRound+2) {
      if (memRoundErrors==0) memPerfectMax=memRound+2;
      memRound++;
      memPhase=MEM_RESULT; memSince=millis();
    }
  }
  renderMemory();
}

// ----- Reaction test: real stimulus-to-button timing, 5 valid/missed trials -----
enum ReactionPhase {RT_READY, RT_WAIT, RT_GO, RT_RESULT, RT_FINISHED};
ReactionPhase rtPhase=RT_READY;
uint32_t rtWaitSince=0, rtDelay=0, rtResultSince=0;
int64_t rtStimulusUs=0;
int rtSamples[5];
int rtValid=0, rtMissed=0, rtFalseStarts=0, rtLast=-1;
bool rtStored=true;
int reactionMedian() {
  if (rtValid==0) return -1;
  int a[5]; for (int i=0;i<rtValid;++i) a[i]=rtSamples[i];
  for (int i=1;i<rtValid;++i) {
    int v=a[i], k=i-1;
    while (k>=0 && a[k]>v) {a[k+1]=a[k];--k;}
    a[k+1]=v;
  }
  return rtValid%2 ? a[rtValid/2] : (a[rtValid/2-1]+a[rtValid/2])/2;
}
void renderReaction() {
  baseScreen("ALVI REACTION TEST");
  if (rtPhase==RT_READY) {
    lineText(8,33,"Wait for GREEN signal");
    lineText(8,52,"Then press SELECT");
    lineText(8,76,"5 timed trials");
    lineText(8,98,"SELECT = Start",ST77XX_CYAN);
  } else if (rtPhase==RT_WAIT) {
    tft.fillRoundRect(18,34,124,60,8,ST77XX_RED);
    lineText(46,57,"WAIT...",ST77XX_WHITE);
    lineText(7,111,"No early presses!");
  } else if (rtPhase==RT_GO) {
    tft.fillRoundRect(18,34,124,60,8,ST77XX_GREEN);
    lineText(60,56,"GO!",ST77XX_BLACK);
    lineText(8,112,"PRESS SELECT NOW!");
    // Timestamp *after* drawing the visible stimulus, not before the random wait.
    rtStimulusUs=esp_timer_get_time();
  } else if (rtPhase==RT_RESULT) {
    String s = rtLast==-2 ? "FALSE START!" : rtLast==-1 ? "MISSED!" : "Time: "+String(rtLast)+" ms";
    lineText(12,48,s,rtLast>=0?ST77XX_GREEN:ST77XX_RED);
    lineText(12,68,"Trials: " + String(rtValid+rtMissed) + "/5");
    lineText(12,84,"Early taps: " + String(rtFalseStarts));
  } else {
    lineText(10,35,"REACTION COMPLETE",ST77XX_GREEN);
    lineText(10,53,"Valid: " + String(rtValid) + "/5");
    lineText(10,68,"Early taps: " + String(rtFalseStarts));
    lineText(10,83,rtValid?"Median: "+String(reactionMedian())+" ms":"No valid trials");
    lineText(10,97,rtStored?"Result saved locally":"QUEUE FULL: not saved",rtStored?ST77XX_CYAN:ST77XX_RED);
    lineText(6,117,"BACK:MENU SELECT:AGAIN");
  }
}
void startReactionTrial() {
  rtPhase=RT_WAIT; rtDelay=(uint32_t)random(1500,4001);
  rtWaitSince=millis(); renderReaction();
}
void startReaction() {
  rtValid=0;rtMissed=0;rtFalseStarts=0;rtLast=-1;
  startReactionTrial();
}
void finishReaction() {
  rtPhase=RT_FINISHED;
  JsonDocument j; fillEvent(j,"REACTION_RESULT","hw_reaction_test");
  JsonObject p=j["payload"].to<JsonObject>();
  if (rtValid) p["median_rt_ms"]=reactionMedian();
  else p["median_rt_ms"]=nullptr;
  p["valid_trials"]=rtValid;
  p["false_starts"]=rtFalseStarts;
  p["missed"]=rtMissed;
  p["trial_count"]=5;
  p["completed"]=true;
  JsonArray trials=p["reaction_times_ms"].to<JsonArray>();
  for (int i=0;i<rtValid;++i) trials.add(rtSamples[i]);
  rtStored=queueEvent(j); renderReaction();
}
void reactionTick() {
  if (page!=REACTION) return;
  uint32_t now=millis();
  if (rtPhase==RT_WAIT && now-rtWaitSince>=rtDelay) {
    rtPhase=RT_GO;renderReaction();
  } else if (rtPhase==RT_GO && esp_timer_get_time()-rtStimulusUs>=10000000LL) {
    rtMissed++;rtLast=-1;rtPhase=RT_RESULT;rtResultSince=now;renderReaction();
  } else if (rtPhase==RT_RESULT && now-rtResultSince>=950) {
    if (rtValid+rtMissed>=5) finishReaction();
    else startReactionTrial();
  }
}
void reactionButton(int b) {
  if (b==0) {page=MAIN_MENU;renderMenu();return;}
  if (rtPhase==RT_READY || rtPhase==RT_FINISHED) {
    if (b==3) startReaction();return;
  }
  if (b!=3) return;
  if (rtPhase==RT_WAIT) {
    rtFalseStarts++; rtLast=-2;
    rtPhase=RT_RESULT;rtResultSince=millis();renderReaction();
  } else if (rtPhase==RT_GO) {
    int ms=(int)((esp_timer_get_time()-rtStimulusUs)/1000);
    if (ms<150) {rtFalseStarts++;rtLast=-2;}
    else if (ms>10000) {rtMissed++;rtLast=-1;}
    else {rtSamples[rtValid++]=ms;rtLast=ms;shortFeedback();}
    rtPhase=RT_RESULT;rtResultSince=millis();renderReaction();
  }
}

// ----- Reminder settings: countdown while device is powered -----
bool reminderEnabled=false;
uint16_t reminderMinutes=30;
uint32_t reminderLast=0;
void renderReminders() {
  baseScreen("ALVI REMINDERS");
  lineText(10,32,reminderEnabled?"Reminder: ON":"Reminder: OFF",reminderEnabled?ST77XX_GREEN:ST77XX_RED);
  lineText(10,52,"Every " + String(reminderMinutes) + " min");
  lineText(10,75,"UP/DOWN: Change time");
  lineText(10,90,"SELECT: Toggle ON/OFF");
  lineText(10,115,"BACK: Menu",ST77XX_CYAN);
}
void reminderButton(int b) {
  if (b==0) {page=MAIN_MENU;renderMenu();return;}
  const uint16_t values[5]={15,30,60,120,240};
  int idx=0; while (idx<4 && values[idx]!=reminderMinutes) idx++;
  if (b==1) reminderMinutes=values[(idx+4)%5];
  if (b==2) reminderMinutes=values[(idx+1)%5];
  if (b==3) reminderEnabled=!reminderEnabled;
  reminderLast=millis();
  prefs.putBool("remOn",reminderEnabled);
  prefs.putUShort("remMin",reminderMinutes);
  renderReminders();
}
void reminderTick() {
  if (!reminderEnabled || page==REMINDER_ALERT) return;
  if (millis()-reminderLast < (uint32_t)reminderMinutes*60000UL) return;
  // Do not interrupt an active game or mood selection.
  if (page!=WELCOME && page!=MAIN_MENU) return;
  page=REMINDER_ALERT;
  baseScreen("ALVI PRACTICE TIME");
  lineText(15,39,"Time for a short",ST77XX_CYAN);
  lineText(15,54,"cognitive activity!");
  lineText(9,84,"SELECT: Dismiss");
  lineText(9,101,"BACK: Snooze 5 min");
  shortFeedback();
}
void reminderAlertButton(int b) {
  if (b!=0 && b!=3) return;
  uint32_t now=millis();
  if (b==0) { // 5-minute snooze (without claiming wall-clock scheduling)
    reminderLast=now - ((uint32_t)reminderMinutes-5UL)*60000UL;
  } else reminderLast=now;
  page=MAIN_MENU;renderMenu();
}

// ----- Voice, USB status, and future NeuroPen screens -----
void renderVoice() {
  baseScreen("ALVI VOICE CHECK-IN");
  lineText(7,29,"Use laptop microphone");
  lineText(7,45,"Open: localhost:5500");
  lineText(7,59,"/voice.html");
  lineText(7,81,"Status:",ST77XX_CYAN);
  lineText(7,96,currentVoiceStatus);
  lineText(7,116,"BACK: Menu");
}
void renderSync() {
  baseScreen("ALVI DEVICE SYNC");
  lineText(6,27,"ID: " + deviceId.substring(0,20));
  lineText(6,42,"Queue: " + String(queuedCount()) + " pending");
  lineText(6,57,"Serial: 115200 baud");
  lineText(6,72,lastAck?"Bridge ACK received":"No bridge ACK yet",lastAck?ST77XX_GREEN:ST77XX_YELLOW);
  lineText(6,90,"SELECT: Retry sync",ST77XX_CYAN);
  lineText(6,116,"BACK: Menu");
}
// ----- NeuroPen: real physical clock drawing timer and serial event queue -----
// The ESP32 handles the task prompt + timing. A phone records the drawing.
// The external ALVI website/backend must implement photo/video scoring.
enum NeuroPhase {NP_READY, NP_RUNNING, NP_DONE, NP_QUEUE_ERROR};
NeuroPhase neuroPhase = NP_READY;
uint32_t neuroStartedAt = 0;
uint32_t neuroDurationMs = 0;
uint32_t neuroLastSecond = 0xFFFFFFFFUL;
String neuroAssessmentId = "";
bool neuroEventSaved = false;

String neuroNewId() {
  // Short human-readable code: use this SAME code when uploading camera media.
  // A UUID is used for each serial event by fillEvent(), independently.
  return String("NP-") + newUUID().substring(0, 8);
}

bool neuroQueueEvent(const char *eventType, uint32_t elapsedMs = 0) {
  JsonDocument j;
  fillEvent(j, eventType, "hw_neuropen_clock");
  // Preserve the existing pairedSession in the envelope's session_id.
  // This test has its own independent association code.
  j["assessment_id"] = neuroAssessmentId;
  JsonObject p = j["payload"].to<JsonObject>();
  p["assessment_id"] = neuroAssessmentId;
  p["task"] = "clock_drawing";
  p["target_time"] = "11:10";
  p["capture_method"] = "phone_camera_or_webcam";
  if (strcmp(eventType, "NEUROPEN_FINISHED") == 0 ||
      strcmp(eventType, "NEUROPEN_CANCELLED") == 0) {
    p["duration_ms"] = elapsedMs;
  }
  return queueEvent(j);  // Persist in ESP32 NVS until a matching ACK.
}

void renderNeuroPen() {
  baseScreen("ALVI NEUROPEN");
  if (neuroPhase == NP_READY) {
    lineText(8,27,"CLOCK DRAWING TEST",ST77XX_CYAN);
    lineText(8,44,"Draw a clock on paper");
    lineText(8,60,"showing 11:10");
    lineText(8,82,"Phone: record drawing");
    lineText(8,103,"SELECT: START",ST77XX_GREEN);
    lineText(8,116,"BACK: MENU");
  } else if (neuroPhase == NP_RUNNING) {
    lineText(8,28,"DRAW CLOCK: 11:10",ST77XX_CYAN);
    lineText(8,47,"Drawing on paper...");
    lineText(8,63,"Code: " + neuroAssessmentId);
    lineText(8,80,"Time: " + String((millis()-neuroStartedAt)/1000UL) + " s",ST77XX_GREEN);
    lineText(8,105,"SELECT: FINISH",ST77XX_CYAN);
    lineText(8,117,"BACK: CANCEL");
    neuroLastSecond = (millis()-neuroStartedAt)/1000UL;
  } else if (neuroPhase == NP_DONE) {
    lineText(7,29,"DRAWING COMPLETED",ST77XX_GREEN);
    lineText(7,46,"Duration: " + String(neuroDurationMs/1000UL) + " s");
    lineText(7,62,"Code: " + neuroAssessmentId);
    lineText(7,77,neuroEventSaved ? "Events queued for USB" : "FINISH EVENT NOT SAVED",
             neuroEventSaved ? ST77XX_CYAN : ST77XX_RED);
    lineText(7,94,"Upload phone recording");
    lineText(7,107,"using SAME code");
    lineText(7,119,"SEL: AGAIN BACK: MENU");
  } else { // NP_QUEUE_ERROR
    lineText(6,33,"Cannot start test",ST77XX_RED);
    lineText(6,51,"USB queue nearly full");
    lineText(6,69,"Go to Device Sync");
    lineText(6,87,"and sync saved events");
    lineText(6,106,"SELECT: RETRY");
    lineText(6,118,"BACK: MENU");
  }
}

void neuroStart() {
  // Reserve at least 2 NVS slots for STARTED and FINISHED messages.
  // The timer won't pretend data is captured if it cannot be queued.
  if (queuedCount() > QUEUE_LIMIT - 2) {
    neuroPhase = NP_QUEUE_ERROR;
    renderNeuroPen();
    return;
  }
  neuroAssessmentId = neuroNewId();
  neuroDurationMs = 0;
  neuroStartedAt = millis();
  neuroLastSecond = 0xFFFFFFFFUL;
  if (!neuroQueueEvent("NEUROPEN_STARTED")) {
    neuroPhase = NP_QUEUE_ERROR;
    renderNeuroPen();
    return;
  }
  neuroPhase = NP_RUNNING;
  shortFeedback();
  renderNeuroPen();
}

void neuroFinish() {
  if (neuroPhase != NP_RUNNING) return;
  neuroDurationMs = millis() - neuroStartedAt;
  neuroEventSaved = neuroQueueEvent("NEUROPEN_FINISHED", neuroDurationMs);
  neuroPhase = NP_DONE;
  shortFeedback();
  renderNeuroPen();
}

void neuroButton(int b) {
  if (b == 0) {  // BACK cancels running activity; otherwise returns to menu.
    if (neuroPhase == NP_RUNNING) {
      neuroDurationMs = millis() - neuroStartedAt;
      neuroQueueEvent("NEUROPEN_CANCELLED", neuroDurationMs);
    }
    neuroPhase = NP_READY;
    page = MAIN_MENU;
    renderMenu();
    return;
  }
  if (b != 3) return;  // SELECT is the only control within this test.
  if (neuroPhase == NP_RUNNING) neuroFinish();
  else neuroStart();  // Ready, done and queue-error can begin a fresh session.
}

void neuroTick() {
  if (page != NEUROPEN || neuroPhase != NP_RUNNING) return;
  uint32_t second = (millis() - neuroStartedAt) / 1000UL;
  if (second == neuroLastSecond) return;
  neuroLastSecond = second;
  // Update only the timer region so the display doesn't flicker every second.
  tft.fillRect(8, 78, 145, 17, BG);
  lineText(8,80,"Time: " + String(second) + " s",ST77XX_GREEN);
}
void renderPage() {
  switch (page) {
    case WELCOME:renderHome();break;
    case MAIN_MENU:renderMenu();break;
    case TIMMY:renderTimmy();break;
    case CONFIRMED:renderConfirmed();break;
    case MEMORY:renderMemory();break;
    case REACTION:renderReaction();break;
    case VOICE:renderVoice();break;
    case REMINDERS:renderReminders();break;
    case SYNC:renderSync();break;
    case NEUROPEN:renderNeuroPen();break;
    case REMINDER_ALERT:break;
  }
}
void saveMood() {
  prefs.putUChar("mood",(uint8_t)moodIndex);
  JsonDocument j;fillEvent(j,"MOOD_SELECTED","hw_timmy_mood");
  JsonObject p=j["payload"].to<JsonObject>();
  p["mood_code"]=moodIndex+1;p["mood_name"]=moods[moodIndex];
  queueEvent(j);shortFeedback();
}
void handleButton(int b) {
  if (page==MEMORY) {memoryButton(b);return;}
  if (page==REACTION) {reactionButton(b);return;}
  if (page==REMINDERS) {reminderButton(b);return;}
  if (page==REMINDER_ALERT) {reminderAlertButton(b);return;}
  if (page==WELCOME) {if (b==3) page=MAIN_MENU;}
  else if (page==MAIN_MENU) {
    if (b==0) page=WELCOME;
    else if (b==1) menuIndex=(menuIndex+6)%7;
    else if (b==2) menuIndex=(menuIndex+1)%7;
    else if (b==3) {
      switch(menuIndex) {
        case 0:page=TIMMY;break;
        case 1:page=MEMORY;memPhase=MEM_READY;break;
        case 2:page=REACTION;rtPhase=RT_READY;break;
        case 3:page=VOICE;break;
        case 4:page=REMINDERS;break;
        case 5:page=SYNC;break;
        case 6:page=NEUROPEN;neuroPhase=NP_READY;break;
      }
    }
  } else if (page==TIMMY) {
    if (b==0) page=MAIN_MENU;
    else if (b==1) moodIndex=(moodIndex+5)%6;
    else if (b==2) moodIndex=(moodIndex+1)%6;
    else if (b==3) {saveMood();page=CONFIRMED;}
  } else if (page==CONFIRMED) {
    if (b==0) page=MAIN_MENU;
    else if (b==3) page=TIMMY;
  } else if (page==VOICE) {
    if (b==0) page=MAIN_MENU;
  } else if (page==SYNC) {
    if (b==0) page=MAIN_MENU;
    else if (b==3) {sendHello();resendPending(true);}
  } else if (page==NEUROPEN) {
    neuroButton(b);
    return;  // The NeuroPen handler draws its own updated screen.
  }
  renderPage();
}
void faceTick() {
  if (page!=WELCOME && page!=TIMMY && page!=CONFIRMED) return;
  uint32_t now=millis();
  bool blink=(now%4200UL)>=4030UL;
  int glance=(int)((now/1950UL)%3UL)-1;
  if (blink!=previousBlink || glance!=previousGlance) {
    previousBlink=blink;previousGlance=glance;drawFace(blink,glance);
  }
}
void setup() {
  Serial.begin(115200);
  for (int i=0;i<4;++i) pinMode(pins[i],INPUT_PULLUP);
  pinMode(STATUS_LED,OUTPUT);digitalWrite(STATUS_LED,LOW);
#if ENABLE_BUZZER
  pinMode(BUZZER_PIN,OUTPUT);digitalWrite(BUZZER_PIN,LOW);
#endif
  SPI.begin(18,-1,23,TFT_CS);
  tft.initR(INITR_BLACKTAB);   // Try INITR_GREENTAB if your panel requires it.
  tft.setRotation(1);
  randomSeed(esp_random());
  prefs.begin("alvipocket",false);
  moodIndex=prefs.getUChar("mood",0);if (moodIndex>5) moodIndex=0;
  reminderEnabled=prefs.getBool("remOn",false);
  reminderMinutes=prefs.getUShort("remMin",30);
  if (reminderMinutes!=15 && reminderMinutes!=30 && reminderMinutes!=60 &&
      reminderMinutes!=120 && reminderMinutes!=240) reminderMinutes=30;
  reminderLast=millis();
  pairedSession=prefs.getString("session","");
  uint64_t mac=ESP.getEfuseMac();
  char id[26];snprintf(id,sizeof(id),"esp32-%04X%08X",(unsigned)((mac>>32)&0xFFFF),(unsigned)(mac&0xFFFFFFFF));
  deviceId=String(id);
  renderPage();
  sendHello();
}
void loop() {
  serialTick();
  if (voiceDirty) { if (page==VOICE) renderVoice(); voiceDirty=false; }
  int b=buttonEvent();
  if (b>=0) handleButton(b);
  memoryTick(); reactionTick(); neuroTick(); reminderTick(); faceTick(); feedbackTick();
  delay(3);
}
