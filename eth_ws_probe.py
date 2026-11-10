#!/usr/bin/env python3
"""Read-only public Binance Futures websocket HTTP handshake diagnostic."""
import base64,os,socket,ssl
for host in ("fstream.binance.com","fstream.binancefuture.com"):
    try:
        raw=socket.create_connection((host,443),timeout=9)
        with ssl.create_default_context().wrap_socket(raw,server_hostname=host) as conn:
            key=base64.b64encode(os.urandom(16)).decode()
            request=("GET /ws/ethusdt@kline_1h HTTP/1.1\r\nHost: "+host+
                     "\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"+
                     "Sec-WebSocket-Key: "+key+"\r\nSec-WebSocket-Version: 13\r\n\r\n")
            conn.sendall(request.encode())
            response=conn.recv(2048).decode("latin1","replace")
            print("ETH_FUTURES_WS",host,"STATUS",response.splitlines()[0] if response else "EMPTY")
    except Exception as e:
        print("ETH_FUTURES_WS",host,"ERROR",type(e).__name__)
