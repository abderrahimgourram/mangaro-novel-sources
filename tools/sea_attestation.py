"""SeaNovel-only remote probe; never accepts an unsigned, stale or other-request result."""
import base64,hashlib,hmac,json,os,re,secrets,time
import requests
from validate import validate,require
URL='https://mangaro-seanovel-check.vercel.app/api/probe'

def check(bundle, deep=False, endpoint=None):
    validate(bundle)
    target = endpoint or URL
    require(target == URL or re.fullmatch(r'https://mangaro-seanovel-check-[a-z0-9]+-jalem\.vercel\.app/api/probe', target), 'Unapproved attestation deployment')
    protocol = 2 if deep else 1
    key=os.environ.get('SEANOVEL_ATTESTATION_SECRET','')
    require(len(key)==64 and all(c in '0123456789abcdef' for c in key),'SeaNovel attestation secret missing/invalid')
    candidate=json.dumps(bundle,ensure_ascii=False,separators=(',',':')).encode()
    digest=hashlib.sha256(candidate).hexdigest()
    nonce=secrets.token_hex(32);requested=int(time.time())
    raw=json.dumps({'protocol':protocol,'candidateSha256':digest,'revision':bundle['revision'],'requestedAt':requested,
                    'nonce':nonce,'bundle':base64.b64encode(candidate).decode()},separators=(',',':')).encode()
    mac=hmac.new(key.encode(),('request-v%d\n'%protocol).encode()+raw,hashlib.sha256).hexdigest()
    with requests.post(target,data=raw,headers={'Content-Type':'application/json','Authorization':'HMAC-SHA256 '+mac},
                       timeout=(10,110),allow_redirects=False,stream=True) as response:
        response.raise_for_status()
        body=bytearray()
        for chunk in response.iter_content(4096):
            body.extend(chunk);require(len(body)<=16384,'Oversized attestation')
    wrapped=json.loads(body)
    require(set(wrapped)=={'payload','signature'})
    payload=base64.b64decode(wrapped['payload'],validate=True)
    expected=hmac.new(key.encode(),('response-v%d\n'%protocol).encode()+payload,hashlib.sha256).hexdigest()
    require(isinstance(wrapped['signature'],str) and hmac.compare_digest(expected,wrapped['signature']),'Invalid attestation signature')
    data=json.loads(payload)
    require(set(data)=={'protocol','candidateSha256','revision','requestedAt','nonce','timestamp','result'})
    require(type(data['protocol']) is int and data['protocol']==protocol)
    require(data['candidateSha256']==digest and type(data['revision']) is int and data['revision']==bundle['revision'])
    require(data['nonce']==nonce and type(data['requestedAt']) is int and data['requestedAt']==requested,'Replayed/mismatched result')
    now=int(time.time());stamp=data['timestamp']
    require(type(stamp) is int and requested-5<=stamp<=now+5 and now-stamp<=120 and now-requested<=120,'Stale attestation')
    result=data['result']
    require(isinstance(result,dict) and result.get('domain')=='seanovel.org')
    verified = dict(result,rulesSha256=digest,revision=bundle['revision'],attestedAt=stamp,requestNonce=nonce,attestationVerified=True)
    if deep and result.get('status') in ('failed','blocked'):
        require(result.get('completeIndex') is False and result.get('indexState') == 'INTERRUPTED', 'Invalid failure attestation')
        return verified
    require(result.get('status')=='healthy')
    require(all(result.get(x) is True for x in ('catalog','search','details','chapters','text')),'SeaNovel stage failed')
    for field,minimum,maximum in [('catalog_count',1,1000),('chapter_count',1,100000),('paragraphs',4,100000),('text_characters',501,8*1024*1024)]:
        value=result.get(field);require(type(value) is int and minimum<=value<=maximum,'Invalid probe counts')
    if deep:
        require(result.get('completeIndex') is True and result.get('indexState')=='COMPLETE' and result.get('verificationTier')=='ATTESTED_COMPLETE_INDEX', 'Incomplete index attestation')
        require(type(result.get('officialTotal')) is int and result['officialTotal']==result['chapter_count'], 'Attested total mismatch')
        require(result.get('ordering')=='SOURCE_ID_ASCENDING' and result.get('chapterPages')==1, 'Unsupported traversal evidence')
        require(type(result.get('sampledTexts')) is int and result['sampledTexts']==min(3,result['chapter_count']), 'Missing representative text samples')
        for field in ('identityHash','indexHash'):
            require(isinstance(result.get(field),str) and re.fullmatch('[0-9a-f]{64}',result[field]), 'Missing identity/index evidence')
        require(result['identityHash']==hashlib.sha256(b'seanovel.org:https://seanovel.org/novels/terra-nova-online-rise-of-the-strongest-player').hexdigest(), 'Unexpected attested novel identity')
        require(isinstance(result.get('sampleHashes'),list) and len(result['sampleHashes'])==result['sampledTexts'] and all(isinstance(h,str) and re.fullmatch('[0-9a-f]{64}',h) for h in result['sampleHashes']), 'Missing text evidence')
    return verified

if __name__=='__main__':
    import argparse
    from pathlib import Path
    from validate import build
    parser=argparse.ArgumentParser()
    parser.add_argument('--deep',action='store_true')
    parser.add_argument('--deployment',default='')
    parser.add_argument('--sources',help='Explicit registered IDs for schema-2 partial compatibility verification')
    args=parser.parse_args()
    try:
        result=check(build(2,args.sources.split(',') if args.sources is not None else None),deep=args.deep,endpoint=args.deployment.rstrip('/')+'/api/probe' if args.deployment else None)
        result.pop('requestNonce',None)
        result.update(purpose='SOURCE_EVIDENCE_ONLY',production='NOT_EXECUTED')
        passed=result.get('status')=='healthy' and (not args.deep or result.get('completeIndex') is True)
    except Exception as error:
        result=dict(status='UNVERIFIED',error_type=type(error).__name__,production='NOT_EXECUTED')
        passed=False
    Path('seanovel-attestation-report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as stream:
            stream.write('SeaNovel signed verification: %s; complete index: %s; observed chapters: %s; publication: NOT_EXECUTED.\n'%(result.get('status'),result.get('completeIndex',False),result.get('chapter_count','unverified')))
    raise SystemExit(0 if passed else 1)
