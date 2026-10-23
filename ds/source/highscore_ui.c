#include "highscore_ui.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "highscore_assets.h"

typedef struct { uint32_t offset; uint16_t width, height; } FontFrame;
static FontFrame frames[55];
static uint16_t *font_pixels;
static char asset_path[384];
static uint16_t *previous_pixels;
static uint32_t previous_hash;

void highscore_ui_close(void)
{
    free(font_pixels); font_pixels = NULL; previous_pixels = NULL;
}

bool highscore_ui_open(const char *asset_directory)
{
    highscore_ui_close();
    if (!asset_directory) asset_directory = "nitro:/highscores";
    int n = snprintf(asset_path, sizeof(asset_path), "%s", asset_directory);
    if (n < 0 || (size_t)n >= sizeof(asset_path)) return false;
    char path[416];
    n = snprintf(path, sizeof(path), "%s/font.bin", asset_path);
    if (n < 0 || (size_t)n >= sizeof(path)) return false;
    FILE *stream = fopen(path, "rb"); if (!stream) return false;
    char magic[4]; uint32_t counts[2];
    bool okay = fread(magic, 1, 4, stream) == 4 && memcmp(magic, "KHS1", 4) == 0 &&
        fread(counts, 4, 2, stream) == 2 && counts[0] == 55 && counts[1] <= 16000;
    if (okay) okay = fread(frames, sizeof(frames[0]), 55, stream) == 55;
    if (okay) {
        font_pixels = malloc(counts[1] * 2);
        okay = font_pixels && fread(font_pixels, 2, counts[1], stream) == counts[1];
    }
    if (okay)
        for (unsigned i = 0; i < 55; ++i)
            if ((uint64_t)frames[i].offset + (uint64_t)frames[i].width * frames[i].height > counts[1]) okay = false;
    if (fclose(stream) != 0) okay = false;
    if (!okay) highscore_ui_close();
    return okay;
}

void highscore_ui_init(HighscoreUI *ui, unsigned native_world)
{
    memset(ui, 0, sizeof(*ui)); ui->world = native_world & 3;
    ui->focus = -1; ui->editing_rank = -1; ui->held_key = -1; ui->revision = 1;
}

bool highscore_ui_begin_name(HighscoreUI *ui, unsigned native_world, int rank)
{
    if (rank < 0 || rank >= 10) return false;
    highscore_ui_init(ui, native_world); ui->editing_rank = rank;
    return true;
}

void highscore_ui_focus(HighscoreUI *ui, int focus)
{
    if (focus < -1 || focus >= 5 || focus == ui->focus) return;
    if (ui->editing_rank >= 0 && focus != 4) return;
    ui->focus = focus; ++ui->revision;
}

void highscore_ui_move(HighscoreUI *ui, int direction)
{
    if (ui->editing_rank >= 0) { highscore_ui_focus(ui, 4); return; }
    int next = ui->focus < 0 ? (direction < 0 ? 4 : 0) : (ui->focus + (direction < 0 ? 4 : 1)) % 5;
    highscore_ui_focus(ui, next);
}

void highscore_ui_back(HighscoreUI *ui)
{
    ui->exit_requested = true; ui->commit_requested = ui->editing_rank >= 0; ++ui->revision;
}

void highscore_ui_activate(HighscoreUI *ui)
{
    static const unsigned world_for_focus[4] = {0,3,1,2};
    if (ui->editing_rank >= 0 || ui->focus == 4) highscore_ui_back(ui);
    else if (ui->focus >= 0 && ui->focus < 4) {
        ui->world = world_for_focus[ui->focus]; ++ui->revision;
    }
}

int highscore_ui_hit_test(int x, int y)
{
    if (x < 0 || y < 0 || x >= 256 || y >= 192) return -1;
    int sx = ((2*x+1)*25)/16, sy = ((2*y+1)*25)/16;
    for (unsigned i = 0; i < 5; ++i) {
        const int16_t *bounds = highscore_hitboxes[i];
        if (sx >= bounds[0] && sy >= bounds[1] && sx < bounds[2] && sy < bounds[3]) return (int)i;
    }
    return -1;
}

bool highscore_ui_touch(HighscoreUI *ui, int x, int y)
{
    int focus = highscore_ui_hit_test(x, y);
    if (focus < 0 || (ui->editing_rank >= 0 && focus != 4)) return false;
    highscore_ui_focus(ui, focus); highscore_ui_activate(ui); return true;
}

static unsigned name_width(const HighscoreUI *ui)
{
    unsigned width = highscore_glyphs[(unsigned char)'_'].advance;
    for (unsigned i = 0; i < ui->name_length; ++i) width += highscore_glyphs[(unsigned char)ui->name[i]].advance;
    return width;
}

bool highscore_ui_input_limit(const HighscoreUI *ui)
{
    return ui->editing_rank>=0 && (ui->name_length>=28 || name_width(ui)>=175);
}

bool highscore_ui_text(HighscoreUI *ui, uint8_t character)
{
    if (ui->editing_rank < 0 || ui->name_length >= 28 || name_width(ui) >= 175) return false;
    bool allowed = false;
    for (unsigned shift = 0; shift < 2; ++shift)
        for (unsigned key = 0; key < 87; ++key)
            if (highscore_scancode_chars[shift][key] == character && character != 0) allowed = true;
    if (!allowed) return false;
    ui->name[ui->name_length++] = (char)character;
    ui->name[ui->name_length] = '\0'; ++ui->revision; return true;
}

