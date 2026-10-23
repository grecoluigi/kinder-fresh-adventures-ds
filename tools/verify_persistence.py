"""Native save routines with mocked stream/CRT boundaries, portable round trips.

The original routine instructions execute; this does not launch original Windows.
Stream outputs are logical LF; Windows text-mode CRLF translation is explicit.
"""
from pathlib import Path
import ctypes as C
import json, random, struct, subprocess, tempfile
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/persistence'
OUT.mkdir(exist_ok=True)
pe=pefile.PE(str(ROOT/'original/extracted/ausf_hrende_Dateien/JR_FERRERO.exe'))
image=pe.get_memory_mapped_image()
u=Uc(UC_ARCH_X86,UC_MODE_32)
u.mem_map(0x400000,(len(image)+4095)&~4095);u.mem_write(0x400000,image)
u.mem_map(0,0x1000);u.mem_map(0x200000,0x40000);u.mem_map(0x4000,0x1000)
OUTPUT=[];DEVICE=1;SKIP_WRITE=False;INPUT_LINES=[];INPUT_INDEX=0;BINARY_INPUT=b'';BINARY_OUTPUT=b'';OPEN_OK=True
def read32(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def signed(x):return C.c_int32(x).value
def text(a):
 data=bytearray()
 while True:
  byte=u.mem_read(a,1)[0];a+=1
  if not byte:return data.decode('cp1252')
  data.append(byte)
def ret(pop=0,eax=None):
 esp=u.reg_read(UC_X86_REG_ESP)
 if eax is not None:u.reg_write(UC_X86_REG_EAX,eax&0xffffffff)
 u.reg_write(UC_X86_REG_EIP,read32(esp));u.reg_write(UC_X86_REG_ESP,esp+4+pop)
def hook(uc,address,size,user):
 global INPUT_INDEX,INPUT_LINES,BINARY_OUTPUT
 esp=uc.reg_read(UC_X86_REG_ESP);ecx=uc.reg_read(UC_X86_REG_ECX)
 if address==0x4422e0:
  uc.mem_write(ecx,struct.pack('<IIIIII',0x230000,0,0,0,0,0));ret(4,ecx)
 elif address==0x4423b4:ret(12,ecx)
 elif address==0x44277d:OUTPUT.append(text(read32(esp+4)));ret(4,ecx)
 elif address==0x44243f:OUTPUT.append(chr(read32(esp+4)));ret(8,ecx)
 elif address==0x4424bb:OUTPUT.append(str(signed(read32(esp+4))));ret(4,ecx)
 elif address==0x442626:OUTPUT.append(str(C.c_int16(read32(esp+4)).value));ret(4,ecx)
 elif address==0x44256c:
  dest=read32(esp+4);limit=read32(esp+8)
  value=INPUT_LINES[INPUT_INDEX]if INPUT_INDEX<len(INPUT_LINES)else b''
  assert len(value)<limit
  uc.mem_write(dest,value+b'\0');INPUT_INDEX+=1
  if INPUT_INDEX>=len(INPUT_LINES):uc.mem_write(ecx+8,b'\x01')
  ret(12,ecx)
 elif address in [0x40a1d0,0x4423fb,0x4423a1,0x441e4e]:ret(0,ecx)
 elif address==0x42827f:ret(0,DEVICE)
 elif address==0x409620:ret(0,1)
 elif address==0x439554:
  dest=read32(esp+4);fmt=text(read32(esp+8));value=signed(read32(esp+12))
  result=fmt%value;uc.mem_write(dest,result.encode('cp1252')+b'\0');ret(0,len(result))
 elif address==0x409ee0 and SKIP_WRITE:ret(0,0)
 elif address==0x439cac:ret(0,0x230100 if OPEN_OK else 0)
 elif address==0x439ba4:
  dest=read32(esp+4);size=read32(esp+8);count=read32(esp+12)
  value=BINARY_INPUT[:size*count]
  if value:uc.mem_write(dest,value)
  ret(0,len(value)//size)
 elif address==0x439cbf:
  source=read32(esp+4);size=read32(esp+8);count=read32(esp+12)
  BINARY_OUTPUT=bytes(uc.mem_read(source,size*count));ret(0,count)
 elif address==0x439b4e:ret(0,0)
 elif address in [0x409cc6,0x409c8d]:
  INPUT_LINES=''.join(OUTPUT).encode().split(b'\n');INPUT_INDEX=0
u.hook_add(UC_HOOK_CODE,hook)
def run(entry,args=()):
 global SKIP_WRITE
 SKIP_WRITE=entry==0x4091b0
 OUTPUT.clear();u.mem_write(0,b'\0'*4)
 u.mem_write(0x220000,struct.pack('<'+'I'*(1+len(args)),0x4000,*args))
 u.reg_write(UC_X86_REG_ESP,0x220000)
 u.emu_start(entry,0x4000,count=1000000)
 return ''.join(OUTPUT).encode('cp1252')
class Table(C.Structure):_fields_=[('names',(C.c_char*30)*10),('score_text',(C.c_char*10)*10)]
class State(C.Structure):_fields_=[('scores',Table*4),('options',C.c_int32*22),('tutorials',C.c_uint8*4)]
def native_table(t,score):
 u.mem_write(0x210000,bytes(t)[:300]);u.mem_write(0x211000,bytes(t)[300:])
 u.mem_write(0x45ed2c,struct.pack('<i',score))
 run(0x4091b0,(0x212000,0x210000,0x211000))
 return signed(u.reg_read(UC_X86_REG_EAX)),bytes(u.mem_read(0x210000,300)),bytes(u.mem_read(0x211000,100))
with tempfile.TemporaryDirectory(prefix='kinder-persistence-') as directory:
 libpath=Path(directory)/'persistence.dylib'
 subprocess.run(['cc','-dynamiclib','-std=c11','-O2','-Wall','-Wextra','-Werror',str(ROOT/'ds/source/persistence.c'),str(ROOT/'ds/source/persistence_store.c'),'-o',str(libpath)],check=True)
 lib=C.CDLL(str(libpath));lib.persistence_defaults.argtypes=[C.POINTER(State),C.c_bool]
 lib.persistence_qualify.argtypes=[C.POINTER(Table),C.c_int32]
 lib.persistence_write_highscores.argtypes=[C.POINTER(Table),C.c_void_p,C.c_size_t];lib.persistence_write_highscores.restype=C.c_size_t
 lib.persistence_write_options.argtypes=[C.POINTER(C.c_int32),C.c_void_p,C.c_size_t];lib.persistence_write_options.restype=C.c_size_t
 lib.persistence_parse_highscores.argtypes=[C.POINTER(Table),C.c_char_p,C.c_size_t]
 lib.persistence_parse_options.argtypes=[C.POINTER(C.c_int32),C.c_char_p,C.c_size_t]
 lib.persistence_load.argtypes=[C.c_char_p,C.POINTER(State)]
 lib.persistence_save.argtypes=[C.c_char_p,C.POINTER(State)]
 counts={'native_default_scores':0,'native_default_options':0,'native_insertion':0,'native_score_writes':0,'native_score_reads':0,'native_option_writes':0,'native_option_reads':0,'native_tutorial_read_write':0,'file_roundtrip':0}
 buffer=C.create_string_buffer(2300)
 for device in [False,True]:
  state=State();lib.persistence_defaults(C.byref(state),device);DEVICE=int(device)
  expected=run(0x409cd0,(0x212000,)).replace(b'\n',b'\r\n')
  size=lib.persistence_write_highscores(C.byref(state.scores[0]),buffer,len(buffer));assert buffer.raw[:size]==expected
  (OUT/'default-highscores.dat').write_bytes(expected);counts['native_default_scores']+=1
  expected=run(0x4096e0).replace(b'\n',b'\r\n')
  size=lib.persistence_write_options(state.options,buffer,len(buffer));assert buffer.raw[:size]==expected
  (OUT/('default-options-device.ini'if device else 'default-options-keyboard.ini')).write_bytes(expected);counts['native_default_options']+=1
 rng=random.Random(20020117)
 lib.persistence_decimal.argtypes=[C.c_char_p];lib.persistence_decimal.restype=C.c_int32
 decimal_cases=[b'',b'foo',b'  -12tail',b'+0',b'-0',b'2147483648',b'4294967295',b'-2147483649',b'99999999999999999999',b'\t\n\r\v\f42',b'--5']
 decimal_cases.extend((rng.choice(['','+','-'])+str(rng.randrange(0,10**20))+rng.choice(['','tail',' '])).encode()for _ in range(1000))
 for value in decimal_cases:
  u.mem_write(0x210000,value+b'\0');run(0x439a45,(0x210000,))
  assert signed(u.reg_read(UC_X86_REG_EAX))==lib.persistence_decimal(value),value
 counts['native_decimal']=len(decimal_cases)
 for case in range(300):
  t=Table();values=[rng.randrange(-1000000,10000000)for _ in range(10)]
  if case<100:values.sort(reverse=True)
  for i,value in enumerate(values):t.names[i].value=f'Name {i}'.encode();t.score_text[i].value=str(value).encode()
  score=rng.choice(values)if case%5==0 else rng.randrange(-1000000,10000000)
  native_rank,native_names,native_scores=native_table(t,score)
  portable_rank=lib.persistence_qualify(C.byref(t),score)
  assert native_rank==portable_rank,(case,native_rank,portable_rank)
  # Native strcpy preserves trailing slot bytes; compare string semantics.
  for i in range(10):
   assert native_names[i*30:(i+1)*30].split(b'\0')[0]==t.names[i].value,(case,i)
   assert native_scores[i*10:(i+1)*10].split(b'\0')[0]==t.score_text[i].value,(case,i)
  counts['native_insertion']+=1
  u.mem_write(0x210000,bytes(t)[:300]);u.mem_write(0x211000,bytes(t)[300:])
  expected=run(0x409ee0,(0x212000,0x210000,0x211000)).replace(b'\n',b'\r\n')
  size=lib.persistence_write_highscores(C.byref(t),buffer,len(buffer));assert buffer.raw[:size]==expected
  parsed=Table();assert lib.persistence_parse_highscores(C.byref(parsed),expected,len(expected));counts['native_score_writes']+=1
  INPUT_LINES=expected.split(b'\r\n');INPUT_INDEX=0
  u.mem_write(0x210000,b'\0'*300);u.mem_write(0x211000,b'\0'*100)
  run(0x409e00,(0x212000,0x210000,0x211000))
  assert bytes(u.mem_read(0x210000,300))+bytes(u.mem_read(0x211000,100))==bytes(parsed)
  counts['native_score_reads']+=1
 state=State();lib.persistence_defaults(C.byref(state),True)
 state.tutorials[:]=[1,0,7,255]
 for index in range(22):state.options[index]=rng.randrange(-100,100)
 u.mem_write(0x45efe8,struct.pack('<8i',*state.options[:8]))
 u.mem_write(0x45ecf8,struct.pack('<8i',*state.options[8:16]))
 u.mem_write(0x45ed28,struct.pack('<2h',*state.options[16:18]));u.mem_write(0x45ed30,struct.pack('<2h',*state.options[18:20]))
 u.mem_write(0x45ecc0,struct.pack('<i',state.options[20]));u.mem_write(0x45efe4,struct.pack('<i',state.options[21]))
 expected=run(0x409a60).replace(b'\n',b'\r\n')
 size=lib.persistence_write_options(state.options,buffer,len(buffer));assert buffer.raw[:size]==expected;counts['native_option_writes']+=1
 INPUT_LINES=expected.split(b'\r\n');INPUT_INDEX=0;run(0x409870)
 actual=list(struct.unpack('<8i',u.mem_read(0x45efe8,32)))+list(struct.unpack('<8i',u.mem_read(0x45ecf8,32)))+list(struct.unpack('<2h',u.mem_read(0x45ed28,4)))+list(struct.unpack('<2h',u.mem_read(0x45ed30,4)))+[signed(read32(0x45ecc0)),signed(read32(0x45efe4))]
 parsed=(C.c_int32*22)();assert lib.persistence_parse_options(parsed,expected,len(expected));assert list(parsed)==actual;counts['native_option_reads']+=1
 lib.persistence_normalize_options.argtypes=[C.POINTER(C.c_int32),C.c_bool]
 for device in [0,1]:
  DEVICE=device
  for case in range(10):
   values=[rng.choice([-1,0,2,7])for _ in range(22)]
   INPUT_LINES=[str(x).encode()for x in values];INPUT_INDEX=0;run(0x409bf0)
   actual=list(struct.unpack('<8i',u.mem_read(0x45efe8,32)))+list(struct.unpack('<8i',u.mem_read(0x45ecf8,32)))+list(struct.unpack('<2h',u.mem_read(0x45ed28,4)))+list(struct.unpack('<2h',u.mem_read(0x45ed30,4)))+[signed(read32(0x45ecc0)),signed(read32(0x45efe4))]
   options=(C.c_int32*22)(*values);lib.persistence_normalize_options(options,bool(device));assert list(options)==actual,(device,case,values,list(options),actual)
 counts['native_option_normalization']=20
 lib.persistence_parse_tutorials.argtypes=[C.POINTER(C.c_uint8),C.c_void_p,C.c_size_t]
 for data in [b'',b'\x01',b'\x01\xff',b'\x00\x07\xff',b'\x01\x02\x03\x04',b'\x01\x02\x03\x04\x05']:
  BINARY_INPUT=data;OPEN_OK=True;run(0x40a0b0)
  flags=(C.c_uint8*4)();lib.persistence_parse_tutorials(flags,data,len(data))
  assert bytes(flags)==bytes(u.mem_read(0x45ed4c,4))
  run(0x40a0f0);assert BINARY_OUTPUT==bytes(flags);counts['native_tutorial_read_write']+=1
 assert lib.persistence_save(directory.encode(),C.byref(state))==63
 loaded=State();lib.persistence_defaults(C.byref(loaded),False)
 assert lib.persistence_load(directory.encode(),C.byref(loaded))==63
 assert bytes(loaded)==bytes(state);counts['file_roundtrip']+=1
 assert lib.persistence_load((directory+'/absent').encode(),C.byref(loaded))==0
 invalid=Table.from_buffer_copy(bytes(state.scores[0]));before=bytes(invalid)
 assert not lib.persistence_parse_highscores(C.byref(invalid),b'truncated',9);assert bytes(invalid)==before
 result={'counts':counts,'failures':[],'native_functions':['0x409cd0','0x4096e0','0x4091b0','0x409ee0','0x409e00','0x409a60','0x409870','0x40a0b0','0x40a0f0','0x439a45','0x409bf0'],
         'scope':__doc__,'limitations':['Original C++ stream/format and binary I/O boundaries are mocked. Original atoi instructions execute against the shipped C-locale table. Native instructions select records, defaults, ranking, sorting and read/write sequence.','Physical CRLF conversion is explicit Windows text-mode translation; no Windows runtime executed.','Malformed input is rejected transactionally, rather than reproducing original stream failbit/unsafe-buffer behavior.','DS FAT integration, UI callbacks and power-loss recovery have not been verified.']}
 (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
