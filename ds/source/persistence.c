#include "persistence.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

int32_t persistence_decimal(const char *text)
{
    uint32_t value = 0;
    bool negative = false;
    while (*text == ' ' || (*text >= '\t' && *text <= '\r')) ++text;
    if (*text == '-' || *text == '+') negative = *text++ == '-';
    while (*text >= '0' && *text <= '9') value = value * 10u + (unsigned)(*text++ - '0');
    if (negative) value = 0u - value;
    int32_t result;
    memcpy(&result, &value, sizeof(result));
    return result;
}

void persistence_defaults(PersistenceState *state, bool input_device_available)
{
    static const int32_t defaults[22] = {
        203,205,200,208,30,31,33,32,0,0,0,1,0,3,0,2,0,0,0,1,75,100
    };
    memset(state, 0, sizeof(*state));
    memcpy(state->options, defaults, sizeof(defaults));
    if (!input_device_available)
        for (unsigned i = 8; i < 20; ++i) state->options[i] = -1;
    for (unsigned w = 0; w < 4; ++w)
        for (unsigned i = 0; i < 10; ++i) {
            snprintf(state->scores[w].names[i], 30, "Player %u", i + 1);
            snprintf(state->scores[w].score_text[i], 10, "%u", (10 - i) * 1000);
        }
}

int persistence_rank(const HighscoreTable *table, int32_t score)
{
    for (unsigned i = 0; i < 10; ++i)
        if (persistence_decimal(table->score_text[i]) < score) return (int)i;
    return -1;
}

void persistence_normalize_options(int32_t options[22], bool input_device_available)
{
    if (!input_device_available) {
        for (unsigned i = 8; i < 20; ++i) options[i] = -1;
        return;
    }
    for (unsigned pair = 0; pair < 4; ++pair) {
        if (options[8 + pair * 2] == -1) options[8 + pair * 2] = 0;
        if (options[9 + pair * 2] == -1) options[9 + pair * 2] = (int32_t)pair;
    }
    for (unsigned i = 16; i < 19; ++i) if (options[i] == -1) options[i] = 0;
    if (options[19] == -1) options[19] = 1;
}

int persistence_qualify(HighscoreTable *table, int32_t score)
{
    char formatted[12];
    int length = snprintf(formatted, sizeof(formatted), "%" PRId32, score);
    if (length < 0 || length >= 10) return -2;
    int32_t values[10];
    for (unsigned i = 0; i < 10; ++i) {
        values[i] = persistence_decimal(table->score_text[i]);
        int n = snprintf(formatted, sizeof(formatted), "%" PRId32, values[i]);
        if (n < 0 || n >= 10) return -2;
    }
    int rank = persistence_rank(table, score);
    if (rank >= 0) {
        for (int i = 9; i > rank; --i) {
            memcpy(table->names[i], table->names[i-1], 30);
            values[i] = values[i-1];
        }
        memset(table->names[rank], 0, 30);
        values[rank] = score;
    }
    /* Original sorts even when the current score does not qualify. */
    for (unsigned pass = 0; pass < 10; ++pass)
        for (unsigned i = 0; i < 9; ++i)
            if (values[i] < values[i+1]) {
                int32_t temporary = values[i]; values[i] = values[i+1]; values[i+1] = temporary;
                char name[30]; memcpy(name, table->names[i], 30);
                memcpy(table->names[i], table->names[i+1], 30);
                memcpy(table->names[i+1], name, 30);
            }
    for (unsigned i = 0; i < 10; ++i) {
        int n = snprintf(formatted, sizeof(formatted), "%" PRId32, values[i]);
        if (n < 0 || n >= 10) return -2;
        memset(table->score_text[i], 0, 10);
        memcpy(table->score_text[i], formatted, (size_t)n);
    }
    return rank;
}

bool persistence_set_name(HighscoreTable *table, unsigned rank, const char *name)
{
    size_t length = strlen(name);
    if (rank >= 10 || length > 29 || strchr(name, '\r') || strchr(name, '\n')) return false;
    memset(table->names[rank], 0, 30);
    memcpy(table->names[rank], name, length);
    return true;
}

static bool read_line(const char **cursor, const char *end, char *output, size_t limit)
{
    const char *start = *cursor;
    const char *stop = start;
    if (start == end) return false;
    while (stop < end && *stop != '\n') ++stop;
    size_t size = (size_t)(stop - start);
    if (size && start[size-1] == '\r') --size;
    if (size >= limit || memchr(start, '\0', size)) return false;
    memcpy(output, start, size); output[size] = '\0';
    *cursor = stop < end ? stop + 1 : end;
    return true;
}

bool persistence_parse_highscores(HighscoreTable *table, const char *data, size_t size)
{
    HighscoreTable parsed;
    memset(&parsed, 0, sizeof(parsed));
    const char *cursor = data, *end = data + size;
    for (unsigned i = 0; i < 10; ++i)
        if (!read_line(&cursor, end, parsed.names[i], 30) ||
            !read_line(&cursor, end, parsed.score_text[i], 9)) return false;
    *table = parsed;
    return true;
}

static bool append(char **cursor, char *end, const char *text)
{
    size_t length = strlen(text);
    if ((size_t)(end - *cursor) < length) return false;
    memcpy(*cursor, text, length); *cursor += length;
    return true;
}

size_t persistence_write_highscores(const HighscoreTable *table, char *data, size_t capacity)
{
    char *cursor = data, *end = data + capacity;
    for (unsigned i = 0; i < 10; ++i) {
        if (!memchr(table->names[i], '\0', 30) || !memchr(table->score_text[i], '\0', 10)) return 0;
        if (!append(&cursor, end, table->names[i]) || !append(&cursor, end, "\r\n") ||
            !append(&cursor, end, table->score_text[i]) ||
            (i != 9 && !append(&cursor, end, "\r\n"))) return 0;
    }
    return (size_t)(cursor - data);
}

bool persistence_parse_options(int32_t options[22], const char *data, size_t size)
{
    int32_t parsed[22];
    const char *cursor = data, *end = data + size;
    char line[99];
    for (unsigned i = 0; i < 22; ++i) {
        if (!read_line(&cursor, end, line, sizeof(line))) return false;
        parsed[i] = persistence_decimal(line);
        if (i >= 16 && i < 20) {
            uint16_t bits = (uint16_t)parsed[i]; int16_t value;
            memcpy(&value, &bits, sizeof(value)); parsed[i] = value;
        }
    }
    memcpy(options, parsed, sizeof(parsed));
    return true;
}

size_t persistence_write_options(const int32_t options[22], char *data, size_t capacity)
{
    char *cursor = data, *end = data + capacity;
    for (unsigned i = 0; i < 22; ++i) {
        int32_t value = options[i];
        if (i >= 16 && i < 20) {
            uint16_t bits = (uint16_t)value; int16_t short_value;
            memcpy(&short_value, &bits, sizeof(short_value)); value = short_value;
        }
        char line[12]; snprintf(line, sizeof(line), "%" PRId32, value);
        if (!append(&cursor, end, line) || (i != 21 && !append(&cursor, end, "\r\n"))) return 0;
    }
    return (size_t)(cursor - data);
}

void persistence_parse_tutorials(uint8_t flags[4], const uint8_t *data, size_t size)
{
    memset(flags, 0, 4);
    memcpy(flags, data, size < 4 ? size : 4);
}
