#ifndef KINDER_ADPCM_CODEC_H
#define KINDER_ADPCM_CODEC_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* DS IMA-ADPCM as decoded by the sound hardware: 4-byte header (initial
 * sample, step index, zero), low nibble first, separately truncated step
 * contributions and a +/-32767 clamp. The offline encoder shares advance(). */
static const int16_t adpcm_steps[89]={7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,29794,32767};
static const int8_t adpcm_index_changes[8]={-1,-1,-1,-1,2,4,6,8};
static inline int adpcm_advance(unsigned nibble,int *value,int *index){
 int step=adpcm_steps[*index],difference=step>>3;
 if(nibble&1)difference+=step>>2;
 if(nibble&2)difference+=step>>1;
 if(nibble&4)difference+=step;
 int next=*value+((nibble&8)?-difference:difference);
 *value=next<-32767?-32767:next>32767?32767:next;
 next=*index+adpcm_index_changes[nibble&7];
 *index=next<0?0:next>88?88:next;
 return *value;
}
/* Decode one block of n samples; false for a malformed header or size. */
static inline bool adpcm_decode_block(const uint8_t *packet,size_t bytes,unsigned n,int16_t *out){
 if(!packet||!out||!n||bytes<4u+(n+1u)/2u||packet[2]>88||packet[3])return false;
 int value=(int16_t)((unsigned)packet[0]|(unsigned)packet[1]<<8),index=packet[2];
 if(value<-32767)return false;
 const uint8_t *nibbles=packet+4;
 for(unsigned i=0;i<n;i++)out[i]=(int16_t)adpcm_advance((nibbles[i>>1]>>((i&1u)*4u))&15u,&value,&index);
 return true;
}
#endif
