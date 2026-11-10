#!/usr/bin/env python3
"""Probe immutable Binance USD-M SOLUSDT public data archive, no API keys/orders."""
import csv
import hashlib
import io
import json
import urllib.error
import urllib.request
import zipfile
ROOT="https://data.binance.vision/data/futures/um"
DATES=("2026-11-09","2026-11-08","2026-10-28")
KIND=[("metrics","", "metrics"),("fundingRate","", "fundingRate"),("klines","1h","1h"),("klines","5m","5m")]

def get(url,max_bytes=12_000_000):
    try:
        r=urllib.request.Request(url,headers={"User-Agent":"SOL-V7-QUALITY-RESEARCH/1.0"})
        with urllib.request.urlopen(r,timeout=18) as response:
            data=response.read(max_bytes+1)
            if len(data)>max_bytes: raise ValueError("TOO_LARGE")
            return data
    except urllib.error.HTTPError as e:
        return "HTTP_"+str(e.code)
    except Exception as e:
        return "ERROR_"+type(e).__name__

for date in DATES:
    for kind,interval,suffix in KIND:
        prefix=f"{ROOT}/daily/{kind}/SOLUSDT/"
        path=f"SOLUSDT-{suffix}-{date}.zip"
        if interval:prefix+=interval+"/"
        blob=get(prefix+path)
        if not isinstance(blob,bytes):
            print(json.dumps({"date":date,"type":kind+":"+interval,"status":blob}),flush=True)
            continue
        checksum=get(prefix+path+".CHECKSUM",max_bytes=3000)
        verified=(isinstance(checksum,bytes) and hashlib.sha256(blob).hexdigest()==checksum.decode().strip().split()[0].lower())
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                csvfiles=[f for f in archive.namelist() if f.endswith(".csv")]
                if len(csvfiles)!=1:raise ValueError("CSV_COUNT_NOT_ONE")
                with archive.open(csvfiles[0]) as raw:
                    reader=csv.reader(io.TextIOWrapper(raw,encoding="utf-8-sig"))
                    sample=[next(reader) for _ in range(3)]
                print(json.dumps({"date":date,"type":kind+":"+interval,"status":"ZIP_OK",
                                  "verified":verified,"bytes":len(blob),"csv_name":csvfiles[0],
                                  "sample":sample}),flush=True)
        except Exception as e:
            print(json.dumps({"date":date,"type":kind+":"+interval,"status":"INVALID_CSV:"+str(e)}),flush=True)
for month in ("2026-10","2026-09","2026-11"):
    url=f"{ROOT}/monthly/fundingRate/SOLUSDT/SOLUSDT-fundingRate-{month}.zip"
    blob=get(url)
    if not isinstance(blob,bytes):
        print(json.dumps({"month":month,"kind":"monthly_fundingRate","status":blob}),flush=True)
        continue
    cs=get(url+".CHECKSUM",max_bytes=3000)
    match=(isinstance(cs,bytes) and hashlib.sha256(blob).hexdigest()==cs.decode().split()[0].lower())
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names=[n for n in archive.namelist() if n.endswith(".csv")]
        with archive.open(names[0]) as src:
            records=csv.reader(io.TextIOWrapper(src,encoding="utf-8-sig"))
            sample=[next(records) for _ in range(3)]
    print(json.dumps({"month":month,"kind":"monthly_fundingRate","status":"ZIP_OK",
                      "sha256_verified":match,"samples":sample}),flush=True)

for label,url in [
    ("OI_REST","https://fapi.binance.com/futures/data/openInterestHist?symbol=SOLUSDT&period=5m&limit=5"),
    ("FUNDING_REST","https://fapi.binance.com/fapi/v1/fundingRate?symbol=SOLUSDT&limit=5")
]:
    b=get(url,max_bytes=3000)
    print(json.dumps({"probe":label,"status":b if isinstance(b,str) else "HTTP_OK","response":str(b)[:300] if isinstance(b,bytes) else ""}),flush=True)
