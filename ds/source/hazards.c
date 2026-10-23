#include "hazards.h"
static void hurt_sound(Player *p,const PlayerEnvironment *e)
{
    if(e->event)e->event(e->context,PLAYER_SOUND_PLAY,
                       p->character?p->milk_hurt_sound:p->penguin_hurt_sound,
                       p->character?1:0);
}
static void set_immunity(Player *p)
{
    if(p->character) {p->milk.opaque_5c=120;p->milk_status=120;}
    else p->penguin.opaque_5c=120;
}
static bool immune(const Player *p)
{ return (p->character?p->milk.opaque_5c:p->penguin.opaque_5c)!=0; }
void player_tile_hazard(Player *p,GameBody *b,bool present,uint8_t flags,uint16_t packed,const PlayerEnvironment *e)
{
    if(p->health==0||!present||packed==0xffff||!(flags&0x80))return;
    hurt_sound(p,e);
    if(!immune(p)) {
        p->hit_feet=20;set_immunity(p);p->health-=20;
        if(p->health<0) {p->health=0;return;}
    }
    if(p->health!=0&&(uint32_t)b->kind<=1)b->motion.vy=-0x14000;
}
bool player_rect_hazard(Player *p,const GameBody *b,int x,int y,int width,int height,int damage,const PlayerEnvironment *e)
{
    int px=(uint32_t)b->kind<=1?b->motion.x/4096:0;
    int py=(uint32_t)b->kind<=1?b->motion.y/4096:0;
    int frame=p->character?p->milk.frame:p->penguin.frame;
    int player_height=frame==(p->character?266:143)?100:190;
    if(x>=px+40||x+width<=px-40||y>=py||y+height<=py-player_height)return false;
    if(damage==0)return true;
    if(p->health==0||immune(p))return false;
    int middle=y+height/2;
    if(middle>=py-50&&middle<py)p->hit_feet=5;
    if(middle>=py-125&&middle<py-50)p->hit_middle=5;
    if(middle<py-125)p->hit_head=5;
    hurt_sound(p,e);p->health-=damage;
    if(p->health<=0)p->health=0;else set_immunity(p);
    return true;
}
