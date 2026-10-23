#include <assert.h>
#include "menu.h"
int main(void) {
    menu_init();
    assert(menu_focus_index() == -1);
    menu_activate();
    assert(menu_take_selection() == MENU_SELECTION_NONE);
    menu_move(1);
    assert(menu_focus_index() == MENU_SELECTION_JUNGLE);
    menu_move(-1);
    assert(menu_focus_index() == MENU_SELECTION_EXIT);
    menu_activate();
    assert(menu_take_selection() == MENU_SELECTION_EXIT);
    assert(menu_take_selection() == MENU_SELECTION_NONE);
    for (int i = 0; i < 6; ++i) {
        menu_focus(i); menu_activate();
        assert(menu_take_selection() == (MenuSelection)i);
    }
    assert(menu_hit_test(20, 40) == MENU_SELECTION_JUNGLE);
    assert(menu_hit_test(10, 80) == MENU_SELECTION_VALLEY);
    assert(menu_hit_test(15, 125) == MENU_SELECTION_MOUNTAIN);
    assert(menu_hit_test(25, 165) == MENU_SELECTION_FACTORY);
    assert(menu_hit_test(180, 180) == MENU_SELECTION_HIGHSCORES);
    assert(menu_hit_test(235, 180) == MENU_SELECTION_EXIT);
    assert(menu_hit_test(100, 100) == -1);
    assert(menu_hit_test(255, 191) == -1);
}
