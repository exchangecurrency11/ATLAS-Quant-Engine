#!/usr/bin/env python3
"""ETHUSDT Binance USD-M public REST connectivity probe (read-only, no keys)."""
import json
import urllib.error
import urllib.parse
import urllib.request

URL="https://fapi.binance.com/fapi/v1/klines"

for interval,limit in (("1h",750),("4h",300),("1d",300)):
    url=URL+"?"+urllib.parse.urlencode({"symbol":"ETHUSDT","interval":interval,"limit":limit})
    request=urllib.request.Request(url,headers={"User-Agent":"ETH-V7-paper-readonly/1.0","Accept":"application/json"},method="GET")
    try:
        with urllib.request.urlopen(request,timeout=15) as resp:
            data=json.loads(resp.read(400000))
            if not isinstance(data,list):
                raise ValueError("Expected list of klines")
            print("ETH_REST_PROBE",interval,"HTTP",resp.status,"rows",len(data),
                  "firstMs",data[0][0] if data else None,
                  "latestMs",data[-1][0] if data else None)
    except urllib.error.HTTPError as e:
        print("ETH_REST_PROBE",interval,"HTTP",e.code,"BLOCKED_OR_FAILED")
    except Exception as e:
        print("ETH_REST_PROBE",interval,"ERROR",type(e).__name__)
