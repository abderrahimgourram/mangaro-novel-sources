#!/usr/bin/env python3
"""Rollback re-signs verified old selectors at a NEW, increasing revision."""
import argparse,json,copy
from validate import ROOT,build,validate,require,manifest_path
from verify import verify_pair,verify_envelope,manifest_bytes

def prepare(revision,rollback=0,initial=False,sources=None):
 candidate=build(revision,sources)
 prior=ROOT/manifest_path(candidate)
 current=0
 if prior.exists():
  data=json.loads(prior.read_bytes());manifest_bytes(data)
  bundle=verify_pair(prior.read_bytes(),(ROOT/data['envelopePath']).read_bytes())
  current=bundle['revision']
 require(current>0 or initial,'Missing production baseline; explicitly authorize initial-release preparation')
 require(not initial or current==0 and rollback==0,'Initial release cannot replace a published revision or fabricate rollback history')
 require(revision>current,'Revision must be greater than the published last-known-good revision')
 # The new feed never replaces the old one, but installed clients share a global floor.
 other=ROOT/('published/manifest.json' if sources is not None else 'published/v2/manifest.json')
 if other.exists():
  data=json.loads(other.read_bytes());manifest_bytes(data)
  anchored=verify_pair(other.read_bytes(),(ROOT/data['envelopePath']).read_bytes())
  require(revision>anchored['revision'],'Revision must exceed both authenticated feeds')
 if rollback:
  require(0<rollback<=current,'Unknown rollback revision')
  bundle=verify_envelope((prior.parent/f'rules-{rollback}.json').read_bytes())
  require(bundle['schemaVersion']==candidate['schemaVersion'],'Rollback channel mismatch')
  bundle['revision']=revision
 elif current and sources is not None:
  # Cumulative signed snapshots preserve previously accepted, excluded replacements.
  bundle=copy.deepcopy(bundle);bundle['revision']=revision
  replacements={row['id']:row for row in candidate['sources']}
  bundle['sources']=[replacements.pop(row['id'],row) for row in bundle['sources']]+list(replacements.values())
 else:bundle=candidate
 return validate(bundle)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--revision',type=int,required=True)
 parser.add_argument('--rollback',type=int,default=0);parser.add_argument('--initial-release',action='store_true')
 parser.add_argument('--sources',help='Comma-separated registered source IDs; selects the versioned partial feed')
 args=parser.parse_args();sources=args.sources.split(',') if args.sources is not None else None
 (ROOT/'bundle.json').write_text(json.dumps(prepare(args.revision,args.rollback,args.initial_release,sources),ensure_ascii=False,separators=(',',':')))
 print('Prepared candidate revision',args.revision,'rollback from',args.rollback or 'none')
