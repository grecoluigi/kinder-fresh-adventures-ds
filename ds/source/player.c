#include "player.h"

static void event(const PlayerEnvironment *e, PlayerEventType type, int id, int arg)
{ if (e->event) e->event(e->context,type,id,arg); }
static void range(Animation *a,int frame,int first,int last,int repeats)
{ a->frame=frame;a->first=first;a->last=last;a->repeats=repeats; }
static void horizontal(Player *p,GameBody *b,unsigned input)
{
    if (input&PLAYER_LEFT) {b->motion.ax=-0x1333;p->facing=1;}
    else if(input&PLAYER_RIGHT) {b->motion.ax=0x1333;p->facing=0;}
    else b->motion.ax=0;
}
static bool unsupported(Player *p,const PlayerEnvironment *e,int reason)
{ event(e,PLAYER_UNSUPPORTED,p->state,reason);return false; }

bool player_ladder_at(const PlayerEnvironment *e,int x,int y)
{
    if(!e->climb_probe||x<0||y<160)return false;
    if(e->climb_probe(e->context,PLAYER_PROBE_TILE_PROPERTY,x,y)&1)return true;
    if(e->climb_probe(e->context,PLAYER_PROBE_TILE_PROPERTY,x,y-10)&1)return true;
    return y!=160&&(e->climb_probe(e->context,PLAYER_PROBE_TILE_PROPERTY,x,y-160)&1);
}

void player_death_tick(Player *p)
{
    if(p->health<=0&&p->death_timer<0) {
        p->knockback_timer=30;p->death_actor=1;
        p->state=p->character?36:34;p->death_timer=240;
    } else if(p->death_timer==0) {p->game_mode=2;return;}
    if(p->death_timer>0)--p->death_timer;
}

bool player_blink_tick(Player *p)
{
    Animation *a=p->character?&p->milk:&p->penguin;
    if(a->opaque_5c!=0) {a->opaque_58^=1u;--a->opaque_5c;}
    if(p->character)p->milk_status=(int32_t)a->opaque_5c;
    return a->opaque_5c==0||a->opaque_58!=0;
}

bool player_blink_present(PlayerBlinkView *view,const Player *p,bool native_visible,bool advanced)
{
    uint32_t remaining=(p->character?p->milk:p->penguin).opaque_5c;
    if(!remaining){view->active=false;view->visible=true;}
    else if(!view->active||view->character!=p->character||remaining>view->remaining){
        view->active=true;view->visible=native_visible;
    }else if(advanced){
        /* One native decrement per display preserves the original phase.
         * Catch-up displays toggle once, preventing even-step phase aliasing. */
        view->visible=view->remaining-remaining==1?native_visible:!view->visible;
    }
    view->remaining=remaining;view->character=p->character;return view->visible;
}

/* 4186dc / 419a2a. The original probes up to three pixels per direction,
 * in up/down/left/right order, and moves only while the ladder continues. */
