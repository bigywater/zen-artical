import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
import socket, struct
tee('m78'); reset()
class Raw:
    def __init__(self, port): self.s = socket.create_connection(('127.0.0.1', port)); self.rid = 1
    def cmd(self, doc):
        body = bson.encode(doc); msg = struct.pack('<I', 0) + b'\x00' + body; hdr = struct.pack('<iiii', 16 + len(msg), self.rid, 0, 2013); self.rid += 1
        self.s.sendall(hdr + msg); h = b''
        while len(h) < 16:
            x = self.s.recv(16 - len(h))
            if not x: raise ConnectionError('服务器关闭了连接(recv 返回空)')
            h += x
        ln = struct.unpack('<i', h[:4])[0]; data = b''
        while len(data) < ln - 16: data += self.s.recv(ln - 16 - len(data))
        return bson.decode(data[5:])
def threads(pid): return len(subprocess.run(['ps', '-M', '-p', str(pid)], capture_output=True, text=True).stdout.strip().split('\n')) - 1
def rss(pid): return int(subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()) / 1024
nd = Node('m78').start(); c = nd.client(); pid = nd.p.pid
def conns(): return c.admin.command('serverStatus')['connections']
def row(label):
    cn = conns(); print(f'  {label:<28}connections.current = {cn["current"]:>5},线程数 = {threads(pid):>5},RSS = {rss(pid):6.1f} MB')
print('== 一:每个连接一个线程吗?用原始 TCP 连接(各发一次 hello)把连接数从 0 加到 1,000,看 mongod 的线程数、RSS')
row('基线(只有我自己)')
socks = []; t0 = time.time()
for target in (100, 500, 1000):
    while len(socks) < target:
        r = Raw(nd.port); r.cmd({'hello': 1, '$db': 'admin'}); socks.append(r)
    time.sleep(0.5); row(f'再加到 {target} 个连接')
print(f'  建立 1,000 个连接(含各一次 hello)共 {time.time() - t0:.2f} 秒')
print('== 二:这些连接关掉之后,线程数、RSS 多久回落')
for r in socks: r.s.close()
socks = []
for w in (0.3, 2, 5): time.sleep(w if w == 0.3 else w - (0.3 if w == 2 else 2)); row(f'关闭后约 {w} 秒')
print('== 三:--maxConns 50(配置文件里叫 net.maxIncomingConnections):第 51 个及以后的连接会怎样')
nd.stop(); nd = Node('m78b', args=['--maxConns', '50'], clean=True).start(); c = nd.client(); pid = nd.p.pid
print('  serverStatus.connections: ' + str(dict(conns())))
socks = []; res = []
for i in range(60):
    try:
        r = Raw(nd.port); r.cmd({'hello': 1, '$db': 'admin'}); socks.append(r); res.append('ok')
    except Exception as ex: res.append(type(ex).__name__ + ':' + str(ex)[:40])
print(f'  依次建立 60 个连接并各发 hello:成功 {res.count("ok")} 个,失败 {60 - res.count("ok")} 个')
print('  失败的情况: ' + str(sorted(set(x for x in res if x != 'ok'))))
print('  服务器端: ' + str(dict(conns())))
lg = [l for l in nd.logs() if 'many' in json.dumps(l, default=str).lower() or 'maxconns' in json.dumps(l, default=str).lower()]
print(f'  日志里含 "too many" / maxConns 的条目数 = {len(lg)};最后一条: ' + (json.dumps({k: lg[-1].get(k) for k in ('s', 'c', 'id', 'msg')}, ensure_ascii=False) if lg else '(无)') + ((' attr = ' + json.dumps(lg[-1].get('attr'), default=str)[:150]) if lg else ''))
for r in socks: r.s.close()
print('== 四:available 是怎么来的:默认 与 --maxConns')
nd.stop(); nd = Node('m78c').start(); c = nd.client(); cn = conns(); print(f'  默认:current = {cn["current"]},available = {cn["available"]},current + available = {cn["current"] + cn["available"]}')
nd.stop(); nd = Node('m78d', args=['--maxConns', '1000']).start(); c = nd.client(); cn = conns(); print(f'  --maxConns 1000:current = {cn["current"]},available = {cn["available"]},current + available = {cn["current"] + cn["available"]}')
print('== 五:新建连接的代价:每次操作都新建 TCP 连接 + hello + find_one,对比复用一个连接(各 1,000 次)')
c.test.t.insert_one({'_id': 1})
r0 = Raw(nd.port)
def reuse(): r0.cmd({'find': 't', 'filter': {'_id': 1}, '$db': 'test'})
def fresh():
    r = Raw(nd.port); r.cmd({'hello': 1, '$db': 'admin'}); r.cmd({'find': 't', 'filter': {'_id': 1}, '$db': 'test'}); r.s.close()
def loop(f, n=1000):
    t0 = time.perf_counter()
    for _ in range(n): f()
    return (time.perf_counter() - t0) * 1000
a = loop(reuse); b = loop(fresh); a = loop(reuse); b = loop(fresh)
print(f'  复用一个连接:1,000 次 find 共 {a:.0f} ms(每次 {a:.0f} μs);每次新建连接:共 {b:.0f} ms(每次 {b:.0f} μs)')
print(f'  新建连接方式是复用的 {b / a:.1f} 倍')
print('== 六:connections 里的 current / active / threaded:200 个空闲连接 + 8 个正在跑慢查询的连接')
socks = []
for _ in range(200):
    r = Raw(nd.port); r.cmd({'hello': 1, '$db': 'admin'}); socks.append(r)
cls = [nd.client() for _ in range(8)]
for x in cls: x.admin.command('ping')
c.test.t.insert_many([{'_id': 100 + i} for i in range(5)])
def slow(cl):
    try: cl.test.command({'find': 't', 'filter': {'$where': 'sleep(1000) || true'}, 'limit': 1})
    except Exception: pass
time.sleep(1.5)
def show(label):
    cn = conns(); print(f'  {label}:current = {cn["current"]},active = {cn["active"]},threaded = {cn["threaded"]},awaitingTopologyChanges = {cn["awaitingTopologyChanges"]}')
show('200 个空闲原始连接 + 8 个已 ping 过的客户端,什么都没跑')
sl = [threading.Thread(target=slow, args=(x,), daemon=True) for x in cls]
for t in sl: t.start()
time.sleep(0.4); show('8 个慢查询正在跑')
for t in sl: t.join(30)
time.sleep(1.5); show('慢查询结束后')
nd.stop()
