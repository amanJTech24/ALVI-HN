#pragma once
// reaction_game.h — Reaction Time Test
// Activity ID: "hw_reaction_test"
#include <Arduino.h>

#define REACTION_TRIALS   5
#define MIN_VALID_RT_MS   150

struct ReactionResult {
    char     session_id[32];
    uint16_t rt_ms[REACTION_TRIALS];
    uint8_t  trial_count;
    uint8_t  false_starts;
    uint8_t  missed;
    uint16_t median_rt_ms;
    uint32_t duration_ms;
    bool     completed;
};

void   reaction_game_init();
void   reaction_game_start(const char* session_id);
void   reaction_game_update();
bool   reaction_game_done();
const ReactionResult& reaction_game_result();
void   reaction_game_reset();