static bool climb(Player *p,GameBody *b,unsigned *input,const PlayerEnvironment *e,bool milk)
{
    if(!e->climb_probe)return unsupported(p,e,4);
    Animation *a=milk?&p->milk:&p->penguin;
    unsigned keys=*input;int x=b->motion.x/4096,y=b->motion.y/4096;
    bool leaving=false,moved=false;
    b->motion.vx=b->motion.vy=0;b->motion.ax=0;b->motion.ay=-b->motion.gravity;
    if(keys&PLAYER_UP) {
        int n=1,head=y-191;
        for(;n<=3;++n,--head) {
            if(!e->climb_probe(e->context,PLAYER_PROBE_LADDER,x,head+190)) {leaving=true;break;}
            if(x>=0&&head>=0&&e->climb_probe(e->context,PLAYER_PROBE_TILE_SOLID,x,head)>0&&
               !(e->climb_probe(e->context,PLAYER_PROBE_TILE_PROPERTY,x,head)&3))break;
        }
        if(n!=1)moved=true;
        y+=1-n;
    }
    if(keys&PLAYER_DOWN) {
        int n=1;
        for(;n<=3;++n) {
            if(!e->climb_probe(e->context,PLAYER_PROBE_LADDER,x,y+n))break;
            if(e->climb_probe(e->context,PLAYER_PROBE_TILE_SOLID,x,y+n-1)>0&&
               !(e->climb_probe(e->context,PLAYER_PROBE_TILE_PROPERTY,x,y+n-1)&1)) {leaving=true;break;}
        }
        if(n!=1)moved=true;
        y+=n-1;
    }
    if(keys&PLAYER_LEFT) {
        int n=1;p->facing=1;
        for(;n<=3;++n)if(!e->climb_probe(e->context,PLAYER_PROBE_LADDER,x-n,y))break;
        if(n!=1)moved=true;
        x+=1-n;
    }
    if(keys&PLAYER_RIGHT) {
        int n=1;p->facing=0;
        for(;n<=3;++n)if(!e->climb_probe(e->context,PLAYER_PROBE_LADDER,x+n,y))break;
        if(n!=1)moved=true;
        x+=n-1;
    }
    a->delay=moved?1:-1;b->slope_limit_fixed=0x2000;
    b->motion.x=x*4096;b->motion.y=y*4096;
    if(leaving&&e->climb_probe(e->context,PLAYER_PROBE_CONTACT,x,y)) {
        b->motion.ay=0;p->state=milk?16:0;*input&=~3u;a->delay=1;p->vertical_latch=1;
    }
    if(keys&PLAYER_JUMP) {
        if(keys&PLAYER_LEFT) {b->motion.vx=-0x5000;p->facing=1;}
        if(keys&PLAYER_RIGHT) {b->motion.vx=0x5000;p->facing=0;}
        b->motion.ay=0;a->delay=1;p->vertical_latch=1;*input&=~3u;p->state=milk?20:4;
    }
    if(!e->climb_probe(e->context,PLAYER_PROBE_LADDER,b->motion.x/4096,b->motion.y/4096)) {
        b->motion.ay=0;a->delay=1;p->state=milk?16:0;
    }
    return true;
}

static void voice(const PlayerEnvironment *e,int path)
{
    event(e,PLAYER_SOUND_LOAD,path,17);
    if(e->sound_load_ok)event(e,PLAYER_SOUND_VOLUME,17,0);
}
/* Ambient and switch voices use the same original channel 17. Randomness is
 * supplied by the caller, preserving the number/order of native rand calls. */
