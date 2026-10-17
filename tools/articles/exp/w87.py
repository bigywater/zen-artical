import sys, os, re, struct, threading, statistics, errno, base64, hashlib, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
from websockets.asyncio.server import serve
tee('w87'); reset()
GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
async def echo(ws):
    try:
        async for m in ws: await ws.send(m)
    except Exception: pass
port = lab_port()
def run_srv():
    async def main():
        async with serve(echo, '127.0.0.1', port, compression=None, ping_interval=None, max_size=None): await asyncio.Future()
    asyncio.run(main())
threading.Thread(target=run_srv, daemon=True).start(); time.sleep(0.8)
def hexs(b, n=40): return ' '.join(f'{x:02x}' for x in b[:n]) + (' …' if len(b) > n else '')
def mkframe(op, payload, fin=True, mask=True, key=b'\x37\xfa\x21\x3d'):
    b0 = (0x80 if fin else 0) | op; n = len(payload); mbit = 0x80 if mask else 0
    if n < 126: h = bytes([b0, mbit | n])
    elif n < 65536: h = bytes([b0, mbit | 126]) + struct.pack('>H', n)
    else: h = bytes([b0, mbit | 127]) + struct.pack('>Q', n)
    if mask: return h + key + bytes(p ^ key[i % 4] for i, p in enumerate(payload))
    return h + payload
def readn(s, n):
    b = b''
    while len(b) < n:
        d = s.recv(n - len(b))
        if not d: raise EOFError()
        b += d
    return b
def readframe(s):
    h = readn(s, 2); fin = h[0] >> 7; op = h[0] & 15; m = h[1] >> 7; n = h[1] & 0x7f; ext = b''
    if n == 126: ext = readn(s, 2); n = struct.unpack('>H', ext)[0]
    elif n == 127: ext = readn(s, 8); n = struct.unpack('>Q', ext)[0]
    key = readn(s, 4) if m else b''; p = readn(s, n)
    if m: p = bytes(x ^ key[i % 4] for i, x in enumerate(p))
    return fin, op, p, h + ext
OPN = {0: '继续', 1: '文本', 2: '二进制', 8: '关闭', 9: 'ping', 10: 'pong'}
def handshake(extra=b'', key=None):
    s = socket.create_connection(('127.0.0.1', port)); s.settimeout(5); key = key or base64.b64encode(os.urandom(16)).decode()
    req = f'GET /chat HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n'.encode() + extra + b'\r\n'
    s.sendall(req); buf = b''
    while b'\r\n\r\n' not in buf: buf += s.recv(4096)
    head, rest = buf.split(b'\r\n\r\n', 1); return s, key, req, head, rest

print('== 一:升级握手:一个普通的 HTTP/1.1 GET 请求带上 Upgrade: websocket;服务器回 101 Switching Protocols,并把 Sec-WebSocket-Key 变成 Sec-WebSocket-Accept(验证用,不是安全措施)')
s, key, req, head, rest = handshake()
print('  客户端发出:'); [print('    ' + l) for l in req.decode().strip().split('\r\n')]
print('  服务器回复:'); [print('    ' + l) for l in head.decode().split('\r\n')]
acc = re.search(r'(?i)sec-websocket-accept: *(\S+)', head.decode()).group(1); calc = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
print(f'  Accept 的计算:base64( SHA-1( Sec-WebSocket-Key + "{GUID}" ) ) = {calc};服务器给的 = {acc};{"一致" if acc == calc else "不一致"}')
print(f'  101 之后同一条 TCP 连接不再说 HTTP,双方改用 WebSocket 帧;握手后服务器多发的字节 {len(rest)} 个')

print('== 二:帧的格式:FIN + 操作码 + 掩码位 + 长度。发一个文本消息 "Hello"(客户端必须掩码),看线上字节,再看服务器的回显帧(服务器不掩码)')
f = mkframe(1, b'Hello'); s.sendall(f)
print(f'  客户端→服务器 帧({len(f)} 字节):{hexs(f)}')
print(f'    = 81(FIN=1,操作码 1 文本)| 85(掩码位 1,长度 5)| 37 fa 21 3d(4 字节掩码密钥)| {hexs(f[6:])}(= "Hello" 逐字节与密钥循环异或)')
print(f'    验证:{" ".join(f"{p:02x}^{f[2 + i % 4]:02x}={p ^ f[2 + i % 4]:02x}" for i, p in enumerate(f[6:]))} → {bytes(p ^ f[2 + i % 4] for i, p in enumerate(f[6:]))!r}')
fin, op, p, hdr = readframe(s); print(f'  服务器→客户端 帧({len(hdr) + len(p)} 字节):{hexs(hdr + p)} = 81 05 + "{p.decode()}"(没有掩码位,没有密钥,头部只有 {len(hdr)} 字节)')
print(f'  所以 5 字节的消息,客户端发的开销是 {len(f) - 5} 字节(2 + 4 掩码),服务器发的开销是 {len(hdr)} 字节')

print('== 三:长度的三种编码:≤125 字节用 7 位;126~65535 用 126 加 2 字节;更大用 127 加 8 字节。各发一个消息,看帧头占多少字节')
for n in (125, 126, 65535, 65536):
    f = mkframe(2, b'a' * n); s.sendall(f); fin, op, p, hdr = readframe(s)
    print(f'  载荷 {n:>6} 字节:客户端帧头 {len(f) - n} 字节(2 + {len(f) - n - 2 - 4} 长度扩展 + 4 掩码),服务器帧头 {len(hdr)} 字节(长度字段 {hdr[1] & 0x7f});回显正确 {len(p) == n}')

print('== 四:分片与控制帧:一个消息拆成 3 个帧(FIN=0 的文本帧 + 两个继续帧);在分片之间插入 ping,服务器要回 pong 并最终回显完整消息')
s.sendall(mkframe(1, b'frag-', fin=False)); s.sendall(mkframe(9, b'PING1')); s.sendall(mkframe(0, b'ment-', fin=False)); s.sendall(mkframe(0, b'end', fin=True))
got = []
for _ in range(2):
    fin, op, p, hdr = readframe(s); got.append((OPN[op], fin, p))
print(f'  服务器回来的帧:{got}')
print('  分片之间可以夹控制帧(ping / pong / close),但不能夹别的数据消息;服务器先回 pong,分片消息收齐之后才回显')

print('== 五:协议违规:客户端发了没有掩码的帧。规范要求服务器关闭连接,错误码 1002(协议错误)')
s2, k2, r2, h2_, rest2 = handshake(); s2.sendall(mkframe(1, b'bad', mask=False))
try:
    fin, op, p, hdr = readframe(s2); code = struct.unpack('>H', p[:2])[0] if len(p) >= 2 else None; print(f'  服务器回 {OPN.get(op, op)} 帧,关闭码 {code},原因 {p[2:].decode(errors="replace")!r}')
except Exception as e: print(f'  服务器直接断开连接:{type(e).__name__}')
s2.close()

print('== 六:正常关闭:客户端发 Close 帧(码 1000),服务器应该回一个 Close 帧,然后 TCP 才关。看这一来一回')
cf = mkframe(8, struct.pack('>H', 1000) + b'bye'); s.sendall(cf); fin, op, p, hdr = readframe(s)
print(f'  客户端→服务器 Close 帧:{hexs(cf)}(88 = FIN + 操作码 8;载荷 = 码 1000 + "bye")')
print(f'  服务器→客户端:{OPN.get(op)} 帧,载荷 {hexs(p)}(码 {struct.unpack(">H", p[:2])[0]});随后读到的是 {"连接关闭" if s.recv(10) == b"" else "还有数据"}')
s.close()
