#pragma once
// ============================================================
// memory_game.h — 4-Color Memory Sequence Game
// Activity ID: "hw_memory_seq" (separate from MindPlay ch1/ch2/ch3)
// ============================================================
#include <Arduino.h>

struct MemoryResult {
    char     session_id[32];
    uint8_t  max_level;
    uint8_t  correct_count;
    uint8_t  error_count;
    uint32_t duration_ms;
    uint8_t  sequence_shown[20];   // up to 20 steps shown
    uint8_t  user_responses[20];
    uint8_t  seq_len;
    bool     completed;
};

void   memory_game_init();
void   memory_game_start(const char* session_id);
void   memory_game_update();     // call each loop — state machine
bool   memory_game_done();       // true when session complete
const MemoryResult& memory_game_result();
void   memory_game_reset();

