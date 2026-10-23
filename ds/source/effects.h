#ifndef KINDER_EFFECTS_H
#define KINDER_EFFECTS_H
/* Released original430470 is one RET instruction. Its direct particle calls
 * consume RNG in the caller but do not mutate state or render any effect. */
void effects_particle(void *context,int x,int y,float vx,float vy);
#endif
