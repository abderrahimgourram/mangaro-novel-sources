#!/usr/bin/env python3
import json,base64,hashlib,subprocess,tempfile
from validate import ROOT
for path in (ROOT/'staging').glob('rules-*.json'):
 data=json.loads(path.read_text());payload=base64.b64decode(data['payload']);signature=base64.b64decode(data['signature'])
 assert hashlib.sha256(payload).hexdigest()==data['sha256']
 with tempfile.TemporaryDirectory() as directory:
  from pathlib import Path
  sig=Path(directory)/'signature';sig.write_bytes(signature)
  subprocess.run(['openssl','dgst','-sha256','-verify',str(ROOT/'keys/rules-public.der'),'-keyform','DER','-signature',str(sig)],input=payload,check=True,capture_output=True)
 print('Verified',path.name)
