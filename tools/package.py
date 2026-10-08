#!/usr/bin/env python3
import os,json,subprocess,base64,hashlib
from validate import ROOT,validate,require,require_health
from verify import manifest_bytes,verify_pair

def package(bundle,key):
 raw=json.dumps(validate(bundle),ensure_ascii=False,separators=(',',':')).encode()
 def sign(value):
  # Existing private key is passed only as an openssl filename; never logged or included in artifacts.
  return base64.b64encode(subprocess.check_output(['openssl','dgst','-sha256','-sign',str(key)],input=value)).decode()
 envelope=json.dumps({'payload':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest(),'signature':sign(raw)},separators=(',',':')).encode()
 manifest={'schemaVersion':1,'engineVersion':bundle['engineVersion'],'revision':bundle['revision'],
  'envelopePath':f"published/rules-{bundle['revision']}.json",'sha256':hashlib.sha256(envelope).hexdigest(),'signature':''}
 manifest['signature']=sign(manifest_bytes(manifest))
 manifest_raw=(json.dumps(manifest,indent=2)+'\n').encode()
 verify_pair(manifest_raw,envelope) # Refuse any private key not matching the Android-pinned public key.
 return manifest_raw,envelope

if __name__=='__main__':
 revision=int(os.environ['RULE_REVISION'])
 bundle=validate(json.loads((ROOT/'bundle.json').read_text()))
 require(bundle['revision']==revision,'Package must use the exact health-tested candidate')
 require_health(json.loads((ROOT/'health.json').read_text()),bundle)
 manifest,envelope=package(bundle,os.environ['NOVEL_RULE_SIGNING_KEY_FILE'])
 staging=ROOT/'staging';staging.mkdir(exist_ok=True)
 # Only these two named files are published. Never glob-upload other staged revisions.
 (staging/f'rules-{revision}.json').write_bytes(envelope)
 (staging/'manifest.json').write_bytes(manifest)
 print('Packaged signed novel manifest and rules',revision)
