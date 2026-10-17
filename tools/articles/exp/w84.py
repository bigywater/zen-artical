import sys, os, re, struct, threading, statistics, errno, ssl; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
import hpack
tee('w84'); reset()
HOST = 'example.com'
FT = {0: 'DATA', 1: 'HEADERS', 2: 'PRIORITY', 3: 'RST_STREAM', 4: 'SETTINGS', 5: 'PUSH_PROMISE', 6: 'PING', 7: 'GOAWAY', 8: 'WINDOW_UPDATE', 9: 'CONTINUATION'}
FL = {0: {1: 'END_STREAM', 8: 'PADDED'}, 1: {1: 'END_STREAM', 4: 'END_HEADERS', 8: 'PADDED', 0x20: 'PRIORITY'}, 4: {1: 'ACK'}, 6: {1: 'ACK'}, 9: {4: 'END_HEADERS'}}
SET = {1: 'HEADER_TABLE_SIZE', 2: 'ENABLE_PUSH', 3: 'MAX_CONCURRENT_STREAMS', 4: 'INITIAL_WINDOW_SIZE', 5: 'MAX_FRAME_SIZE', 6: 'MAX_HEADER_LIST_SIZE'}
ERR = {0: 'NO_ERROR', 1: 'PROTOCOL_ERROR', 2: 'INTERNAL_ERROR', 3: 'FLOW_CONTROL_ERROR', 4: 'SETTINGS_TIMEOUT', 5: 'STREAM_CLOSED', 6: 'FRAME_SIZE_ERROR', 7: 'REFUSED_STREAM', 8: 'CANCEL', 9: 'COMPRESSION_ERROR', 0xb: 'ENHANCE_YOUR_CALM'}
def frame(t, flags, sid, payload): return struct.pack('>I', len(payload))[1:] + bytes([t, flags]) + struct.pack('>I', sid) + payload
def connect():
    ctx = ssl.create_default_context(); ctx.set_alpn_protocols(['h2']); s = socket.create_connection(('104.20.23.154', 443), timeout=8); ss = ctx.wrap_socket(s, server_hostname=HOST); ss.settimeout(4); return ss
class Rd:
    def __init__(self, s): self.s = s; self.buf = b''; self.t0 = time.time()
    def read_frame(self, tmo=3):
        self.s.settimeout(tmo)
        try:
            while len(self.buf) < 9: self.buf += self.recv()
            n = int.from_bytes(self.buf[:3], 'big')
            while len(self.buf) < 9 + n: self.buf += self.recv()
        except (socket.timeout, TimeoutError): return None
        t, fl = self.buf[3], self.buf[4]; sid = struct.unpack('>I', self.buf[5:9])[0] & 0x7fffffff; p = self.buf[9:9 + n]; self.buf = self.buf[9 + n:]; return t, fl, sid, p, n
    def recv(self):
        d = self.s.recv(65536)
        if not d: raise TimeoutError()
        return d
def flags_str(t, fl): return '+'.join(v for k, v in FL.get(t, {}).items() if fl & k) or '-'
def describe(t, fl, sid, p, n, dec=None):
    s = f'{FT.get(t, t):<13} 流 {sid:<2} 长度 {n:<5} 标志 {flags_str(t, fl)}'
    if t == 4 and not fl & 1: s += '  ' + ', '.join(f'{SET.get(i, i)}={v}' for i, v in (struct.unpack('>HI', p[j:j + 6]) for j in range(0, len(p), 6)))
    if t == 8: s += f'  窗口增量 {struct.unpack(">I", p)[0] & 0x7fffffff}'
    if t == 7: s += f'  最后处理的流 {struct.unpack(">I", p[:4])[0]},错误码 {ERR.get(struct.unpack(">I", p[4:8])[0], struct.unpack(">I", p[4:8])[0])},附加信息 {p[8:60]!r}'
    if t == 3: s += f'  错误码 {ERR.get(struct.unpack(">I", p)[0], struct.unpack(">I", p)[0])}'
    if t == 1 and dec:
        hs = dec.decode(p); s += '  头部 ' + ', '.join(f'{k}: {v[:28]}' for k, v in hs[:6]) + (f' …共 {len(hs)} 个' if len(hs) > 6 else '')
    return s

print('== 一:连接建立:TLS 里用 ALPN 协商出 h2 之后,客户端先发 24 字节的固定“前言”,再发 SETTINGS 帧。逐帧看双方的开场')
ss = connect(); print(f'  ALPN 协商结果:{ss.selected_alpn_protocol()};TLS {ss.version()}')
preface = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
my_settings = frame(4, 0, 0, struct.pack('>HI', 3, 100) + struct.pack('>HI', 4, 65535))
ss.sendall(preface + my_settings); rd = Rd(ss); dec = hpack.Decoder()
print(f'  客户端发出:前言 {preface!r}({len(preface)} 字节)+ 一个 SETTINGS 帧({len(my_settings)} 字节:9 字节帧头 + 2 个设置 × 6 字节)')
print(f'  SETTINGS 帧的字节:{my_settings.hex(" ")}')
print('    = 00 00 0c(长度 12)| 04(类型 SETTINGS)| 00(标志)| 00 00 00 00(流 0)| 00 03 00 00 00 64(MAX_CONCURRENT_STREAMS=100)| 00 04 00 00 ff ff(INITIAL_WINDOW_SIZE=65535)')
got = []
while True:
    f = rd.read_frame(1.5)
    if not f: break
    got.append(f); print(f'  服务器 → ' + describe(*f))
    if len(got) >= 6: break
