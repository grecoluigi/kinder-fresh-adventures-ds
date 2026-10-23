"""Validate the supported original disc and extract its game data without running it."""
from pathlib import Path
import argparse, hashlib, json, shutil, struct, subprocess

DISC = dict(bytes=214038528, md5='186e1d22c3cf1d490542399a570e93bb',
            sha256='9c6d7b33665ce10d0d2e38277d07ff51b2887c1b348012fd91210abc308458a7')
MEMBERS = ('DATA1.CAB','DATA1.HDR','DATA2.CAB')

def verify_disc(path):
    hashes={name:hashlib.new(name)for name in ('md5','sha256')}
    with path.open('rb')as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            for digest in hashes.values():digest.update(block)
    actual=dict(bytes=path.stat().st_size,**{name:digest.hexdigest()for name,digest in hashes.items()})
    if actual!=DISC:raise ValueError('Unsupported disc: expected MD5 '+DISC['md5']+', got '+actual['md5'])
    return actual

def root_files(source):
    # The supported disc has a plain ISO9660 primary descriptor and root-level
    # InstallShield volumes. Do not mount it or execute any Windows programs.
    source.seek(16*2048);header=source.read(2048)
    if header[:7]!=b'\x01CD001\x01' or struct.unpack_from('<H',header,128)[0]!=2048:
        raise ValueError('Unsupported ISO9660 descriptor')
    root=header[156:190];extent=struct.unpack_from('<I',root,2)[0];size=struct.unpack_from('<I',root,10)[0]
    if size>1024*1024:raise ValueError('Invalid root directory size')
    source.seek(extent*2048);directory=source.read(size);at=0;files={}
    while at<len(directory):
        length=directory[at]
        if not length:at=(at//2048+1)*2048;continue
        record=directory[at:at+length]
        if length<34 or len(record)!=length or 33+record[32]>length:raise ValueError('Invalid directory record')
        name=record[33:33+record[32]].split(b';')[0].decode('ascii')
        if name in MEMBERS:
            if name in files or record[25] or record[1]:raise ValueError('Unsupported cabinet extent')
            start=struct.unpack_from('<I',record,2)[0]*2048;count=struct.unpack_from('<I',record,10)[0]
            if start>DISC['bytes'] or count>DISC['bytes']-start:raise ValueError('Cabinet outside disc')
            files[name]=(start,count)
        at+=length
    if set(files)!=set(MEMBERS):raise ValueError('InstallShield volumes missing')
    return files

def extract(iso,output,keep_cabinets=False):
    identity=verify_disc(iso)
    if output.exists():raise FileExistsError('Output already exists: '+str(output))
    unshield=shutil.which('unshield')
    if not unshield:raise RuntimeError('Install unshield to extract InstallShield cabinets')
    output.mkdir(parents=True);cabinets=output/'cabinets';cabinets.mkdir();rows=[]
    with iso.open('rb')as source:
        files=root_files(source)
        for name in MEMBERS:
            offset,count=files[name];source.seek(offset);remaining=count;digest=hashlib.sha256()
            with(cabinets/name).open('wb')as target:
                while remaining:
                    block=source.read(min(1024*1024,remaining))
                    if not block:raise ValueError('Truncated disc')
                    target.write(block);digest.update(block);remaining-=len(block)
            rows.append(dict(name=name,bytes=count,sha256=digest.hexdigest()))
    with(output/'extraction.log').open('w')as log:
        subprocess.run([unshield,'-d',str((output/'source').resolve()),'x',str((cabinets/'DATA1.CAB').resolve())],
                       stdout=log,stderr=subprocess.STDOUT,check=True)
    game=output/'source/ausf_hrende_Dateien';exe=game/'JR_FERRERO.exe'
    if not exe.is_file()or exe.read_bytes()[:2]!=b'MZ'or not(game/'GData').is_dir():raise ValueError('Original game files missing after extraction')
    manifest=dict(disc=identity,cabinets=rows,game_directory='source/ausf_hrende_Dateien',
                  files=sum(p.is_file()for p in game.rglob('*')),windows_installer_executed=False)
    (output/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if not keep_cabinets:shutil.rmtree(cabinets)
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--iso',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('build/assets'));p.add_argument('--verify-only',action='store_true')
    p.add_argument('--keep-cabinets',action='store_true');a=p.parse_args()
    try:result=verify_disc(a.iso)if a.verify_only else extract(a.iso,a.output,a.keep_cabinets)
    except(ValueError,RuntimeError,OSError,subprocess.CalledProcessError)as error:p.exit(1,str(error)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
