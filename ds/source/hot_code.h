#ifndef KINDER_HOT_CODE_H
#define KINDER_HOT_CODE_H
/* ARM9-only instruction placement. All DMA/audio buffers remain in main RAM. */
#if defined(__NDS__) && defined(ARM9) && !defined(KF_DISABLE_ITCM)
#include <nds/ndstypes.h>
#define KF_ITCM_CODE ITCM_CODE
#else
#define KF_ITCM_CODE
#endif
#endif
