#ifndef KINDER_CAMERA_H
#define KINDER_CAMERA_H
#include <stdint.h>
#define CAMERA_LAYERS 8
typedef struct {
 int16_t tile_x,tile_y,offset_x,offset_y,factor_x,factor_y;
} CameraLayer;
typedef struct {
 CameraLayer layers[CAMERA_LAYERS];
 int32_t max_x,max_y;
 int32_t left,top,right,bottom;
 int16_t reference_layer;
} GameCamera;
/* Native434650 starts on whole tiles. x/y are requested origins, not player positions. */
void camera_init(GameCamera *camera,int width_cells,int height_cells,int x,int y,const int16_t factors[CAMERA_LAYERS],int reference_layer);
/* Native4349c0; selector0 follows left130, selector1 follows right670. */
void camera_follow(GameCamera *camera,int player_x,int player_y,int selector,int disabled);
int camera_x(const GameCamera *camera,int layer);
int camera_y(const GameCamera *camera,int layer);
#endif