static bool idle(Player *p,unsigned *input,const PlayerEnvironment *e,bool milk)
{
    Animation *a=milk?&p->milk:&p->penguin;
    if(!e->grounded) {
        p->penguin_status=0;p->state=milk?22:6;
        event(e,PLAYER_SOUND_STOP,17,0);return true;
    }
    if(p->fatal) {p->state=milk?40:38;return true;}
    /* No mutations if a missing random callback would be required. */
    if((int32_t)a->opaque_44==0 || (a->opaque_40==0&&a->opaque_44==1)) {
        if(e->world_stage<4&&!e->random)return unsupported(p,e,2);
    }
    if(!milk) {
        if(a->opaque_40==2&&a->frame==a->last&&a->timer==0) {
            a->opaque_40=0;a->frame=a->first=a->last=47;
        } else if(a->opaque_40==1&&!e->voice_active) {
            a->opaque_40=0;
            if(!p->penguin_status)a->frame=a->first=a->last=47;
            else p->penguin_status=2;
        } else if(a->opaque_40==0&&a->opaque_44!=0)--a->opaque_44;
        if(a->opaque_44==0) {
            a->opaque_44=240;
            int choice=e->world_stage<4?e->random(e->context)%3:2;
            if(choice==0) {a->opaque_40=0;a->frame=a->first=a->last=47;}
            else if(choice==1) {
                a->opaque_40=1;
                int v=e->random(e->context)%2;
                if(v==0)voice(e,0x456bc0);else if(v==1)voice(e,0x456be4);
                a->frame=a->first=65;a->last=69;
            } else if(choice==2) {
                voice(e,0x456c08);a->opaque_40=2;
                a->frame=a->first=91;a->last=115;
            }
        }
    } else {
        if(a->opaque_40==2) {
            if(a->frame==146)a->first=146;
            if(a->frame==a->last&&a->timer==0&&!e->voice_active)a->last=159;
            if(a->frame==159&&a->timer==0) {
                a->opaque_40=0;
                if(!p->penguin_status)a->frame=a->first=a->last=0;
                else p->penguin_status=2;
            }
        } else if(a->opaque_40==1&&a->frame==a->last&&a->timer==0) {
            if(a->opaque_48!=0)--a->opaque_48;
            else {a->opaque_40=0;a->frame=a->first=a->last=0;}
        } else if(a->opaque_40==0&&a->opaque_44!=0)--a->opaque_44;
        if(a->opaque_44==0&&e->world_stage<4) {
            a->opaque_44=240;
            int choice=e->random(e->context)%3;
            if(choice==0) {a->opaque_40=0;a->frame=a->first=a->last=0;}
            else if(choice==1||choice==2) {
                a->opaque_40=2;a->frame=a->first=137;a->last=150;
                int v=e->random(e->context)%2;
                if(v==0)voice(e,0x456b54);else if(v==1)voice(e,0x456b78);
            }
        }
    }
    if(p->penguin_status==1)return true;
    if(p->penguin_status==2) {
        *input&=~PLAYER_SWITCH;p->penguin_status=0;p->puff_frame=0;
        p->switch_latch=1;p->character=milk?0:1;p->switch_available=milk?0:1;
        if(milk)p->penguin.opaque_5c=p->milk.opaque_5c;
        else {p->milk.opaque_5c=p->penguin.opaque_5c;p->milk_status=(int32_t)p->milk.opaque_5c;}
        p->state=milk?0:16;return true;
    }
    unsigned keys=*input;
    if(keys&PLAYER_SWITCH) {
        a->opaque_40=milk?2:1;a->opaque_44=1;
        voice(e,milk?0x456b30:0x456b9c);
        a->frame=a->first=milk?137:65;a->last=milk?150:69;
        p->penguin_status=1;return true;
    }
    if(e->ladder&&(keys&3)) {
        event(e,PLAYER_SOUND_STOP,17,0);p->state=milk?28:12;return true;
    }
    if((keys&PLAYER_SHOOT)&&p->inventory!=0) {
        --p->inventory;p->shoot_latch=1;p->state=milk?30:14;
        event(e,PLAYER_SOUND_STOP,17,0);
    }
    if(keys&PLAYER_JUMP) {p->state=milk?20:4;event(e,PLAYER_SOUND_STOP,17,0);}
    else if(keys&12) {p->state=milk?18:2;event(e,PLAYER_SOUND_STOP,17,0);}
    if(keys&PLAYER_DOWN) {p->state=milk?24:8;event(e,PLAYER_SOUND_STOP,17,0);}
    return true;
}

unsigned player_filter_input(Player *p,GameBody *b,unsigned keys,bool enabled)
{
    if(!(keys&128u))p->jump_release=0;
    if(!(keys&PLAYER_SWITCH))p->switch_latch=0;
    if(!(keys&PLAYER_SHOOT))p->shoot_latch=0;
    if(!(keys&3))p->vertical_latch=0;
    if(!(keys&12))p->direction_latch=0;
    if(p->jump_release)keys&=~128u;
    if(p->switch_latch)keys&=~PLAYER_SWITCH;
    if(p->shoot_latch)keys&=~PLAYER_SHOOT;
    if(p->vertical_latch)keys&=~3u;
    if(p->direction_latch)keys&=~12u;
    if(!(keys&PLAYER_JUMP))p->jump_debounce=-5;
    else if(p->jump_debounce>=0)keys&=~PLAYER_JUMP;
    else ++p->jump_debounce;
    if(!enabled) {b->motion.ax=b->motion.ay=0;keys=0;}
    return keys;
}

