import json, collections, re
from lib import table_structure as ts
from lib.continuation_rows import merge_continuation_rows
from lib.table_utils import detect_header_row
P='pipelines/foi_pipeline/steps/'
res=json.load(open(P+'transform_disclosure_files/output.json'))['results']
errs={x['context']['file_url']:x['context']['failed_checks'] for x in json.load(open(P+'assess_table_structure/errors.json'))}
ov=set(json.load(open(P+'extract_disclosures_canonicalize/column_mappings.json')))
COMMON={'a','an','the','of','to','for','and','or','in','on','re','by','at','is','it','as','be','no','mr','ms','dr','ltd','na','sec','all','any','its'}
def stub_pair(a,n):
    if not (re.search(r"[A-Za-z]$",a) and re.match(r"[a-z]",n)): return False
    last=re.findall(r"[A-Za-z]+$",a)[0]; first=re.match(r"[a-z]+",n).group(0)
    return (len(last)<=3 and last.lower() not in COMMON) or (len(first)<=3 and first not in COMMON)
def score(rows, keep_hdr_in_denom):
    rows=rows[detect_header_row(rows):]
    header,data=ts._data_rows(merge_continuation_rows(rows)[0])
    hn=[ts._norm(c) for c in ts._trimmed(header)]
    isrep=[[ts._norm(c) for c in ts._trimmed(r)]==hn for r in data]
    rep=sum(isrep); total=len(data)
    data=[r for r,x in zip(data,isrep) if not x]
    n=len(data)
    if n==0: return ['min_rows'],0
    widths=[len(ts._trimmed(r)) for r in data]
    sub=[w for w,r in zip(widths,data) if len(ts._non_empty(r))>=3]
    mc=collections.Counter(sub) if sub else collections.Counter(widths)
    mw=max(mc,key=lambda w:(mc[w],w))
    if mw<2: return ['width_uniformity'],n
    rc=collections.Counter(len(r) for r in data); rm=max(rc,key=lambda w:(rc[w],w)); mx=max(mw,rm)
    uni=sum(1 for w,r in zip(widths,data) if w==mw or (len(r)>=mw and mw-2<=w<=mx and len(ts._non_empty(r))>=3))
    denom=total if keep_hdr_in_denom else n
    wu=(uni+(rep if keep_hdr_in_denom else 0))/denom
    fs=(sum(1 for r in data if 1<=len(ts._non_empty(r))<=2)/denom) if mw>=4 else 0
    cross=cells=0
    for row in [header]+data:
        tx=[ts._text(c) for c in row]
        for i,x in enumerate(tx):
            if not x.strip(): continue
            cells+=1
            if i+1<len(tx) and tx[i+1].strip() and stub_pair(x,tx[i+1]): cross+=1
    pur=ts._column_type_purity(data)
    th=ts.DEFAULT_THRESHOLDS; f=[]
    if n<max(1,th.min_rows): f.append('min_rows')
    if wu<th.min_width_uniformity: f.append('width_uniformity')
    if fs>th.max_fragment_share: f.append('fragment_share')
    if pur<th.min_column_type_purity: f.append('column_type_purity')
    if cross/cells>th.max_split_word_rate: f.append('split_word_rate')
    return f,n
for keep in (False,True):
    rec=collections.Counter(); rrows=collections.Counter(); newfail=collections.Counter(); still=collections.Counter()
    for r in res:
        if r.get('file_type')!='pdf' or not r.get('rows') or r['file_url'] in ov: continue
        u=r['file_url']; old=errs.get(u); f,n=score(r['rows'],keep)
        key='+'.join(sorted(old)) if old and len(old)<3 else ('3+' if old else None)
        if old and not f: rec[key]+=1; rrows[key]+=n
        if old and f: still[key]+=1
        if old is None and f: newfail['+'.join(f)]+=1
    print('header rows in denominator' if keep else 'header rows removed from denominator')
    print('  recovered',dict(rec),'rows',dict(rrows),'total rows',sum(rrows.values()))
    print('  still gated',dict(still))
    print('  newly failing',dict(newfail))
