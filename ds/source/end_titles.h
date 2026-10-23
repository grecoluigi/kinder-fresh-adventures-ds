#ifndef KINDER_END_TITLES_H
#define KINDER_END_TITLES_H
#include <stdbool.h>
#include <stdint.h>
typedef struct {int32_t action,frame;float x,y,vy;} EndTitle;
/* Native4111e5..41135b. Advance once per original60Hz simulation tick. */
void end_title_tick(EndTitle *title);
bool end_title_draw(const EndTitle *title,uint16_t *pixels);
void end_title_close(void);
#endif
