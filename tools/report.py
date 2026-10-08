#!/usr/bin/env python3
import json,os
from validate import ROOT
report=ROOT/'health.json'
text='## Novel source health\n\n'
if not report.exists():text+='Health report unavailable; publication is not approved.\n'
else:
 text+='| Source | Catalog | Search | Details | Chapters | Text | Failure |\n|---|---|---|---|---|---|---|\n'
 for item in json.loads(report.read_text()):
  states=['PASS' if item.get(x) else 'FAIL' for x in ('catalog','search','details','chapters','text')]
  text+='| '+str(item.get('domain','unknown'))+' | '+' | '.join(states)+' | '+str(item.get('failedStage','—'))+' |\n'
 text+='\nOnly counts, hashes and error categories are retained. Failed probes cannot advance the published feed.\n'
summary=os.environ.get('GITHUB_STEP_SUMMARY')
if summary:
 with open(summary,'a') as file:file.write(text)
else:print(text)