bool player_case(Player *p,GameBody *b,unsigned *input,int32_t *vy,const PlayerEnvironment *e)
{
    unsigned keys=*input;
    Animation *a=p->state>=16&&p->state<=33?&p->milk:&p->penguin;
    switch(p->state) {
    case -1:case 26:case 27: /* Native417835 and no-op jump-table entries. */
        break;
    case 34: /* 41795d */
    case 36: /* 418b2a */
        a=p->state==36?&p->milk:&p->penguin;
        range(a,p->state==36?36:150,p->state==36?44:158,p->state==36?48:162,-1);
        a->timer=a->delay=1;b->motion.vx=p->facing?0x12000:-0x12000;b->motion.vy=-0x6000;
        p->control_y=-32;a->opaque_5c=0;if(p->state==36)p->milk_status=0;
        p->state=p->state==36?37:35;break;
    case 35: /* 4179ee */
    case 37: /* 418bbb */
        if(!e->random)return unsupported(p,e,6);
        a=p->state==37?&p->milk:&p->penguin;
        if(p->knockback_timer==0)a->timer=1;else --p->knockback_timer;
        for(int i=0;i<5;++i) {
            float particle_vy=(float)((e->random(e->context)%60-60)/10);
            float particle_vx=(float)((e->random(e->context)%60-30)/10);
            int y=b->motion.y/4096-e->random(e->context)%10-40;
            int x=b->motion.x/4096+e->random(e->context)%30+(p->facing?30:-60);
            if(e->particle)e->particle(e->context,x,y,particle_vx,particle_vy);
        }
        break;
    case 39: /* 4178d2 */
    case 41: /* 418a8f */
        if(p->fatal==0) {
            p->penguin_status=0;a=p->state==41?&p->milk:&p->penguin;
            a->opaque_40=0;a->opaque_44=240;p->state=p->state==41?16:0;
        } else if(keys&12)p->fatal=2;
        break;
    case 12: /* 418676 */
    case 28: /* 4199c5 */
        b->motion.vx=b->motion.vy=0;b->motion.ax=0;b->motion.ay=-b->motion.gravity;
        range(a,p->state==12?124:24,p->state==12?124:24,p->state==12?135:35,-1);
        *input&=~3u;p->state=p->state==12?13:29;break;
    case 13: case 29:
        return climb(p,b,input,e,p->state==29);
    case 32: /* 41913d */
        range(a,172,172,190,-1);b->motion.ax=b->motion.vx=0;
        p->control_y=-32;p->state=33;break;
    case 33: /* 419198 */
        if(!e->grounded) {p->state=22;break;}
        if(a->frame==176&&a->timer==0) {
            if(!e->push_query||!e->push_resolve||!e->push_velocity)return unsupported(p,e,5);
            int32_t index=e->push_query(e->context,b->motion.x/4096+(p->facing?-32:32),b->motion.y/4096-100,5);
            if(index!=0) {
                uint32_t handle=e->push_resolve(e->context,index);
                if(handle) {
                    if(e->world_stage<4)event(e,PLAYER_SOUND_PLAY,p->push_sound,6);
                    e->push_velocity(e->context,handle,p->facing?-7.0f:7.0f);
                }
            }
        }
        if(a->frame==a->last&&a->timer==0)p->state=16;
        break;
    case 0: /* 417b96 */
        range(a,47,47,47,-1);a->opaque_40=0;a->opaque_44=300;
        p->control_y=-32;p->state=1;break;
    case 1: /* 417bd5 */
    case 17: /* 418da4 */
        return idle(p,input,e,p->state==17);
    case 2: /* 4181b3 */
        range(a,75,78,87,-1);p->control_y=-32;p->state=3;break;
    case 3: /* 4181f0 */
        if(!e->grounded) {p->state=6;break;}
        if(p->fatal) {p->state=38;break;}
        if(e->ladder&&(keys&3))p->state=12;
        if(keys&PLAYER_JUMP) {p->state=4;break;}
        horizontal(p,b,keys);
        if(!(keys&12))p->state=0;
        break;
    case 4: /* 4182e9 */
        p->control_y=-57;range(a,6,6,8,0);
        p->platform_jump_y=b->platform_dy;*vy=b->platform_dy-0xb000;
        b->motion.vy=*vy;p->jump_hold=10;p->glide_hold=0;
        event(e,PLAYER_SOUND_PLAY,p->jump_sound,0);p->state=5;break;
    case 5: /* 418362 */
    case 21: /* 4197ff */
        if(e->ladder&&(keys&3))p->state=p->state==5?12:28;
        if((keys&PLAYER_JUMP)&&*vy<0&&p->jump_hold>0) {
            --p->jump_hold;*vy=p->platform_jump_y-0xb000;b->motion.vy=*vy;
            p->jump_debounce=-5;break;
        }
        p->state=a==&p->penguin?7:23;break;
    case 6: /* 41840a */
        range(a,8,8,8,0);p->control_y=-57;p->glide_hold=0;p->state=7;break;
    case 7: /* 418441 */
        if(e->ladder&&(keys&3))p->state=12;
        if(*vy>0)a->last=14;
        if(e->grounded&&*vy>=0) {p->state=2;break;}
        if(!(keys&PLAYER_JUMP)&&p->glide_hold==0)p->glide_hold=1;
        if((keys&PLAYER_JUMP)&&p->glide_hold>0) {p->state=10;break;}
        horizontal(p,b,keys);break;
    case 8: /* 4178ff */
        range(a,136,136,143,0);p->control_y=-32;p->state=9;break;
    case 9: /* 417933 / 418196 */
        if(!e->grounded) {p->state=6;break;}
        if(!(keys&PLAYER_DOWN))a->last=149;
        if(a->frame==149&&a->timer==0)p->state=0;
        break;
    case 10: /* 418558: glide, not ordinary falling */
        range(a,287,287,287,0);p->control_y=-57;p->glide_hold=60;
        event(e,PLAYER_SOUND_PLAY,p->glide_sound,0);p->state=11;break;
    case 11: /* 4185a3 */
        if(e->grounded) {
            *input&=~PLAYER_JUMP;p->jump_debounce=0;p->state=2;
            event(e,PLAYER_SOUND_STOP,0,0);break;
        }
        horizontal(p,b,keys);
        if((keys&PLAYER_JUMP)&&p->glide_hold>0) {
            --p->glide_hold;*vy=0;b->motion.vy=0;p->jump_debounce=-1;break;
        }
        p->glide_hold=-1;p->state=7;event(e,PLAYER_SOUND_STOP,0,0);break;
    case 14: /* 417f46: shot animation entry */
        range(a,p->projectile_variant?217:233,p->projectile_variant?217:233,
              p->projectile_variant?231:260,-1);
        p->control_y=-32;p->state=15;break;
    case 15: /* 417f97 */
    case 31: /* 419371 */
        if(!e->grounded) {p->state=p->state==15?6:22;break;}
        if((a->frame==(a==&p->penguin?255:291)||
            a->frame==(a==&p->penguin?226:200))&&a->timer==0) {
            if(!e->random||!e->projectile)return unsupported(p,e,3);
            event(e,PLAYER_SOUND_PLAY,p->shot_sound,a==&p->penguin?0:1);
            int random=e->random(e->context);
            float vx=(keys&PLAYER_UP)?9.0f:16.0f;
            float shot_vy=(float)((keys&PLAYER_UP)?-20-random%3:-11-random%2);
            if(p->facing)vx=-vx;
            e->projectile(e->context,b->motion.x/4096+(p->facing?-32:32),
                          b->motion.y/4096-100,vx,shot_vy,p->projectile_variant);
        }
        if((a->frame==(a==&p->penguin?260:296)||
            a->frame==(a==&p->penguin?231:205))&&a->timer==0)
            p->state=a==&p->penguin?0:16;
        break;
    case 16: /* 418d63 */
        range(a,0,0,0,-1);a->opaque_40=0;a->opaque_44=300;
        p->control_y=-32;p->state=17;break;
    case 18: /* 41958e */
        range(a,0,3,12,-1);p->control_y=-32;p->state=19;break;
    case 19: /* 4195c7 */
        if(!e->grounded) {p->state=22;break;}
        if(p->fatal) {p->state=40;break;}
        if(e->milk_obstacle&&((p->facing==0&&(keys&PLAYER_RIGHT))||
                              (p->facing!=0&&(keys&PLAYER_LEFT)))) {
            p->jump_release=1;*input&=~128u;p->state=32;break;
        }
        if(e->ladder&&(keys&3))p->state=28;
        if(keys&PLAYER_JUMP) {p->state=20;break;}
        horizontal(p,b,keys);if(!(keys&12))p->state=16;break;
    case 20: /* 419781 */
        p->control_y=-57;range(a,56,56,58,0);
        p->platform_jump_y=b->platform_dy;*vy=b->platform_dy-0xb000;
        b->motion.vy=*vy;p->jump_hold=10;p->glide_hold=0;
        event(e,PLAYER_SOUND_PLAY,p->jump_sound,1);p->state=21;break;
    case 22: /* 4198a6 */
        range(a,58,58,58,0);p->control_y=-57;p->glide_hold=0;p->state=23;break;
    case 23: /* 4198dd */
        if(e->ladder&&(keys&3))p->state=28;
        if(*vy>0)a->last=65;
        if(e->grounded&&*vy>=0) {p->state=18;break;}
        horizontal(p,b,keys);break;
    case 24: /* 418acc */
        range(a,259,259,266,0);p->control_y=-32;p->state=25;break;
    case 25: /* 418b00 / 419577 */
        if(!e->grounded) {p->state=22;break;}
        if(!(keys&PLAYER_DOWN))a->last=272;
        if(a->frame==272&&a->timer==0)p->state=16;
        break;
    case 30: /* 419320 */
        range(a,p->projectile_variant?191:273,p->projectile_variant?191:273,
              p->projectile_variant?205:296,-1);
        p->control_y=-32;p->state=31;break;
    case 38: /* 41786c */
        range(&p->penguin,47,47,47,-1);p->control_y=-32;b->motion.ax=0;
        b->motion.vx=0;p->direction_latch=1;*input&=~12u;p->state=39;break;
    case 40: /* 418a2a */
        range(&p->milk,0,0,0,-1);p->control_y=-32;b->motion.ax=0;
        b->motion.vx=0;p->direction_latch=1;*input&=~12u;p->state=41;break;
    default:break; /* Native unsigned state>41 branches to common tail unchanged. */
    }
    return true;
}

