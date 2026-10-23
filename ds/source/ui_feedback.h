#ifndef KINDER_UI_FEEDBACK_H
#define KINDER_UI_FEEDBACK_H
#include <stdbool.h>
#include <stdint.h>
typedef struct {int focus[2];uint8_t latched[2];} UIFeedback;
typedef void (*UIFeedbackPlay)(unsigned channel,unsigned key,unsigned repeat,int attenuation,void *context);
void ui_feedback_init(UIFeedback *state);
void ui_feedback_reset(UIFeedback *state,bool scores);
/* Focus order is jungle,valley,mountain,factory,then non-world actions.
 * Original40473f and403263 gates differ when sound percentage is zero. */
void ui_feedback_tick(UIFeedback *state,bool scores,int focus,int percentage,UIFeedbackPlay play,void *context);
/* Original4099f2..409a17; original UI percentage domain0..100. */
int ui_feedback_attenuation(int percentage);
/* Menu BGM only. Original normal-world/boss loaders set their own volumes. */
unsigned ui_feedback_music_volume(int percentage);
#endif
