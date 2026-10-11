#!/usr/bin/env python3
"""Immutable assets first; atomic Git ref update last. Failures preserve the old feed."""
import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
from validate import ROOT,require,require_health,manifest_path,require_staging
from verify import verify_pair,verify_public_feed

def run(*args,**kwargs):return subprocess.run(args,check=True,**kwargs)
revision=int(os.environ['RULE_REVISION'])
manifest=ROOT/'staging/manifest.json';envelope=ROOT/'staging'/f'rules-{revision}.json'
bundle=verify_pair(manifest.read_bytes(),envelope.read_bytes());require(bundle['revision']==revision)
health=json.loads((ROOT/'health.json').read_text())
source=os.environ.get('PUBLICATION_SOURCE') or None
current=None
prior=ROOT/manifest_path(bundle)
if prior.is_file():
 require(prior.is_file(),'Authenticated current bundle required; scoped publication cannot initialize a feed')
 data=json.loads(prior.read_bytes())
 from verify import manifest_bytes
 manifest_bytes(data)
 current=verify_pair(prior.read_bytes(),(ROOT/data['envelopePath']).read_bytes())
 require(bundle['revision']>current['revision'],'Revision must increase')
 if bundle['schemaVersion']==2:
  require({r['id'] for r in current['sources']}<={r['id'] for r in bundle['sources']},'Partial snapshots cannot discard previously accepted sources')
if source:
 require(current is not None,'Authenticated current bundle required; scoped publication cannot initialize a feed')
require_health(health,bundle,current=current,source=source)
if bundle['schemaVersion']==2:
 proof=ROOT/'staging/acceptance.json'
 require(proof.is_file(),'Independent signed partial staging receipt required')
 require_staging(json.loads(proof.read_bytes()),bundle,source)
repo=os.environ['GITHUB_REPOSITORY'];require(repo=='abderrahimgourram/mangaro-novel-sources','Wrong publication namespace')
tag=f"novel-rules-{'partial-' if bundle['schemaVersion']==2 else ''}v{revision}"
existing=subprocess.run(['gh','release','view',tag,'--repo',repo],capture_output=True)
require(existing.returncode!=0,'Never overwrite an existing release')
run('gh','release','create',tag,str(manifest),str(envelope),'--repo',repo,'--target',os.environ['GITHUB_SHA'],'--title',tag,'--notes',f"Verified, signed declarative novel rules for {len(bundle['sources'])} included sources. Absent sources retain trusted application rules. No chapter content. Previous revisions remain available.")
# Verify the actual uploaded bytes before changing published/manifest.json.
with tempfile.TemporaryDirectory() as folder:
 run('gh','release','download',tag,'--repo',repo,'--dir',folder)
 remote=Path(folder)
 require((remote/'manifest.json').read_bytes()==manifest.read_bytes() and (remote/envelope.name).read_bytes()==envelope.read_bytes(),'Uploaded asset mismatch')
 verify_pair((remote/'manifest.json').read_bytes(),(remote/envelope.name).read_bytes())
published=ROOT/manifest_path(bundle);published=published.parent;published.mkdir(parents=True,exist_ok=True)
require(not (published/envelope.name).exists(),'Never overwrite an immutable revision')
shutil.copy2(envelope,published/envelope.name);shutil.copy2(manifest,published/'manifest.json')
run('git','config','user.name','novel-rules-bot');run('git','config','user.email','novel-rules-bot@users.noreply.github.com')
run('git','add',str(published/'manifest.json'),str(published/envelope.name));run('git','commit','-m',f'rules: publish verified revision {revision}')
# Auth stays in gh's credential helper: no token in remote URLs, scripts or Git history.
run('gh','auth','setup-git')
run('git','push','origin','HEAD:main') # Non-fast-forward rejects concurrent source changes; no force push.
for attempt in range(3):
 try:
  delivered=verify_public_feed(manifest.read_bytes(),envelope.read_bytes());break
 except Exception:
  if attempt==2:raise ValueError('Public feed verification failed; preserve pending publication for reconciliation') from None
  time.sleep(3)
require(delivered['revision']==revision,'Public revision mismatch')
print('Published and publicly verified signed CURRENT revision',revision,'; prior immutable revisions retained')