ack_sent = False
for f in got:
    if f[0] == 4 and not f[1] & 1: ss.sendall(frame(4, 1, 0, b'')); ack_sent = True
print(f'  客户端对服务器的 SETTINGS 回了一个空的 SETTINGS ACK 帧({"已发送" if ack_sent else "未发送"}):9 字节 = 00 00 00 | 04 | 01 | 00 00 00 00')

print('== 二:一个 GET 请求在 HTTP/2 里是什么样:一个 HEADERS 帧(HPACK 压缩的头部);响应是 HEADERS + DATA 帧,带 END_STREAM 标志结束。和 HTTP/1.1 的文本请求比大小')
enc = hpack.Encoder(); hdrs = [(':method', 'GET'), (':scheme', 'https'), (':path', '/'), (':authority', HOST), ('user-agent', 'w84'), ('accept', '*/*')]
block = enc.encode(hdrs); req = frame(1, 5, 1, block)
ss.sendall(req); h1 = f'GET / HTTP/1.1\r\nHost: {HOST}\r\nUser-Agent: w84\r\nAccept: */*\r\n\r\n'.encode()
print(f'  请求:HEADERS 帧 流 1,标志 END_HEADERS+END_STREAM(没有消息体),头部块 {len(block)} 字节(HPACK),整个帧 {len(req)} 字节;等价的 HTTP/1.1 文本请求 {len(h1)} 字节')
print(f'  头部块的字节:{block.hex(" ")}')
tot = {'DATA': 0}; resp_frames = []
while True:
    f = rd.read_frame(2.5)
    if not f: break
    resp_frames.append(f)
    if f[2] == 1 and f[1] & 1: break
for f in resp_frames: print('  服务器 → ' + describe(*f, dec=dec if f[0] == 1 else None))
data = sum(f[4] for f in resp_frames if f[0] == 0); hdr_len = sum(f[4] for f in resp_frames if f[0] == 1)
print(f'  响应的头部块 {hdr_len} 字节(HPACK 压缩后),数据 {data} 字节;帧数 {len(resp_frames)};每个帧还要加 9 字节帧头')

print('== 三:两个请求同时在一个连接上:流 3 和流 5 的 HEADERS 连着发出去,看响应帧怎么交错(流 ID:客户端发起的流用奇数)')
req3 = frame(1, 5, 3, enc.encode(hdrs[:-1] + [(':path', '/')])) + frame(1, 5, 5, enc.encode(hdrs))
ss.sendall(req3); seq = []; done = set()
while len(done) < 2:
    f = rd.read_frame(3)
    if not f: break
    seq.append(f)
    if f[0] in (0, 1) and f[1] & 1 and f[2] in (3, 5): done.add(f[2])
print('  收到的帧序列(类型@流):' + ' '.join(f'{FT.get(f[0], f[0])}@{f[2]}' for f in seq))
print(f'  流 3 的帧 {sum(1 for f in seq if f[2] == 3)} 个,流 5 的帧 {sum(1 for f in seq if f[2] == 5)} 个;两条流各自以带 END_STREAM 标志的帧结束')

print('== 四:PING 帧:8 字节的任意载荷,对方必须原样返回并置 ACK 标志。用来测往返时间和保活。连发 5 个')
rtts = []
for i in range(5):
    t0 = time.time(); ss.sendall(frame(6, 0, 0, bytes([i]) * 8))
    while True:
        f = rd.read_frame(3)
        if not f: break
        if f[0] == 6 and f[1] & 1: rtts.append((time.time() - t0) * 1000); ok = f[3] == bytes([i]) * 8; break
print(f'  5 个 PING 的往返:{[round(x) for x in rtts]} ms;载荷原样返回:{ok};对照 TCP 握手约 {0:.0f}'.replace('对照 TCP 握手约 0', '这就是应用层(HTTP/2)能看到的往返时间'))

print('== 五:出错:发一个缺少必需伪头部(没有 :method)的 HEADERS,看服务器怎么回;另开一个新连接,以免弄坏前面的连接')
ss.close(); ss = connect(); ss.sendall(preface + frame(4, 0, 0, b'')); rd = Rd(ss)
bad = frame(1, 5, 1, hpack.Encoder().encode([(':scheme', 'https'), (':path', '/'), (':authority', HOST)])); ss.sendall(bad)
seq = []
while True:
    f = rd.read_frame(2.5)
    if not f: break
    seq.append(f)
    if f[0] in (3, 7): break
dec5 = hpack.Decoder()
for f in seq: print('  服务器 → ' + describe(*f, dec=dec5 if f[0] == 1 else None))
for f in seq:
    if f[0] == 0: print(f'    DATA 内容:{f[3][:120]!r}')
ss.close()
