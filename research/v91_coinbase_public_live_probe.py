#!/usr/bin/env python3
"""V9.1 Coinbase market-data network probe; NO KEYS, NO ORDERS, NO SIGNALS.

GitHub-only research. All requests are fixed to public official Coinbase endpoints.
Coinbase Exchange SPOT (USD) is NOT Binance USD-M or Coinbase INTX PERP (USDC).
"""
import datetime as dt
import json
import math
import urllib.error
import urllib.parse
import urllib.request

SYMBOLS = ("BTC", "ETH", "SOL")
ONE_HOUR = 3600
SPOT_HOST = "https://api.exchange.coinbase.com"
PERP_HOST = "https://api.international.coinbase.com"
MAX_RESPONSE_BYTES = 500_000
TIMEOUT_SECONDS = 9


def utc(ts):
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def read_public_json(url, open_url=urllib.request.urlopen):
    req = urllib.request.Request(
        url, headers={
            "Accept": "application/json",
            "User-Agent": "V91-Coinbase-Public-Market-Data-Research-ReadOnly/1.0",
        }, method="GET")
    try:
        with open_url(req, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            if status != 200:
                return {"status": "HTTP_UNAVAILABLE", "httpCode": status}
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                return {"status": "RESPONSE_TOO_LARGE", "httpCode": 200}
            try:
                return {"status": "JSON_RECEIVED", "httpCode": 200, "_payload": json.loads(raw)}
            except (ValueError, UnicodeDecodeError):
                return {"status": "INVALID_JSON", "httpCode": 200}
    except urllib.error.HTTPError as e:
        return {"status": "HTTP_UNAVAILABLE", "httpCode": e.code}
    except (OSError, TimeoutError, urllib.error.URLError) as e:
        return {"status": "TRANSPORT_UNAVAILABLE", "errorClass": type(e).__name__}


def valid_positive(v):
    try:
        x = float(v)
        return x if math.isfinite(x) and x > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def inspect_spot_ticker(reply, now):
    if reply.get("status") != "JSON_RECEIVED":
        return reply
    payload = reply["_payload"]
    if not isinstance(payload, dict):
        return {"status": "BAD_TICKER_SHAPE", "httpCode": 200}
    price = valid_positive(payload.get("price"))
    try:
        observed_at = dt.datetime.fromisoformat(str(payload["time"]).replace("Z", "+00:00"))
        if observed_at.tzinfo is None:
            raise ValueError("missing UTC timezone")
        age = now - observed_at.timestamp()
    except (TypeError, KeyError, ValueError, OverflowError):
        return {"status": "BAD_TICKER_TIME", "httpCode": 200}
    if price is None or age < -60 or age > 600:
        return {"status": "TICKER_INVALID_OR_STALE", "httpCode": 200,
                "observedUTC": utc(observed_at.timestamp())}
    return {"status": "FRESH_COINBASE_SPOT_TICKER", "httpCode": 200,
            "spotUSD": price, "observedUTC": utc(observed_at.timestamp()),
            "tradeAgeSeconds": round(age, 1)}


def inspect_spot_candles(reply, last_closed_hour):
    if reply.get("status") != "JSON_RECEIVED":
        return reply
    candles = reply["_payload"]
    if not isinstance(candles, list) or not candles:
        return {"status": "BAD_CANDLE_SHAPE", "httpCode": 200}
    observed = []
    for row in candles:
        if not isinstance(row, list) or len(row) < 6:
            return {"status": "BAD_CANDLE_SHAPE", "httpCode": 200}
        try:
            stamp = int(row[0])
        except (TypeError, ValueError):
            return {"status": "BAD_CANDLE_TIME", "httpCode": 200}
        if stamp != last_closed_hour - ONE_HOUR:
            continue
        lows, highs, opens, closes, vols = map(float, row[1:6])
        if not (all(map(math.isfinite, [lows, highs, opens, closes, vols])) and
                lows > 0 and lows <= min(opens, closes) and
                max(opens, closes) <= highs and vols >= 0):
            return {"status": "BAD_CLOSED_1H_OHLCV", "httpCode": 200}
        observed.append({"openTimeUTC": utc(stamp), "closeTimeUTC": utc(stamp+ONE_HOUR),
                         "open": opens, "high": highs, "low": lows,
                         "close": closes, "spotBaseVolume": vols})
    if len(observed) != 1:
        return {"status": "LAST_CLOSED_1H_MISSING_OR_DUPLICATE",
                "httpCode": 200}
    return {"status": "VALID_COINBASE_SPOT_CLOSED_1H", "httpCode": 200,
            "candle": observed[0]}


def inspect_intx_quote(reply):
    if reply.get("status") != "JSON_RECEIVED":
        return reply
    payload = reply["_payload"]
    # A successful public HTTP response must still have a real market-data object.
    if not isinstance(payload, dict) or not payload:
        return {"status": "INTX_QUOTE_INVALID_RESPONSE", "httpCode": 200}
    # This is only a reachability check; not a verified fresh PERP quote.
    return {"status": "INTX_PUBLIC_PERP_QUOTE_ENDPOINT_REACHABLE_UNVERIFIED",
            "httpCode": 200, "receivedObjectKeys": sorted(payload.keys())[:16]}


def run_probe(now=None, fetch=read_public_json):
    if now is None:
        now = dt.datetime.now(dt.timezone.utc).timestamp()
    close = int(now)//ONE_HOUR*ONE_HOUR
    report = {
        "mode": "V91_COINBASE_PUBLIC_READONLY_GITHUB_NETWORK_PROBE",
        "checkedUTC": utc(now), "expectedLastClosed1HUTC": utc(close),
        "spotExchange": {"venue": "COINBASE_EXCHANGE_SPOT", "quote": "USD"},
        "perpetualExchange": {"venue": "COINBASE_INTERNATIONAL_PERPETUAL",
                              "quote": "USDC"},
        "assets": {}, "allThreeSpotFreshAndClosed": False,
        "allThreePerpPublicQuotesReachable": False,
        "binancePerpParityProven": False, "orders": False,
        "alerts": False, "v7OrV91ProductionModified": False
    }
    for asset in SYMBOLS:
        pair = f"{asset}-USD"
        product = f"{asset}-PERP"
        ticker_url = f"{SPOT_HOST}/products/{pair}/ticker"
        params = urllib.parse.urlencode({
            "start": utc(close-4*ONE_HOUR), "end": utc(close),
            "granularity": "3600"
        })
        candle_url = f"{SPOT_HOST}/products/{pair}/candles?{params}"
        perp_url = f"{PERP_HOST}/api/v1/instruments/{product}/quote"
        spot_ticker = inspect_spot_ticker(fetch(ticker_url), now)
        spot_1h = inspect_spot_candles(fetch(candle_url), close)
        intx_quote = inspect_intx_quote(fetch(perp_url))
        report["assets"][asset] = {
            "coinbaseSpotTicker": spot_ticker,
            "coinbaseSpotClosed1H": spot_1h,
            "coinbaseIntxPerpQuote": intx_quote
        }
    report["allThreeSpotFreshAndClosed"] = all(
        r["coinbaseSpotTicker"]["status"] == "FRESH_COINBASE_SPOT_TICKER"
        and r["coinbaseSpotClosed1H"]["status"] == "VALID_COINBASE_SPOT_CLOSED_1H"
        for r in report["assets"].values())
    report["allThreePerpPublicQuotesReachable"] = all(
        r["coinbaseIntxPerpQuote"]["status"] ==
        "INTX_PUBLIC_PERP_QUOTE_ENDPOINT_REACHABLE_UNVERIFIED"
        for r in report["assets"].values())
    return report


if __name__ == "__main__":
    print(json.dumps(run_probe(), indent=2), flush=True)