bool player_dispatch(Player *p,GameBody *b,unsigned *keys,const PlayerEnvironment *e)
{
    int32_t vy=b->motion.vy;
    for(unsigned count=0;count<64;++count) {
        int old=p->state;
        if(!player_case(p,b,keys,&vy,e))return false;
        if(old==p->state)return true;
    }
    return unsupported(p,e,1);
}

/* Native419dc1..419dda: both character animations share mirror state. */
void player_sync_facing(Player *p)
{
    p->penguin.opaque_50=p->milk.opaque_50=p->facing?0u:2u;
}
/* Native419e76..41a0ee: original430470 is RET, but each nonzero hit
 * timer still decrements and consumes40 rand calls, feet→middle→head. */
bool player_damage_effects_tick(Player *p,const GameBody *b,const PlayerEnvironment *e)
{
    if((p->hit_feet||p->hit_middle||p->hit_head)&&!e->random)return unsupported(p,e,7);
    int32_t *timers[3]={&p->hit_feet,&p->hit_middle,&p->hit_head};
    const int height[3]={0,100,150};
    for(unsigned part=0;part<3;part++){
        if(!*timers[part])continue;
        *timers[part]=(int32_t)((uint32_t)*timers[part]-1u);
        for(unsigned i=0;i<10;i++){
            float vy=(float)((e->random(e->context)%60-60)/10);
            float vx=(float)((e->random(e->context)%60-30)/10);
            int y=b->motion.y/4096-e->random(e->context)%10-height[part];
            int x=b->motion.x/4096+e->random(e->context)%20-10;
            if(e->particle)e->particle(e->context,x,y,vx,vy);
        }
    }
    return true;
}
