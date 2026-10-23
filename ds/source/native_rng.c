#include "native_rng.h"
static uint32_t state=1;
void native_rng_seed(uint32_t seed){state=seed;}
int32_t native_rng_next(void){state=state*214013u+2531011u;return (int32_t)((state>>16)&32767u);}
