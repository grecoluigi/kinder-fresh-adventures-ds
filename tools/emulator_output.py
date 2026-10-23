"""Continuously drain an owned child process into a bounded in-memory log tail."""
import subprocess,threading
class BoundedOutput:
 def __init__(self,command,limit=65536):
  if limit<=0:raise ValueError('Output limit must be positive')
  self.command=command;self.limit=limit;self.data=bytearray();self.total_bytes=0;self.process=None;self.thread=None;self.error=None
 def __enter__(self):
  self.process=subprocess.Popen(self.command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  def drain():
   try:
    while chunk:=self.process.stdout.read1(8192):
     self.total_bytes+=len(chunk);self.data.extend(chunk)
     if len(self.data)>self.limit:del self.data[:-self.limit]
   except Exception as error:self.error=error
   finally:self.process.stdout.close()
  self.thread=threading.Thread(target=drain,name='bounded-emulator-log',daemon=True);self.thread.start();return self
 def save(self,path):
  self.thread.join(timeout=5)
  if self.thread.is_alive():raise RuntimeError('Child output pipe did not close after process exit')
  if self.error:raise RuntimeError('Could not drain child output') from self.error
  path.write_bytes(self.data)
 def __exit__(self,*exception):
  if self.process.poll()is None:
   self.process.terminate()
   try:self.process.wait(timeout=10)
   except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
  self.thread.join(timeout=5)
