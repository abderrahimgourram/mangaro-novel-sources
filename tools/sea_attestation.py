"""SeaNovel-only remote probe; never accepts an unsigned, stale or other-request result."""
import base64,hashlib,hmac,json,os,secrets,time
import requests
from validate import validate,require
URL='https://mangaro-seanovel-check.vercel.app/api/probe'

def check(bundle):
    validate(bundle)
    key=os.environ.get('SEANOVEL_ATTESTATION_SECRET','')
    require(len(key)==64 and all(c in '0123456789abcdef' for c in key),'SeaNovel attestation secret missing/invalid')
    candidate=json.dumps(bundle,ensure_ascii=False,separators=(',',':')).encode()
    digest=hashlib.sha256(candidate).hexdigest()
    nonce=secrets.token_hex(32);requested=int(time.time())
    raw=json.dumps({'protocol':1,'candidateSha256':digest,'revision':bundle['revision'],'requestedAt':requested,
                    'nonce':nonce,'bundle':base64.b64encode(candidate).decode()},separators=(',',':')).encode()
    mac=hmac.new(key.encode(),b'request-v1\n'+raw,hashlib.sha256).hexdigest()
    with requests.post(URL,data=raw,headers={'Content-Type':'application/json','Authorization':'HMAC-SHA256 '+mac},
                       timeout=(10,110),allow_redirects=False,stream=True) as response:
        response.raise_for_status()
        body=bytearray()
        for chunk in response.iter_content(4096):
            body.extend(chunk);require(len(body)<=16384,'Oversized attestation')
    wrapped=json.loads(body)
    require(set(wrapped)=={'payload','signature'})
    payload=base64.b64decode(wrapped['payload'],validate=True)
    expected=hmac.new(key.encode(),b'response-v1\n'+payload,hashlib.sha256).hexdigest()
    require(isinstance(wrapped['signature'],str) and hmac.compare_digest(expected,wrapped['signature']),'Invalid attestation signature')
    data=json.loads(payload)
    require(set(data)=={'protocol','candidateSha256','revision','requestedAt','nonce','timestamp','result'})
    require(type(data['protocol']) is int and data['protocol']==1)
    require(data['candidateSha256']==digest and type(data['revision']) is int and data['revision']==bundle['revision'])
    require(data['nonce']==nonce and type(data['requestedAt']) is int and data['requestedAt']==requested,'Replayed/mismatched result')
    now=int(time.time());stamp=data['timestamp']
    require(type(stamp) is int and requested-5<=stamp<=now+5 and now-stamp<=120 and now-requested<=120,'Stale attestation')
    result=data['result']
    require(isinstance(result,dict) and result.get('domain')=='seanovel.org' and result.get('status')=='healthy')
    require(all(result.get(x) is True for x in ('catalog','search','details','chapters','text')),'SeaNovel stage failed')
    for field,minimum,maximum in [('catalog_count',1,1000),('chapter_count',1,100000),('paragraphs',4,100000),('text_characters',501,8*1024*1024)]:
        value=result.get(field);require(type(value) is int and minimum<=value<=maximum,'Invalid probe counts')
    return dict(result,rulesSha256=digest,revision=bundle['revision'],attestedAt=stamp,requestNonce=nonce,attestationVerified=True)
