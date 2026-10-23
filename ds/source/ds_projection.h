#ifndef KINDER_DS_PROJECTION_H
#define KINDER_DS_PROJECTION_H
#include <stdint.h>
/* Uniform8/25world grid. Quantize world positions and camera separately so
 * sprites and pre-sampled scenery move together at every camera phase. */
static inline int ds_world_pixel(int native){
    /* Divide before multiplying: the quotient/remainder fit signed32 bits
     * even at INT_MIN/MAX. ARM9 lowers constant32-bit division to multiply
     * and shifts instead of the longer multiword64-bit arithmetic sequence. */
    int whole=native/25,remainder=native-whole*25;
    int fraction=remainder*8+12;
    return whole*8+(fraction>=0?fraction/25:-((-fraction+24)/25));
}
static inline int ds_relative_pixel(int native,int camera){
    return ds_world_pixel(native)-ds_world_pixel(camera);
}
#endif
