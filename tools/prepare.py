#!/usr/bin/env python3
"""Rollback re-signs verified old selectors at a NEW, increasing revision."""
import argparse,json
from validate import ROOT,build,validate,require
from verify import verify_pair,verify_envelope

def prepare(revision,rollback=0):
 prior=ROOT/'published/manifest.json'
 current=0
 if prior.exists():
  data=json.loads(prior.read_bytes())
  bundle=verify_pair(prior.read_bytes(),(ROOT/'published'/f"rules-{data['revision']}.json").read_bytes())
  current=bundle['revision']
 require(revision>current,'Revision must be greater than the published last-known-good revision')
 if rollback:
  require(0<rollback<=current,'Unknown rollback revision')
  bundle=verify_envelope((ROOT/'published'/f'rules-{rollback}.json').read_bytes())
  bundle['revision']=revision
 else:bundle=build(revision)
 return validate(bundle)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--revision',type=int,required=True)
 parser.add_argument('--rollback',type=int,default=0);args=parser.parse_args()
 (ROOT/'bundle.json').write_text(json.dumps(prepare(args.revision,args.rollback),ensure_ascii=False,separators=(',',':')))
 print('Prepared candidate revision',args.revision,'rollback from',args.rollback or 'none')
