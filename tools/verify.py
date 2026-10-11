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
 require(type(data['schemaVersion']) is int and data['schemaVersion'] in (1,2))
 require(type(data['engineVersion']) is int and data['engineVersion'] in ((1,2) if data['schemaVersion']==1 else (3,)),'Incompatible engine')
 require(type(data['revision']) is int and 0<data['revision']<=2147483647)
 require(data['envelopePath']==f"published/{'v2/' if data['schemaVersion']==2 else ''}rules-{data['revision']}.json",'Invalid envelope path')
 require(isinstance(data['sha256'],str) and re.fullmatch('[0-9a-f]{64}',data['sha256']))
 # Fixed ASCII-only, domain-separated protocol shared with Android: no JSON serialization ambiguity.
 return (f"MangaroNovelManifestV{data['schemaVersion']}\n"+''.join(str(data[x])+'\n' for x in
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
 require(bundle['schemaVersion']==manifest['schemaVersion'] and bundle['revision']==manifest['revision'] and bundle['engineVersion']==manifest['engineVersion'],'Manifest/payload mismatch')
 return bundle

def verify_public_feed(expected_manifest,expected_envelope):
 """Verify exactly the public feed consumed by Android after the atomic Git update."""
 import requests
 base='https://raw.githubusercontent.com/abderrahimgourram/mangaro-novel-sources/main/'
 def read(path,limit):
  with requests.get(base+path,timeout=(5,10),allow_redirects=False,stream=True,headers={'Cache-Control':'no-cache'}) as response:
   require(response.status_code==200,'Public rule asset unavailable')
   body=bytearray()
   for chunk in response.iter_content(8192):
    body.extend(chunk);require(len(body)<=limit,'Public rule asset oversized')
   return bytes(body)
 expected=json.loads(expected_manifest);manifest_bytes(expected)
 manifest=read('published/'+('v2/' if expected['schemaVersion']==2 else '')+'manifest.json',8192)
 data=json.loads(manifest);manifest_bytes(data)
 envelope=read(data['envelopePath'],96*1024)
 bundle=verify_pair(manifest,envelope)
 require(manifest==expected_manifest and envelope==expected_envelope,'Public feed does not match published revision')
 return bundle

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=ROOT/'staging');args=parser.parse_args()
 manifest=(args.directory/'manifest.json').read_bytes()
 data=json.loads(manifest)
 manifest_bytes(data) # Validate path before local file access.
 bundle=verify_pair(manifest,(args.directory/Path(data['envelopePath']).name).read_bytes())
 print('Verified signed manifest and four-source envelope; engine',bundle['engineVersion'],'revision',bundle['revision'])
