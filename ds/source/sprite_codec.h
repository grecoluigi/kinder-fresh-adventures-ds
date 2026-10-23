#ifndef KINDER_SPRITE_CODEC_H
#define KINDER_SPRITE_CODEC_H
#include "tile_codec.h"
/* Variable-size counterpart of indexed tile packets. Expand backwards inside
 * the RGB555 image buffer so indices require no second allocation/scratch.
 * Header mode0 is palette/direct LZ10; mode1 is exact raw RGB555 (bits16,
 * colors0), with payload length equal to twice the requested pixel count. */
static inline bool sprite_codec_decode(const uint8_t *packet,size_t bytes,uint16_t *image,unsigned pixels){
    if(!packet||!image||!pixels||bytes<4)return false;
    unsigned bits=packet[0],colors=tile_le16(packet+2);
    /* Explicit raw RGB555 fallback: LZ flag/token overhead can make a
     * high-entropy tile larger and slower than an exact pixel copy. */
    if(packet[1]){
        if(packet[1]!=1||bits!=16||colors||((bytes-4)&1u)||(bytes-4)/2!=pixels)return false;
        memcpy(image,packet+4,bytes-4);return true;
    }
    if(bytes<8)return false;
    if(bits==16){if(colors)return false;return tile_decode_lz(packet+4,bytes-4,image,pixels*2);}
    unsigned palette=(colors*2+3)&~3u;
    if((bits!=4&&bits!=8)||!colors||colors>(1u<<bits)||4u+palette>bytes)return false;
    unsigned size=bits==8?pixels:(pixels+1)/2;
    if(!tile_decode_lz(packet+4+palette,bytes-4-palette,image,size))return false;
    const uint8_t *indices=(const uint8_t *)image;
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    if(!(((uintptr_t)packet|(uintptr_t)image)&3u)){
        typedef uint32_t Word __attribute__((__may_alias__));
        typedef uint16_t Halfword __attribute__((__may_alias__));
        const Halfword *colors16=(const Halfword *)(packet+4);unsigned i=pixels;
        if(i&1u){
            --i;unsigned index=bits==8?indices[i]:(indices[i/2]>>((i&1u)*4))&15u;
            if(index>=colors)return false;
            image[i]=colors16[index];
        }
        /* Load both source indices before the in-place word store. Expanding
         * backwards keeps every unread byte intact, including the final pair
         * whose input and output begin at the same address. */
        if(bits==8)while(i){
            i-=2;unsigned packed=image[i/2],a=packed&255u,b=packed>>8;
            if(a>=colors||b>=colors)return false;
            *(Word *)(image+i)=(uint32_t)colors16[a]|(uint32_t)colors16[b]<<16;
        }else while(i){
            i-=2;unsigned packed=indices[i/2],a=packed&15u,b=packed>>4;
            if(a>=colors||b>=colors)return false;
            *(Word *)(image+i)=(uint32_t)colors16[a]|(uint32_t)colors16[b]<<16;
        }
        return true;
    }
#endif
    for(unsigned i=pixels;i--;){
        unsigned index=bits==8?indices[i]:(indices[i/2]>>((i&1)*4))&15u;
        if(index>=colors)return false;
        image[i]=(uint16_t)tile_le16(packet+4+index*2);
    }
    return true;
}
#endif
