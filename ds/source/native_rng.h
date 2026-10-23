#ifndef KINDER_NATIVE_RNG_H
#define KINDER_NATIVE_RNG_H
#include <stdint.h>
void native_rng_seed(uint32_t seed);
int32_t native_rng_next(void);
#endif
