#!/usr/bin/env python3
"""Immutable assets first; atomic Git ref update last. Failures preserve the old feed."""
import json,os,shutil,subprocess,tempfile
from pathlib import Path
from validate import ROOT,require,require_health
from verify import verify_pair

def run(*args,**kwargs):return subprocess.run(args,check=True,**kwargs)
revision=int(os.environ['RULE_REVISION'])
manifest=ROOT/'staging/manifest.json';envelope=ROOT/'staging'/f'rules-{revision}.json'
bundle=verify_pair(manifest.read_bytes(),envelope.read_bytes());require(bundle['revision']==revision)
health=json.loads((ROOT/'health.json').read_text())
require_health(health,bundle)
repo=os.environ['GITHUB_REPOSITORY'];require(repo=='abderrahimgourram/mangaro-novel-sources','Wrong publication namespace')
tag=f'novel-rules-v{revision}'
existing=subprocess.run(['gh','release','view',tag,'--repo',repo],capture_output=True)
require(existing.returncode!=0,'Never overwrite an existing release')
run('gh','release','create',tag,str(manifest),str(envelope),'--repo',repo,'--target',os.environ['GITHUB_SHA'],'--title',tag,'--notes','Verified, signed declarative novel rules for exactly four approved sources. No chapter content. Previous revisions remain available.')
# Verify the actual uploaded bytes before changing published/manifest.json.
with tempfile.TemporaryDirectory() as folder:
 run('gh','release','download',tag,'--repo',repo,'--dir',folder)
 remote=Path(folder)
 require((remote/'manifest.json').read_bytes()==manifest.read_bytes() and (remote/envelope.name).read_bytes()==envelope.read_bytes(),'Uploaded asset mismatch')
 verify_pair((remote/'manifest.json').read_bytes(),(remote/envelope.name).read_bytes())
published=ROOT/'published';published.mkdir(exist_ok=True)
require(not (published/envelope.name).exists(),'Never overwrite an immutable revision')
shutil.copy2(envelope,published/envelope.name);shutil.copy2(manifest,published/'manifest.json')
run('git','config','user.name','novel-rules-bot');run('git','config','user.email','novel-rules-bot@users.noreply.github.com')
run('git','add','published');run('git','commit','-m',f'rules: publish verified revision {revision}')
# Auth stays in gh's credential helper: no token in remote URLs, scripts or Git history.
run('gh','auth','setup-git')
run('git','push','origin','HEAD:main') # Non-fast-forward rejects concurrent source changes; no force push.
print('Published signed revision',revision,'and advanced the last-known-good feed')
