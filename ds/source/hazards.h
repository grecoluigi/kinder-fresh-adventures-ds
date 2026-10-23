#ifndef KINDER_HAZARDS_H
#define KINDER_HAZARDS_H
#include "player.h"
/* Original41a290: caller supplies the layer2 cell at the original, truncated
 * body foot coordinates. Use raw flags/packed tile, not tile draw queries. */
void player_tile_hazard(Player *player,GameBody *body,bool present,
                        uint8_t flags,uint16_t packed,const PlayerEnvironment *environment);
/* Original41a3e0 rectangle contact. A zero-damage query returns overlap only.
 * Positive damage preserves native immunity, effects and sound ordering. */
bool player_rect_hazard(Player *player,const GameBody *body,int x,int y,int width,int height,
                       int damage,const PlayerEnvironment *environment);
#endif
