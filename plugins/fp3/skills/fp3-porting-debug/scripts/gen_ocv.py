# SPDX-License-Identifier: MIT
# row-legend (centi-percent) and 25C column (3rd value, units of 100uV) from Kayo v1-lut
legend = [10000,9800,9600,9400,9200,9000,8800,8600,8400,8200,8000,7800,7600,7400,7200,
          7000,6800,6600,6400,6200,6000,5800,5600,5400,5200,5000,4800,4600,4400,4200,
          4000,3800,3600,3400,3200,3000,2800,2600,2400,2200,2000,1800,1600,1400,1200,
          1000,900,800,700,600,500,400,300,200,100,0]
# 3rd column (25C) values, in order top->bottom:
col25 = [43831,43575,43325,43082,42840,42600,42363,42129,41899,41673,41449,41240,41056,40869,40638,
         40381,40175,40019,39875,39732,39589,39402,39142,38910,38757,38636,38540,38464,38394,38325,
         38262,38203,38150,38102,38062,38025,37989,37953,37902,37815,37708,37596,37468,37312,37166,
         37070,37044,37031,37013,36976,36767,36348,35785,35019,33832,30000]
assert len(legend)==len(col25)==56, (len(legend),len(col25))
# build (uV, percent) pairs; percent = centi/100 (integer)
pairs=[]
for c,v in zip(legend,col25):
    pct = round(c/100)
    uv  = v*100
    pairs.append((uv,pct))
# must be strictly descending in ocv; check + dedupe percent collisions
prev=None
out=[]
for uv,pct in pairs:
    if prev is not None and uv>=prev:
        uv=prev-1000  # enforce strict descend (shouldn't trigger)
    out.append((uv,pct)); prev=uv
# emit dts
print("\t\tocv-capacity-celsius = <25>;")
line="\t\tocv-capacity-table-0 = "
chunks=[]
for uv,pct in out:
    chunks.append("<%d %d>"%(uv,pct))
# 4 per line
buf=""
res=[]
for i,ch in enumerate(chunks):
    buf += ch + (", " if i<len(chunks)-1 else ";")
    if (i+1)%4==0:
        res.append(buf); buf=""
if buf: res.append(buf)
print(line + res[0])
for r in res[1:]:
    print("\t\t\t"+r.lstrip())
