#!/usr/bin/env python3
"""Verify the actual signed manifest AND envelope against the Android-pinned key."""
import argparse,base64,hashlib,json,re,subprocess,tempfile
from pathlib import Path
from validate import ROOT,require,validate

def verify_signature(raw,encoded,key):
 signature=base64.b64decode(encoded,validate=True)
 with tempfile.TemporaryDirectory() as directory:
  sig=Path(directory)/'signature';sig.write_bytes(signature)
  result=subprocess.run(['openssl','dgst','-sha256','-verify',str(key),'-keyform','DER','-signature',str(sig)],input=raw,capture_output=True)
 require(result.returncode==0,'Invalid signature')

def manifest_bytes(data):
 require(set(data)=={'schemaVersion','engineVersion','revision','envelopePath','sha256','signature'},'Invalid manifest schema')
 require(type(data['schemaVersion']) is int and data['schemaVersion']==1)
 require(type(data['engineVersion']) is int and data['engineVersion'] in (1,2),'Incompatible engine')
 require(type(data['revision']) is int and 0<data['revision']<=2147483647)
 require(data['envelopePath']==f"published/rules-{data['revision']}.json",'Invalid envelope path')
 require(isinstance(data['sha256'],str) and re.fullmatch('[0-9a-f]{64}',data['sha256']))
 # Fixed ASCII-only, domain-separated protocol shared with Android: no JSON serialization ambiguity.
 return ('MangaroNovelManifestV1\n'+''.join(str(data[x])+'\n' for x in
  ('schemaVersion','engineVersion','revision','envelopePath','sha256'))).encode('ascii')

def verify_envelope(raw,key=ROOT/'keys/rules-public.der'):
 require(len(raw)<=96*1024,'Oversized envelope')
 data=json.loads(raw);require(set(data)=={'payload','sha256','signature'})
 payload=base64.b64decode(data['payload'],validate=True)
 require(len(payload)<=64*1024 and hashlib.sha256(payload).hexdigest()==data['sha256'],'Invalid payload hash')
 verify_signature(payload,data['signature'],key)
 return validate(json.loads(payload))

def verify_pair(manifest_raw,envelope,key=ROOT/'keys/rules-public.der'):
 require(len(manifest_raw)<=8192,'Oversized manifest')
 manifest=json.loads(manifest_raw)
 verify_signature(manifest_bytes(manifest),manifest['signature'],key)
 require(hashlib.sha256(envelope).hexdigest()==manifest['sha256'],'Invalid envelope hash')
 bundle=verify_envelope(envelope,key)
 require(bundle['revision']==manifest['revision'] and bundle['engineVersion']==manifest['engineVersion'],'Manifest/payload mismatch')
 return bundle

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=ROOT/'staging');args=parser.parse_args()
 manifest=(args.directory/'manifest.json').read_bytes()
 data=json.loads(manifest)
 manifest_bytes(data) # Validate path before local file access.
 bundle=verify_pair(manifest,(args.directory/Path(data['envelopePath']).name).read_bytes())
 print('Verified signed manifest and four-source envelope; engine',bundle['engineVersion'],'revision',bundle['revision'])
