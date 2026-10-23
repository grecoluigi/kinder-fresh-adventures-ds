#ifndef KINDER_MENU_H
#define KINDER_MENU_H
#include <stdbool.h>
typedef enum {
    MENU_SELECTION_NONE = -1,
    MENU_SELECTION_JUNGLE = 0,
    MENU_SELECTION_VALLEY,
    MENU_SELECTION_MOUNTAIN,
    MENU_SELECTION_FACTORY,
    MENU_SELECTION_HIGHSCORES,
    MENU_SELECTION_EXIT
} MenuSelection;
/* Returns selected original menu action once, then resets to NONE.
 * Main dispatches world/highscore/exit callbacks. */
MenuSelection menu_take_selection(void);
void menu_init(void);
void menu_move(int direction);
void menu_focus(int index);
void menu_activate(void);
int menu_focus_index(void);
int menu_hit_test(int x, int y);
#endif
