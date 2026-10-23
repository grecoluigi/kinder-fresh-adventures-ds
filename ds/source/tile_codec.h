#ifndef KINDER_TILE_CODEC_H
#define KINDER_TILE_CODEC_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
/* Lossless32x32 RGB555 tiles. Packet header: bits8,reserved8,colors16;
 * padded RGB555 palette followed by BIOS LZ10 indices (or direct16-bit pixels).
 * Transparent zero remains distinct from opaque black0x8000. */
#ifdef __NDS__
#include <nds/bios.h>
/* The decompressor changes r2. Declare its scratch registers explicitly so
 * inlined callers cannot keep a live image pointer there across the SWI. */
static inline void tile_lz_wram(const void *source,void *destination){
    register const void *r0 asm("r0")=source;
    register void *r1 asm("r1")=destination;
    asm volatile("swi 0x11 << ((1f - . == 4) * -16); 1:"
                 : "+r"(r0), "+r"(r1) : : "r2", "r3", "r12", "cc", "memory");
}
#endif
static inline unsigned tile_le16(const uint8_t *p){return p[0]|p[1]<<8;}
static inline bool tile_decode_lz(const uint8_t *s,size_t bytes,void *dest,unsigned size){
    if(bytes<4||s[0]!=0x10||((unsigned)s[1]|(unsigned)s[2]<<8|(unsigned)s[3]<<16)!=size)return false;
#ifdef __NDS__
    if(((uintptr_t)s|(uintptr_t)dest)&3)return false;
    tile_lz_wram(s,dest);return true;
#else
    size_t in=4,out=0;uint8_t *d=dest;
    while(out<size){
        if(in>=bytes)return false;
        unsigned flags=s[in++];
        for(unsigned bit=128;bit&&out<size;bit>>=1){
            if(flags&bit){
                if(in+2>bytes)return false;
                unsigned v=s[in]*256+s[in+1];in+=2;
                unsigned n=(v>>12)+3,back=(v&4095)+1;
                if(back>out||n>size-out)return false;
                while(n--){d[out]=d[out-back];out++;}
            }else{if(in>=bytes)return false;d[out++]=s[in++];}
        }
    }
    return in==bytes;
#endif
}
static inline bool tile_codec_decode(const uint8_t *p,size_t bytes,uint16_t *pixels){
    if(!p||!pixels||bytes<8||p[1])return false;
    unsigned bits=p[0],colors=tile_le16(p+2),palette_bytes=(colors*2+3)&~3u;
    if(bits==16){if(colors)return false;return tile_decode_lz(p+4,bytes-4,pixels,2048);}
    if((bits!=4&&bits!=8)||!colors||colors>(1u<<bits)||4u+palette_bytes>bytes)return false;
    uint8_t indices[1024] __attribute__((aligned(4)));
    unsigned size=1024u*bits/8;
    if(!tile_decode_lz(p+4+palette_bytes,bytes-4-palette_bytes,indices,size))return false;
    for(unsigned i=0;i<1024;i++){
        unsigned index=bits==8?indices[i]:(indices[i/2]>>((i&1)*4))&15u;
        if(index>=colors)return false;
        pixels[i]=(uint16_t)tile_le16(p+4+index*2);
    }
    return true;
}
/* Runtime caches can retain the palette and indices instead of expanding
 * every source tile to2048 bytes. The buffer remains word aligned. */
static inline unsigned tile_codec_compact_size(const uint8_t *p,size_t bytes){
    if(!p||bytes<8||p[1])return 0;
    unsigned bits=p[0],colors=tile_le16(p+2),palette=(colors*2+3)&~3u;
    if(bits==16)return colors?0:2048;
    if((bits!=4&&bits!=8)||!colors||colors>(1u<<bits)||4u+palette>bytes)return 0;
    return palette+1024u*bits/8;
}
static inline bool tile_codec_decode_compact(const uint8_t *p,size_t bytes,uint8_t *dest){
    unsigned size=tile_codec_compact_size(p,bytes);if(!size)return false;
    unsigned palette=p[0]==16?0:(tile_le16(p+2)*2+3)&~3u;
    memcpy(dest,p+4,palette);
    if(!tile_decode_lz(p+4+palette,bytes-4-palette,dest+palette,size-palette))return false;
    if(p[0]!=16){
        unsigned colors=tile_le16(p+2);const uint8_t *indices=dest+palette;
        for(unsigned i=0;i<1024;i++){
            unsigned index=p[0]==8?indices[i]:(indices[i/2]>>((i&1)*4))&15u;
            if(index>=colors)return false;
        }
    }
    return true;
}

#endif
