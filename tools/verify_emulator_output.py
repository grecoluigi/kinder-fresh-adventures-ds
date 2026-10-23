"""Check high-volume logging and failed preference writes without launching an emulator."""
import json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
from emulator_output import BoundedOutput
from playtest import write_config
with tempfile.TemporaryDirectory(prefix='kinder-log-proof-') as td:
 p=Path(td)/'tail.log'
 with BoundedOutput([sys.executable,'-c','import sys;sys.stdout.buffer.write(bytes(range(256))*65536+b"LOG-END")']) as log:
  assert log.process.wait(timeout=10)==0;log.save(p)
  assert log.total_bytes==16777223 and p.stat().st_size==65536 and p.read_bytes().endswith(b'LOG-END')
 drained=log.total_bytes
 # Context cleanup owns and terminates a child even if callers fail.
 with BoundedOutput([sys.executable,'-c','import time;time.sleep(60)']) as log:pass
 assert log.process.poll()is not None and not log.thread.is_alive()
 config=Path(td)/'preferences.toml';original='enabled = false\n';config.write_text(original)
 with patch.object(Path,'write_text',side_effect=OSError('simulated disk full')):
  try:write_config('enabled = true\n',config)
  except OSError:pass
  else:raise AssertionError('Simulated full disk did not fail')
 assert config.read_text()==original and not config.with_suffix('.toml.codex-tmp').exists()
 write_config('enabled = true\n',config);assert config.read_text()=='enabled = true\n'
print(json.dumps({'bytes_drained':drained,'maximum_retained_bytes':65536,'owned_child_cleanup':True,'original_preferences_preserved_on_full_disk':True,'emulator_launched':False}))
