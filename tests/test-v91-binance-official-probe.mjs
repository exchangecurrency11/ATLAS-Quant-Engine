import test from "node:test";
import assert from "node:assert/strict";
import worker, {probeAll} from "../cloudflare/v91-binance-official-probe.js";

const H=3_600_000;
const target=Date.parse("2026-11-11T17:00:00Z");
const now=target + 25*60*1000;

function candle(openMs) {
  return [
    openMs,"100","105","95","101","1000",openMs+H-1,
    "101000",124,"400","40400","0"
  ];
}
const three=[
  candle(target-2*H),candle(target-H),candle(target)
];
const res=(body,status=200)=>({ok:status===200,status,text:async()=>JSON.stringify(body)});
const successful=async()=>res(three);

test("Fixed BTC ETH SOL exactly 1H CLOSED official public REST probes",async()=>{
  const urls=[];
  const out=await probeAll(now,{fetchImpl:async(url,opts)=>{
    urls.push(url);
    assert.equal(opts.method,"GET");
    assert.equal(opts.headers.Accept,"application/json");
    assert.equal(opts.headers["Cache-Control"],"no-cache");
    return successful();
  }});
  assert.equal(out.successAllThree,true);
  assert.equal(urls.length,3);
  assert.deepEqual(urls.map(u=>new URL(u).searchParams.get("symbol")).sort(),
    ["BTCUSDT","ETHUSDT","SOLUSDT"]);
  assert.ok(urls.every(u=>u.startsWith("https://fapi.binance.com/fapi/v1/klines?")));
  for(const z of Object.values(out.statusBySymbol)){
    assert.equal(z.status,"OFFICIAL_CLOSED_1H_AVAILABLE");
    assert.equal(z.closedKline.openTimeMs,target-H);
    assert.equal(z.closedKline.closeTimeMs,target-1);
    assert.equal(z.closedKline.numberOfTrades,124);
    assert.equal(z.closedKline.takerBuyBase,400);
    assert.equal(z.noFormingCandlesUsed,true);
  }
  assert.equal(out.cannotClaimCoinalyzeParityUntilSameHourIsCompared,true);
  assert.equal(out.noProductionSignalOrOrders,true);
});

test("HTTP 451 blocks claims of independent live exchange verification",async()=>{
  const a=await probeAll(now,{fetchImpl:async()=>res({message:"unavailable"},451)});
  assert.equal(a.successAllThree,false);
  assert.ok(Object.values(a.statusBySymbol).every(
    x=>x.status==="PUBLIC_BINANCE_RESTRICTED_HTTP_451" && x.httpStatus===451));
});

test("Stale old official candles cannot be counted as latest closed 1H",async()=>{
  const a=await probeAll(now,{fetchImpl:async()=>res([
    candle(target-3*H),candle(target-2*H)])});
  assert.equal(a.successAllThree,false);
  assert.ok(Object.values(a.statusBySymbol).every(
    x=>x.status==="PUBLIC_BINANCE_TRANSPORT_OR_VALIDATION_FAILED" &&
       x.failureCategory==="CANDLE_NOT_READY"));
});

test("Bad kline OHLC and provider JSON are rejected",async()=>{
  const bad=structuredClone(three);
  bad[1][2]="90";
  const a=await probeAll(now,{fetchImpl:async()=>res(bad)});
  assert.equal(a.successAllThree,false);
  assert.ok(Object.values(a.statusBySymbol).every(
    x=>x.status==="PUBLIC_BINANCE_TRANSPORT_OR_VALIDATION_FAILED"));
});

test("Unexpected source timestamp or future candle excluded, not promoted",async()=>{
  const b=structuredClone(three);
  b[1][6]=b[1][0]+H;
  const a=await probeAll(now,{fetchImpl:async()=>res(b)});
  assert.equal(a.successAllThree,false);
});

test("Network failure is fail-closed, no made-up success",async()=>{
  const a=await probeAll(now,{fetchImpl:async()=>{throw new Error("blocked");}});
  assert.equal(a.successAllThree,false);
});

test("Only fixed GET /probe path, query input cannot turn into proxy",async()=>{
  for(const request of [
    new Request("https://example.test/"),
    new Request("https://example.test/probe?symbol=DOGEUSDT"),
    new Request("https://example.test/probe",{method:"POST"}),
  ]) {
    const response=await worker.fetch(request,{});
    assert.equal(response.status,404);
  }
});
