#!/usr/bin/env python3
"""Read-only official Binance USD-M Futures WebSocket API request/response probe."""
import base64,os,json,socket,ssl,struct

host="ws-fapi.binance.com"
path="/ws-fapi/v1"

def client_frame(payload):
    data=payload.encode()
    mask=os.urandom(4)
    if len(data)<126: hdr=bytes([0x81,0x80|len(data)])
    elif len(data)<65536: hdr=b"\x81\xfe"+struct.pack("!H",len(data))
    else: hdr=b"\x81\xff"+struct.pack("!Q",len(data))
    return hdr+mask+bytes(b^mask[i%4] for i,b in enumerate(data))

def frame_from(reader):
    header=reader.read(2)
    if len(header)<2:raise EOFError("WS header missing")
    op=header[0]&15
    n=header[1]&127
    if n==126:n=struct.unpack("!H",reader.read(2))[0]
    elif n==127:n=struct.unpack("!Q",reader.read(8))[0]
    if n>1000000:raise ValueError("Oversized WS frame")
    mask=reader.read(4) if header[1]&128 else b""
    data=reader.read(n)
    if len(data)<n:raise EOFError("Partial WS message")
    if mask:data=bytes(b^mask[i%4] for i,b in enumerate(data))
    return op,data

try:
    with socket.create_connection((host,443),timeout=10) as sock:
        with ssl.create_default_context().wrap_socket(sock,server_hostname=host) as tls:
            tls.settimeout(10)
            key=base64.b64encode(os.urandom(16)).decode()
            upgrade=(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                     f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                     f"Sec-WebSocket-Version: 13\r\n\r\n")
            tls.sendall(upgrade.encode())
            reader=tls.makefile("rb")
            status=reader.readline().decode("latin1").strip()
            print("ETH_WS_API_UPGRADE",status,flush=True)
            while True:
                line=reader.readline()
                if not line or line==b"\r\n":break
            if "101" not in status:raise SystemExit()
            for req in (
                {"id":"eth-price-test","method":"ticker.price","params":{"symbol":"ETHUSDT"}},
                {"id":"eth-klines-test","method":"klines","params":{"symbol":"ETHUSDT","interval":"1h","limit":3}},
            ):
                tls.sendall(client_frame(json.dumps(req,separators=(",",":"))))
                for _ in range(20):
                    op,payload=frame_from(reader)
                    if op==9:
                        tls.sendall(client_frame(payload.decode("utf-8","replace")))
                        continue
                    if op!=1:continue
                    message=json.loads(payload)
                    if message.get("id")==req["id"]:
                        print("ETH_WS_API_RESPONSE",req["method"],str(message)[:1800],flush=True)
                        break
                else:
                    print("ETH_WS_API_RESPONSE",req["method"],"NOT_RECEIVED",flush=True)
except Exception as e:
    print("ETH_WS_API_FAILED",type(e).__name__,str(e)[:180],flush=True)
