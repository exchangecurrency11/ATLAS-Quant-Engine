#!/usr/bin/env python3
"""Probe official Binance Futures WS API for read-only historical kline query."""
import base64,os,json,socket,ssl,struct

host="ws-fapi.binance.com"
path="/ws-fapi/v1"

def frame(payload):
    data=payload.encode()
    mask=os.urandom(4)
    if len(data)<126:
        start=bytes([0x81,0x80|len(data)])
    else:
        start=bytes([0x81,0x80|126])+struct.pack("!H",len(data))
    return start+mask+bytes(b^mask[i%4] for i,b in enumerate(data))

def unframe(raw):
    if len(raw)<2:
        return "EMPTY"
    n=raw[1]&127
    start=2
    if n==126:
        n=struct.unpack("!H",raw[2:4])[0];start=4
    elif n==127:
        n=struct.unpack("!Q",raw[2:10])[0];start=10
    if raw[1]&128:
        return "MASKED_SERVER_MESSAGE"
    return raw[start:start+n].decode("utf-8","replace")[:1100]

try:
    with socket.create_connection((host,443),timeout=10) as sock:
        with ssl.create_default_context().wrap_socket(sock,server_hostname=host) as tls:
            tls.settimeout(10)
            key=base64.b64encode(os.urandom(16)).decode()
            upgrade=(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                     f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                     f"Sec-WebSocket-Version: 13\r\n\r\n")
            tls.sendall(upgrade.encode())
            reply=tls.recv(2000)
            print("ETH_WS_API_UPGRADE",reply.split(b"\r\n")[0].decode("latin1"))
            if b" 101 " not in reply.split(b"\r\n")[0]:raise SystemExit()
            for request in (
                {"id":"eth-price-test","method":"ticker.price","params":{"symbol":"ETHUSDT"}},
                {"id":"eth-klines-test","method":"klines","params":{"symbol":"ETHUSDT","interval":"1h","limit":3}},
            ):
                tls.sendall(frame(json.dumps(request,separators=(",",":"))))
                response=tls.recv(6000)
                print("ETH_WS_API_RESPONSE",request["method"],unframe(response))
except Exception as e:
    print("ETH_WS_API_FAILED",type(e).__name__,str(e)[:180])
