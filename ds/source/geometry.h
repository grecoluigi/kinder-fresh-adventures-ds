#ifndef KF_GEOMETRY_H
#define KF_GEOMETRY_H
#include <stdint.h>
/* Original list record: 32 bytes. Bounds use source pixels, right/bottom exclusive. */
typedef struct {
    int32_t left, right, top, bottom;
    uint32_t flags;
    int32_t reserved20, object_index, reserved28;
} GeometryRect;
/* Animation collision bounds must already be resolved by the scene. */
typedef struct {
    int16_t id, x, y, active, width, height, align_x, align_y;
    uint8_t solid, top_trim;
    int32_t object_index;
} GeometryObject;
uint32_t geometry_query(const GeometryRect *rects, int32_t count,
                        int32_t x, int32_t y, uint32_t mode);
/* Input order is the native selected-object index order. Output reverses it. */
int32_t geometry_build(GeometryRect *out, int32_t capacity,
                       const GeometryObject *objects, int32_t count,
                       int32_t left, int32_t top, int32_t right, int32_t bottom);
#endif