bool highscore_ui_backspace(HighscoreUI *ui)
{
    if (ui->editing_rank < 0 || !ui->name_length) return false;
    ui->name[--ui->name_length] = '\0'; ++ui->revision; return true;
}

bool highscore_ui_key(HighscoreUI *ui, unsigned scan_code, bool down, bool shift, bool caps_lock)
{
    if (scan_code > 255 || ui->editing_rank < 0) return false;
    if (!down) { if (ui->held_key == (int)scan_code) ui->held_key = -1; return false; }
    if (ui->held_key >= 0 || scan_code == 42 || scan_code == 54) return false;
    ui->held_key = (int)scan_code;
    if (scan_code == 14) return highscore_ui_backspace(ui);
    if (scan_code == 28) { highscore_ui_back(ui); return true; }
    uint8_t character = scan_code == 181 ? '/' : (scan_code < 87 ? highscore_scancode_chars[shift != caps_lock][scan_code] : 0);
    return highscore_ui_text(ui, character);
}

bool highscore_ui_commit_name(HighscoreUI *ui, HighscoreTable *table)
{
    if (!ui->commit_requested || ui->editing_rank < 0) return false;
    char name[30]; memcpy(name, ui->name, ui->name_length);
    name[ui->name_length] = ' '; name[ui->name_length+1] = '\0';
    if (ui->name_length + 1 > 29) return false;
    if (!persistence_set_name(table, (unsigned)ui->editing_rank, name)) return false;
    ui->commit_requested = false; ui->editing_rank = -1; ++ui->revision; return true;
}

void highscore_ui_text_commands(const char *text, int x, int y, HighscoreGlyphCommand callback, void *context)
{
    for (const unsigned char *cursor = (const unsigned char *)text; *cursor; ++cursor) {
        const HighscoreGlyph *glyph = &highscore_glyphs[*cursor];
        if (glyph->frame >= 0 && glyph->frame < 55 && callback) callback(context, glyph->frame, x, y + glyph->dy);
        x += glyph->advance;
    }
}

void highscore_ui_row_commands(const HighscoreTable *table, const HighscoreUI *ui, HighscoreGlyphCommand callback, void *context)
{
    for (unsigned i = 0; i < 10; ++i) {
        char rank[4], editing[30]; snprintf(rank, sizeof(rank), "%u", i+1);
        const char *name = table->names[i];
        if (ui && ui->editing_rank == (int)i) {
            memcpy(editing, ui->name, ui->name_length); editing[ui->name_length] = '_'; editing[ui->name_length+1] = '\0'; name = editing;
        }
        int y = 128 + 32*(int)i;
        highscore_ui_text_commands(rank, 180, y, callback, context);
        highscore_ui_text_commands(name, 230, y, callback, context);
        highscore_ui_text_commands(table->score_text[i], 490 - 13*(int)strlen(table->score_text[i]), y, callback, context);
    }
}

static void draw_glyph(void *context, int frame, int x, int y)
{
    uint16_t *pixels = context; const FontFrame *glyph = &frames[frame];
    for (int dy = 0; dy < 192; ++dy) {
        int sy = ((2*dy+1)*25)/16 - y;
        if (sy < 0 || sy >= glyph->height) continue;
        for (int dx = 0; dx < 256; ++dx) {
            int sx = ((2*dx+1)*25)/16 - x;
            if (sx < 0 || sx >= glyph->width) continue;
            uint16_t value = font_pixels[glyph->offset + sy*glyph->width + sx];
            if (value) pixels[dy*256+dx] = value;
        }
    }
}

bool highscore_ui_draw(uint16_t *pixels, const HighscoreTable *table, const HighscoreUI *ui)
{
    if (!font_pixels || !pixels || !table || !ui || ui->world >= 4) return false;
    uint32_t hash = 2166136261u;
    const unsigned char *bytes = (const unsigned char *)table;
    for (unsigned i = 0; i < sizeof(*table); ++i) hash = (hash ^ bytes[i]) * 16777619u;
    hash = (hash ^ ui->revision) * 16777619u;
    hash = (hash ^ ui->world) * 16777619u;
    hash = (hash ^ (unsigned)(ui->focus+1)) * 16777619u;
    hash = (hash ^ (unsigned)(ui->editing_rank+1)) * 16777619u;
    for(unsigned i=0;i<ui->name_length;++i)
        hash=(hash^(unsigned char)ui->name[i])*16777619u;
    if (previous_pixels == pixels && previous_hash == hash) return true;
    char path[416]; int n = snprintf(path, sizeof(path), "%s/world%u_focus%d.bin", asset_path, ui->world, ui->focus+1);
    if (n < 0 || (size_t)n >= sizeof(path)) return false;
    FILE *stream = fopen(path, "rb"); if (!stream) return false;
    bool okay = fread(pixels, 2, 256*192, stream) == 256*192;
    if (fclose(stream) != 0) okay = false;
    if (!okay) return false;
    highscore_ui_row_commands(table, ui, draw_glyph, pixels);
    previous_pixels = pixels; previous_hash = hash; return true;
}
