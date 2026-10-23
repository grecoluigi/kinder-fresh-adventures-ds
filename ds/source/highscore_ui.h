#ifndef KINDER_HIGHSCORE_UI_H
#define KINDER_HIGHSCORE_UI_H
#include <stdbool.h>
#include <stdint.h>
#include "persistence.h"
typedef struct {
    unsigned world;
    int focus;
    int editing_rank;
    int held_key;
    char name[30];
    unsigned name_length;
    bool exit_requested;
    bool commit_requested;
    uint32_t revision;
} HighscoreUI;
/* Font cache is approximately14KiB. Backgrounds stream directly into caller's
 * framebuffer on redraw. Close when leaving to return this memory to gameplay. */
bool highscore_ui_open(const char *asset_directory);
void highscore_ui_close(void);
void highscore_ui_init(HighscoreUI *ui, unsigned native_world);
bool highscore_ui_begin_name(HighscoreUI *ui, unsigned native_world, int rank);
void highscore_ui_move(HighscoreUI *ui, int direction);
void highscore_ui_focus(HighscoreUI *ui, int focus);
void highscore_ui_activate(HighscoreUI *ui);
void highscore_ui_back(HighscoreUI *ui);
int highscore_ui_hit_test(int x, int y);
bool highscore_ui_touch(HighscoreUI *ui, int x, int y);
/* Text input follows the original glyph alphabet,28-byte cursor limit and
 *175-source-pixel name field. Native PC scan-code conversion is also exposed. */
/* Native409597 replaces the cursor with a space at length/width limit. */
bool highscore_ui_input_limit(const HighscoreUI *ui);
bool highscore_ui_text(HighscoreUI *ui, uint8_t character);
bool highscore_ui_backspace(HighscoreUI *ui);
bool highscore_ui_key(HighscoreUI *ui, unsigned scan_code, bool down, bool shift, bool caps_lock);
/* Original confirmation turns the cursor underscore into a trailing space. */
bool highscore_ui_commit_name(HighscoreUI *ui, HighscoreTable *table);
/* Table contains the selected native world's ten ranks. Output256x192 RGB555.
 * Draw only on changes; unchanged output is skipped when pointer also matches. */
bool highscore_ui_draw(uint16_t *pixels, const HighscoreTable *table, const HighscoreUI *ui);
/* Portable original font command layout, useful for native command verification. */
typedef void (*HighscoreGlyphCommand)(void *context, int frame, int x, int y);
void highscore_ui_text_commands(const char *text, int x, int y, HighscoreGlyphCommand callback, void *context);
void highscore_ui_row_commands(const HighscoreTable *table, const HighscoreUI *ui, HighscoreGlyphCommand callback, void *context);
#endif
