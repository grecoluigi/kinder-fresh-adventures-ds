#include "world_routes.h"
#include <stddef.h>
static const WorldRoute main_routes[4]={
 {"Welt1.W02","GData\\Maps\\Welt1.w01","GData\\Maps\\Welt1.w02",0,false,false},
 {"Welt2.W02","GData\\Maps\\Welt2.w01","GData\\Maps\\Welt2.w02",1,false,false},
 {"welt3.W02","GData\\Maps\\Welt3.w01","GData\\Maps\\Welt3.w02",2,false,false},
 {"welt4.W02","GData\\Maps\\Welt4.w01","GData\\Maps\\Welt4.w02",3,false,false}
};
static const WorldRoute tutorial_routes[4]={
 {"Welt1t.W02","GData\\Maps\\Welt1t.w01","GData\\Maps\\Welt1t.w02",0,true,false},
 {"Welt2T.W02","GData\\Maps\\Welt2t.w01","GData\\Maps\\Welt2t.w02",1,true,false},
 {"welt3t.W02","GData\\Maps\\Welt3t.w01","GData\\Maps\\Welt3t.w02",2,true,false},
 {"welt4t.W02","GData\\Maps\\Welt4t.w01","GData\\Maps\\Welt4t.w02",3,true,false}
};
static const WorldRoute arena_routes[4]={
 {"Welt1E.W02","GData\\Maps\\Welt1.w01","GData\\Maps\\Welt1e.w02",0,false,true},
 {"Welt2E.W02","GData\\Maps\\Welt2.w01","GData\\Maps\\Welt2e.w02",1,false,true},
 {"Welt3E.W02","GData\\Maps\\Welt3.w01","GData\\Maps\\Welt3e.w02",2,false,true},
 {"Welt4E.W02","GData\\Maps\\Welt4.w01","GData\\Maps\\Welt4e.w02",3,false,true}
};
const WorldRoute *world_route_select(unsigned world,const uint8_t tutorials[4]){
 if(world>=8)return NULL;
 if(world>=4)return &arena_routes[world-4];
 return tutorials&&tutorials[world]?&main_routes[world]:&tutorial_routes[world];
}

int world_arena_target(unsigned world,const int16_t ingredients[6]){
 if(world>=4||!ingredients)return -1;
 for(unsigned i=0;i<6;i++)if(!ingredients[i])return -1;
 return (int)world+4;
}

bool world_arena_startup(unsigned world,WorldArenaStartup *startup){
 if(world<4||world>=8||!startup)return false;
 *startup=(WorldArenaStartup){1,world!=6,world==5?0:32,world==5?0:224};
 return true;
}
