"""Inject optional scenery counters into a temporary build; normal source stays exact.
Each replacement requires unique unchanged context and fails before source mutation.
"""
PATCHES=[
  [
    " (void)value;return 0;\n#endif\n}\n#define COMPOSITE_CACHE_SLOTS 768\ntypedef struct {uint32_t id,opaque_rows,empty_rows,offset;int16_t older,newer;uint16_t bytes,colors;uint8_t bits;bool valid;} Slot;\nstatic Slot slots[COMPOSITE_CACHE_SLOTS];\n",
    " (void)value;return 0;\n#endif\n}\n/* Optional build-time probe: absent from ordinary ROMs. Reader time includes\n * IO; the separate IO counter is a subset. Decode/classify are exclusive. */\n#if defined(__NDS__) && defined(COMPOSITE_PROFILE)\nstatic volatile uint32_t composite_profile_ticks[4];\n#define PROFILE_BEGIN() ticks()\n#define PROFILE_END(kind,start) (composite_profile_ticks[kind]+=ticks()-(start))\n#else\n#define PROFILE_BEGIN() 0u\n#define PROFILE_END(kind,start) ((void)(start))\n#endif\n#define COMPOSITE_CACHE_SLOTS 768\ntypedef struct {uint32_t id,opaque_rows,empty_rows,offset;int16_t older,newer;uint16_t bytes,colors;uint8_t bits;bool valid;} Slot;\nstatic Slot slots[COMPOSITE_CACHE_SLOTS];\n"
  ],
  [
    " if(!bytes||bytes>sizeof(compressed)||offset>atlas_size||bytes>atlas_size-offset)return NULL;\n#ifdef COMPOSITE_DIRECT_READ\n stats->read_calls++;stats->read_bytes+=bytes;\n return !fseek(atlas,offset,SEEK_SET)&&fread(compressed,1,bytes,atlas)==bytes?compressed:NULL;\n#else\n if(!atlas_page){stats->read_calls++;stats->read_bytes+=bytes;return !fseek(atlas,offset,SEEK_SET)&&fread(compressed,1,bytes,atlas)==bytes?compressed:NULL;}\n unsigned copied=0;\n while(copied<bytes){\n  uint32_t at=offset+copied,base=at&~(ATLAS_PAGE_BYTES-1u);\n",
    " if(!bytes||bytes>sizeof(compressed)||offset>atlas_size||bytes>atlas_size-offset)return NULL;\n#ifdef COMPOSITE_DIRECT_READ\n stats->read_calls++;stats->read_bytes+=bytes;\n uint32_t io_start=PROFILE_BEGIN();bool ok=!fseek(atlas,offset,SEEK_SET)&&fread(compressed,1,bytes,atlas)==bytes;PROFILE_END(0,io_start);return ok?compressed:NULL;\n#else\n if(!atlas_page){stats->read_calls++;stats->read_bytes+=bytes;uint32_t io_start=PROFILE_BEGIN();bool ok=!fseek(atlas,offset,SEEK_SET)&&fread(compressed,1,bytes,atlas)==bytes;PROFILE_END(0,io_start);return ok?compressed:NULL;}\n unsigned copied=0;\n while(copied<bytes){\n  uint32_t at=offset+copied,base=at&~(ATLAS_PAGE_BYTES-1u);\n"
  ],
  [
    "   for(unsigned i=1;i<atlas_pages;i++)if(atlas_page_age[i]<atlas_page_age[page])page=i;\n   unsigned amount=atlas_size-base;if(amount>ATLAS_PAGE_BYTES)amount=ATLAS_PAGE_BYTES;\n   stats->read_calls++;stats->read_bytes+=amount;\n   if(fseek(atlas,base,SEEK_SET)||fread(atlas_page_data(page),1,amount,atlas)!=amount)return NULL;\n   atlas_page_offset[page]=base;atlas_page_bytes[page]=amount;\n  }\n  atlas_page_age[page]=++atlas_age;\n",
    "   for(unsigned i=1;i<atlas_pages;i++)if(atlas_page_age[i]<atlas_page_age[page])page=i;\n   unsigned amount=atlas_size-base;if(amount>ATLAS_PAGE_BYTES)amount=ATLAS_PAGE_BYTES;\n   stats->read_calls++;stats->read_bytes+=amount;\n   uint32_t io_start=PROFILE_BEGIN();bool ok=!fseek(atlas,base,SEEK_SET)&&fread(atlas_page_data(page),1,amount,atlas)==amount;PROFILE_END(0,io_start);if(!ok)return NULL;\n   atlas_page_offset[page]=base;atlas_page_bytes[page]=amount;\n  }\n  atlas_page_age[page]=++atlas_age;\n"
  ],
  [
    " uint32_t record_offset=records[id*2],record_size=records[id*2+1];\n uint32_t packet_offset=row_metadata?record_offset&0x1fffffu:record_offset;\n uint32_t bytes=row_metadata?record_size&1023u:record_size;if(bytes>sizeof(compressed))return NULL;\n stats->tile_misses++;\n if(packet_offset>atlas_size-payload_offset)return NULL;\n const uint8_t *packet=read_packet(payload_offset+packet_offset,bytes,stats);if(!packet)return NULL;\n",
    " uint32_t record_offset=records[id*2],record_size=records[id*2+1];\n uint32_t packet_offset=row_metadata?record_offset&0x1fffffu:record_offset;\n uint32_t bytes=row_metadata?record_size&1023u:record_size;if(bytes>sizeof(compressed))return NULL;\n stats->tile_misses++;\n if(packet_offset>atlas_size-payload_offset)return NULL;\n uint32_t packet_start=PROFILE_BEGIN();\n const uint8_t *packet=read_packet(payload_offset+packet_offset,bytes,stats);PROFILE_END(1,packet_start);if(!packet)return NULL;\n"
  ],
  [
    "  if(slot<0){slot=oldest;if(slot<0)return NULL;evict_slot(slot);}\n  offset=cache_cursor;cache_cursor+=size;\n }\n uint8_t *destination=(uint8_t *)pixels_cache+offset;\n if(scaled_tiles){if(!sprite_codec_decode(packet,bytes,(uint16_t *)destination,256))return NULL;}\n else if(indexed_tiles){\n#ifdef COMPOSITE_FORCE_RGB555\n",
    "  if(slot<0){slot=oldest;if(slot<0)return NULL;evict_slot(slot);}\n  offset=cache_cursor;cache_cursor+=size;\n }\n uint8_t *destination=(uint8_t *)pixels_cache+offset;uint32_t decode_start=PROFILE_BEGIN();\n if(scaled_tiles){if(!sprite_codec_decode(packet,bytes,(uint16_t *)destination,256))return NULL;}\n else if(indexed_tiles){\n#ifdef COMPOSITE_FORCE_RGB555\n"
  ],
  [
    "#endif\n }\n else if(!decompress(packet,bytes,(uint16_t *)destination))return NULL;\n slots[slot].offset=offset;slots[slot].bytes=(uint16_t)size;\n slots[slot].bits=indexed_tiles?packet[0]:16;\n slots[slot].colors=indexed_tiles?(uint16_t)le16(packet+2):0;\n",
    "#endif\n }\n else if(!decompress(packet,bytes,(uint16_t *)destination))return NULL;\n PROFILE_END(2,decode_start);\n slots[slot].offset=offset;slots[slot].bytes=(uint16_t)size;\n slots[slot].bits=indexed_tiles?packet[0]:16;\n slots[slot].colors=indexed_tiles?(uint16_t)le16(packet+2):0;\n"
  ],
  [
    " {\n slots[slot].opaque_rows=slots[slot].empty_rows=0;\n unsigned side=scaled_tiles?16:32;\n if(slots[slot].bits==16){\n  classify_rgb555_rows((const uint16_t *)destination,side,&slots[slot].opaque_rows,&slots[slot].empty_rows);\n }else for(unsigned row=0;row<side;row++){",
    " {\n slots[slot].opaque_rows=slots[slot].empty_rows=0;\n unsigned side=scaled_tiles?16:32;uint32_t classify_start=PROFILE_BEGIN();\n if(slots[slot].bits==16){\n  classify_rgb555_rows((const uint16_t *)destination,side,&slots[slot].opaque_rows,&slots[slot].empty_rows);\n }else for(unsigned row=0;row<side;row++){"
  ],
  [
    "  if(opaque==side)slots[slot].opaque_rows|=1u<<row;\n  if(!opaque)slots[slot].empty_rows|=1u<<row;\n }\n }\n slots[slot].id=id;slots[slot].valid=true;lookup[id]=(int16_t)slot;append_slot(slot);\n return slots+slot;\n}\n",
    "  if(opaque==side)slots[slot].opaque_rows|=1u<<row;\n  if(!opaque)slots[slot].empty_rows|=1u<<row;\n }\n PROFILE_END(3,classify_start);\n }\n slots[slot].id=id;slots[slot].valid=true;lookup[id]=(int16_t)slot;append_slot(slot);\n return slots+slot;\n}\n"
  ]
]
def instrument(source):
 for old,new in PATCHES:
  if source.count(old)!=1:raise ValueError('Scenery renderer changed near a probe site; refresh instrumentation before profiling.')
  source=source.replace(old,new,1)
 return '#define COMPOSITE_PROFILE 1\n'+source
