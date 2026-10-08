#!/usr/bin/env python3
import os,json,subprocess,base64,hashlib
from pathlib import Path
from validate import ROOT,build
revision=int(os.environ['RULE_REVISION'])
raw=json.dumps(build(revision),ensure_ascii=False,separators=(',',':')).encode()
# Private key is supplied only to openssl; never emitted in logs/artifacts.
key=os.environ['NOVEL_RULE_SIGNING_KEY_FILE']
signature=subprocess.check_output(['openssl','dgst','-sha256','-sign',key],input=raw)
staging=ROOT/'staging';staging.mkdir(exist_ok=True)
envelope=json.dumps({'payload':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest(),'signature':base64.b64encode(signature).decode()},separators=(',',':')).encode()
(staging/f'rules-{revision}.json').write_bytes(envelope)
(staging/'manifest.json').write_text(json.dumps({'engineVersion':1,'revision':revision,'envelopePath':f'published/rules-{revision}.json','sha256':hashlib.sha256(envelope).hexdigest()},indent=2)+'\n')
print('Packaged signed novel rules',revision)
