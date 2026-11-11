/**
 * V9.1 official Binance USD-M public REST reachability probe.
 * RESEARCH ONLY - NOT DEPLOYED BY THIS REPO/WORKFLOW.
 * Does not modify existing Cloudflare worker, V7/V9 alerts or orders.
 * Fixed GET /probe only, exactly 3 known symbols, no API keys.
 * Operationally secure behind Cloudflare Access/rate limits before deployment.
 */
const SYMBOLS = Object.freeze(["BTCUSDT", "ETHUSDT", "SOLUSDT"]);
const KLINE_HOUR_MS = 3_600_000;
const TARGET_ENDPOINT = "https://fapi.binance.com/fapi/v1/klines";
const MAX_BODY_BYTES = 100_000;

function numeric(v,field) {
  const n = Number(v);
  if ((typeof v !== "string" && typeof v !== "number") || !Number.isFinite(n)) {
    throw new Error("BAD_FINITE_" + field);
  }
  return n;
}

function verifyLastFullyClosedKline(payload, nowMs) {
  if (!Array.isArray(payload) || payload.length < 2 || payload.length > 3) {
    throw new Error("WRONG_NUMBER_KLINES");
  }
  const target = Math.floor(nowMs / KLINE_HOUR_MS) * KLINE_HOUR_MS;
  const usable = [];
  for (const row of payload) {
    if (!Array.isArray(row) || row.length < 11) {
      throw new Error("MALFORMED_KLINE_ROW");
    }
    const begin = numeric(row[0],"OPEN_MS");
    const end = numeric(row[6],"END_MS");
    if (!Number.isInteger(begin) || !Number.isInteger(end) ||
        begin % KLINE_HOUR_MS !== 0 || end !== begin + KLINE_HOUR_MS - 1) {
      throw new Error("NONSTANDARD_UTC_FUTURES_KLINE_TIME");
    }
    if (begin + KLINE_HOUR_MS > target) continue; // NEVER read a forming candle.
    const o=numeric(row[1],"OPEN"), h=numeric(row[2],"HIGH");
    const l=numeric(row[3],"LOW"), c=numeric(row[4],"CLOSE");
    const vol=numeric(row[5],"VOLUME"), trades=numeric(row[8],"TRADES");
    const tbv=numeric(row[9],"TAKER_BUY_BASE");
    const q=numeric(row[7],"QUOTE_VOLUME"), tq=numeric(row[10],"TAKER_BUY_QUOTE");
    if (l <= 0 || h < Math.max(o,c) || l > Math.min(o,c) ||
        vol < 0 || !Number.isSafeInteger(trades) || trades < 0 ||
        tbv < 0 || tbv > vol || q < 0 || tq < 0 || tq > q) {
      throw new Error("INVALID_EXCHANGE_KLINE_OHLCV_OR_TAKER");
    }
    usable.push({openTimeMs:begin,closeTimeMs:end,open:o,high:h,low:l,
      close:c,volume:vol,quoteVolume:q,
      numberOfTrades:trades,takerBuyBase:tbv,takerBuyQuote:tq});
  }
  usable.sort((a,b)=>a.openTimeMs-b.openTimeMs);
  const last=usable.at(-1);
  if (!last || last.openTimeMs !== target - KLINE_HOUR_MS) {
    throw new Error("LAST_CLOSED_1H_NOT_FRESH");
  }
  return {
    exactClosed1HUTC:new Date(target).toISOString(),
    source:"Binance_USDM_Official_Public_REST",
    closedKline:last,
    noFormingCandlesUsed:true
  };
}

async function checkOne(symbol, nowMs, fetchImpl) {
  const query=new URLSearchParams({symbol,interval:"1h",limit:"3"});
  const url=TARGET_ENDPOINT+"?"+query.toString();
  try {
    const response=await fetchImpl(url,{method:"GET",headers:{
      "Accept":"application/json","Cache-Control":"no-cache"},
      signal:AbortSignal.timeout(8000)});
    if (!response || typeof response.status !== "number") {
      return {symbol,status:"NO_HTTP_RESPONSE"};
    }
    if (response.status===451) {
      return {symbol,status:"PUBLIC_BINANCE_RESTRICTED_HTTP_451",httpStatus:451};
    }
    if (!response.ok) {
      return {symbol,status:"PUBLIC_BINANCE_HTTP_UNAVAILABLE",httpStatus:response.status};
    }
    const body=await response.text();
    if (body.length>MAX_BODY_BYTES) {
      return {symbol,status:"PUBLIC_BINANCE_RESPONSE_TOO_LARGE"};
    }
    const checked=verifyLastFullyClosedKline(JSON.parse(body),nowMs);
    return {symbol,status:"OFFICIAL_CLOSED_1H_AVAILABLE",
      httpStatus:200,...checked};
  } catch (err) {
    // Do not expose provider error bodies, credentials, user info or stack traces.
    return {symbol,status:"PUBLIC_BINANCE_TRANSPORT_OR_VALIDATION_FAILED",
      failureCategory:err?.message?.startsWith("LAST_CLOSED")?"CANDLE_NOT_READY":
        (err instanceof SyntaxError?"UNEXPECTED_JSON":"NETWORK_OR_INVALID_DATA")};
  }
}

export async function probeAll(nowMs,{fetchImpl=fetch}={}) {
  const results=await Promise.all(SYMBOLS.map(s=>checkOne(s,nowMs,fetchImpl)));
  return {
    mode:"V91_BINANCE_READ_ONLY_CLOUDFLARE_REACHABILITY_PROBE",
    checkedAtUTC:new Date(nowMs).toISOString(),
    expectedLastClosed1HUTC:new Date(Math.floor(nowMs/KLINE_HOUR_MS)*KLINE_HOUR_MS).toISOString(),
    successAllThree:results.every(x=>x.status==="OFFICIAL_CLOSED_1H_AVAILABLE"),
    statusBySymbol:Object.fromEntries(results.map(x=>[x.symbol,x])),
    cannotClaimCoinalyzeParityUntilSameHourIsCompared:true,
    noProductionSignalOrOrders:true,
    noNotifications:true
  };
}

export default {
  async fetch(request,env) {
    const url=new URL(request.url);
    if (request.method!=="GET" || url.pathname!=="/probe" || url.search) {
      return new Response(JSON.stringify({status:"NOT_FOUND"}),{
        status:404,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});
    }
    // Do NOT deploy to a publicly unprotected endpoint: Access/rate limits
    // are required. This source file intentionally contains no credentials.
    const snapshot=await probeAll(Date.now());
    return new Response(JSON.stringify(snapshot),{
      status:200,headers:{"Content-Type":"application/json","Cache-Control":"no-store",
        "X-Content-Type-Options":"nosniff"}});
  }
};
