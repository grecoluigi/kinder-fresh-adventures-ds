#include "menu.h"
#include "menu_hitboxes.h"
static int focus = MENU_SELECTION_JUNGLE;
static MenuSelection selection = MENU_SELECTION_NONE;
void menu_init(void) { focus = MENU_SELECTION_JUNGLE; selection = MENU_SELECTION_NONE; }
void menu_move(int direction) {
    if (focus < 0) focus = direction < 0 ? 5 : 0;
    else focus = (focus + (direction < 0 ? 5 : 1)) % 6;
}
void menu_focus(int index) { if (index >= 0 && index < 6) focus = index; }
int menu_focus_index(void) { return focus; }
void menu_activate(void) {
    if (focus >= 0) selection = (MenuSelection)focus;
}
MenuSelection menu_take_selection(void) {
    MenuSelection result = selection;
    selection = MENU_SELECTION_NONE;
    return result;
}
int menu_hit_test(int x, int y) {
    for (int i = 0; i < 6; ++i) {
        const int *b = menu_hitboxes[i];
        if (x >= b[0] && x < b[2] && y >= b[1] && y < b[3]) return i;
    }
    return -1;
}
