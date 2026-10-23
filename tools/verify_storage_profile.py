"""Sanitize stdio timing pass-through, short reads, errors, nesting and clock wrap."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--overlay-dir', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
overlay = args.overlay_dir.resolve()
with tempfile.TemporaryDirectory(prefix='kinder-storage-profile-') as directory:
    work = Path(directory)
    (work / 'test.c').write_text(r'''
#include "storage_profile.h"
#include <stdio.h>
#include <stdint.h>
#include <errno.h>
#include <assert.h>
#include <string.h>
int __wrap_fseek(FILE *,long,int);
size_t __wrap_fread(void *,size_t,size_t,FILE *);
static uint32_t clock_ticks;
static int seek_result,nested,read_error;
static size_t read_result=3;
static long expected_offset;
static int expected_whence;
static FILE *const expected_file=(FILE *)(uintptr_t)0x1234;
uint32_t storage_profile_test_now(void){return clock_ticks;}
int __real_fseek(FILE *f,long offset,int whence){
 assert(f==expected_file&&offset==expected_offset&&whence==expected_whence);
 clock_ticks+=7;if(seek_result)errno=EIO;return seek_result;
}
size_t __real_fread(void *out,size_t size,size_t count,FILE *f){
 assert(f==expected_file&&count>=read_result);clock_ticks+=5;
 if(nested){expected_offset=-17;expected_whence=SEEK_CUR;assert(__wrap_fseek(f,-17,SEEK_CUR)==seek_result);}
 memset(out,0x5a,size*read_result);clock_ticks+=11;
 if(read_error)errno=ENOSPC;return read_result;
}
int main(void){
 unsigned char out[16]={0};
 expected_offset=-9;expected_whence=SEEK_END;errno=EDOM;
 #ifdef KINDER_STORAGE_PROFILE_OPTIN
 assert(!storage_profile_enabled);
 assert(!__wrap_fseek(expected_file,-9,SEEK_END));
 assert(__wrap_fread(out,2,7,expected_file)==3);
 storage_profile_snapshot();assert(!storage_frame_seek_us&&!storage_frame_read_us&&!storage_frame_read_calls);
 storage_profile_enable(true);assert(storage_profile_enabled);
 #endif
 assert(__wrap_fseek(expected_file,-9,SEEK_END)==0&&errno==EDOM);
 assert(__wrap_fread(out,2,7,expected_file)==3&&errno==EDOM);
 for(unsigned i=0;i<6;i++)assert(out[i]==0x5a);
 for(unsigned i=6;i<16;i++)assert(out[i]==0);
 storage_profile_snapshot();assert(storage_frame_seek_us==7&&storage_frame_read_us==16);
 assert(storage_frame_seek_calls==1&&storage_frame_read_calls==1&&storage_frame_read_bytes==6);
 storage_profile_snapshot();assert(!storage_frame_seek_us&&!storage_frame_read_us&&!storage_frame_seek_calls&&!storage_frame_read_calls&&!storage_frame_read_bytes);
 seek_result=-1;assert(__wrap_fseek(expected_file,-9,SEEK_END)==-1&&errno==EIO);
 read_result=0;read_error=1;assert(!__wrap_fread(out,2,7,expected_file)&&errno==ENOSPC);
 storage_profile_snapshot();assert(storage_frame_seek_us==7&&storage_frame_read_us==16&&!storage_frame_read_bytes);
 assert(storage_frame_seek_calls==1&&storage_frame_read_calls==1);
 nested=1;read_result=3;read_error=0;seek_result=0;
 assert(__wrap_fread(out,1,3,expected_file)==3);
 storage_profile_snapshot();assert(!storage_frame_seek_us&&storage_frame_read_us==23);
 assert(!storage_frame_seek_calls&&storage_frame_read_calls==1&&storage_frame_read_bytes==3);
 clock_ticks=UINT32_MAX-3u;expected_offset=91;expected_whence=SEEK_SET;
 assert(!__wrap_fseek(expected_file,91,SEEK_SET));
 storage_profile_snapshot();assert(storage_frame_seek_us==7&&!storage_frame_read_us);
 #ifdef KINDER_STORAGE_PROFILE_OPTIN
 storage_profile_enable(false);assert(!storage_profile_enabled&&!storage_frame_seek_us);
 assert(!__wrap_fseek(expected_file,91,SEEK_SET));storage_profile_snapshot();
 assert(!storage_frame_seek_us&&!storage_frame_seek_calls);
 storage_profile_enable(true);assert(!storage_frame_seek_us&&!storage_frame_seek_calls);
 #endif
 puts("stdio telemetry pass-through checks passed");return 0;
}
''')
    has_service = 'storage_set_service_callback' in (overlay/'storage_profile.h').read_text()
    if has_service:
        test = (work/'test.c').read_text()
        test = test.replace('int main(void){', r"""
static unsigned services;
static void service_fixture(void){
 services++;clock_ticks+=1000;
 /* A nested backend call cannot reenter servicing or pollute outer timing. */
 assert(!__wrap_fseek(expected_file,expected_offset,expected_whence));errno=ERANGE;
}
int main(void){""")
        test = test.replace(' puts("stdio', r"""
 nested=0;read_result=3;read_error=0;seek_result=0;
 expected_offset=91;expected_whence=SEEK_SET;
 storage_set_service_callback(service_fixture);errno=EDOM;
 assert(__wrap_fread(out,1,3,expected_file)==3&&errno==EDOM&&services==2);
 storage_profile_snapshot();assert(storage_frame_read_us==16&&!storage_frame_seek_us);
 assert(storage_frame_read_calls==1&&!storage_frame_seek_calls);
 storage_profile_enable(false);errno=EIO;
 assert(__wrap_fread(out,1,3,expected_file)==3&&errno==EIO&&services==4);
 storage_set_service_callback(NULL);
 puts("stdio""")
        (work/'test.c').write_text(test)
    executable = work / 'test'
    subprocess.run(['cc', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-DKINDER_STORAGE_PROFILE_TEST', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', '-I' + str(overlay),
                    str(work / 'test.c'), str(overlay / 'storage_profile.c'),
                    '-o', str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
report = {
    'scope': __doc__, 'asan_ubsan': True,
    'checks': ['arguments and return values', 'short-read byte count',
               'failure errno', 'empty frame reset', 'nested calls counted once',
               'unsigned clock wrap'],
    'source_sha256': hashlib.sha256((overlay / 'storage_profile.c').read_bytes()).hexdigest(),
    'limits': ['Fake backend verifies wrapper semantics, not SD-card latency or ARM9 timing.'],
}
if has_service:report['checks'].append('loader servicing while profiling disabled/enabled, errno preservation and recursion guard')
report['opt_in'] = 'KINDER_STORAGE_PROFILE_OPTIN' in (overlay / 'storage_profile.h').read_text()
if report['opt_in']:
    report['checks'].append('disabled pass-through and clean re-enable')
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
