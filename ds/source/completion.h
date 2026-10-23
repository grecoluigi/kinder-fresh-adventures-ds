#ifndef KINDER_COMPLETION_H
#define KINDER_COMPLETION_H
#include "highscore_ui.h"
/* Native402de4/403005 qualifies;403e18 confirms then reopens rankings.
 * Returns the insertion rank, or a negative value for the viewer alone. */
int completion_begin(HighscoreUI *ui,unsigned world,int32_t score);
/* Confirms the name and returns to the same world's viewer. RAM survives a
 * storage failure; result reports whether the selective FAT write succeeded. */
bool completion_confirm(HighscoreUI *ui);
#endif
