import sys, os, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml import *
from pymongo import monitoring
from pymongo.errors import CursorNotFound, OperationFailure
tee('m54'); reset()
n = Node('m54'); n.start()
class Spy(monitoring.CommandListener):
    def __init__(self): self.cmds = []
    def started(self, e): pass
    def succeeded(self, e):
        if e.command_name in ('find', 'getMore'):
            cur = e.reply.get('cursor', {}); b = cur.get('firstBatch', cur.get('nextBatch', [])); self.cmds.append((e.command_name, len(b), cur.get('id', 0) != 0, e.duration_micros / 1000))
    def failed(self, e): pass
spy = Spy(); c = MongoClient(n.uri, directConnection=True, event_listeners=[spy]); db = c.test
N = 100000
fill(db.t, N, lambda i: {'_id': i, 'k': i, 'pad': 'x' * 200}, batch=20000)
print(f'== 一:{N:,} 个文档(每个约 230 字节)。默认的 find:第一批多少个?之后每个 getMore 多少个?')
spy.cmds.clear(); sum(1 for _ in db.t.find({})); cm = spy.cmds[:]
print(f'  共 {len(cm)} 条命令(1 个 find + {len(cm) - 1} 个 getMore);第一批 {cm[0][1]} 个;之后每批: {[x[1] for x in cm[1:6]]} …;最后一批 {cm[-1][1]} 个')
print(f'  总共读到 {sum(x[1] for x in cm):,} 个文档')
print('== 二:batchSize 越小往返越多:读完 10 万个文档(各 5 次中位数)')
print(f'  {"batch_size":>12}{"命令数":>8}{"耗时":>12}')
for bs in (10, 100, 1000, 10000, 0):
    spy.cmds.clear(); sum(1 for _ in db.t.find({}, batch_size=bs)); nc = len(spy.cmds)
    t = bench(lambda: sum(1 for _ in db.t.find({}, {'pad': 0}, batch_size=bs)), 5)
    print(f'  {bs if bs else "默认":>12}{nc:>8}{fm(t):>12}')
print('== 三:没读完的游标占着服务端资源:serverStatus().metrics.cursor.open;close() 之后释放')
msh(n, 'db.serverStatus().metrics.cursor.open', note='读之前')
cur = db.t.find({}, batch_size=10); next(cur)
msh(n, 'db.serverStatus().metrics.cursor.open', note='开了一个游标、只读了第一条之后')
cur.close()
msh(n, 'db.serverStatus().metrics.cursor.open', note='cur.close() 之后')
print('== 四:游标空闲超时:参数 cursorTimeoutMillis 默认 10 分钟;为了观察调成 3 秒。空闲多久之后 getMore 失败?')
msh(n, 'db.adminCommand({getParameter: 1, cursorTimeoutMillis: 1}).cursorTimeoutMillis', note='默认值(毫秒)')
msh(n, 'var r = db.adminCommand({setParameter: 1, cursorTimeoutMillis: 3000}); r.was')
import socket, struct
class Raw:
    """极简 OP_MSG 客户端:不带 lsid 的命令(pymongo 的游标总是绑定隐式会话,会话里的游标不受 cursorTimeoutMillis 管)。"""
    def __init__(self, port): self.s = socket.create_connection(('127.0.0.1', port)); self.rid = 1
    def cmd(self, doc):
        body = bson.encode(doc); msg = struct.pack('<I', 0) + b'\x00' + body; hdr = struct.pack('<iiii', 16 + len(msg), self.rid, 0, 2013); self.rid += 1
        self.s.sendall(hdr + msg); h = b''
        while len(h) < 16: h += self.s.recv(16 - len(h))
        ln = struct.unpack('<i', h[:4])[0]; data = b''
        while len(data) < ln - 16: data += self.s.recv(ln - 16 - len(data))
        return bson.decode(data[5:])
rw = Raw(n.port)
curs = []
for _ in range(5):
    r = rw.cmd({'find': 't', 'filter': {}, 'batchSize': 10, '$db': 'test'}); curs.append(r['cursor']['id'])
t0 = time.perf_counter(); print(f'  不带 lsid 的 find(batchSize 10)开了 5 个游标;每个游标只在指定的空闲时间点做一次 getMore(之前不碰它,因为每次 getMore 都会重置空闲计时):')
for idle, cid in zip((2, 5, 8, 12, 20), curs):
    time.sleep(max(0, idle - (time.perf_counter() - t0)))
    r3 = rw.cmd({'getMore': cid, 'collection': 't', 'batchSize': 10, '$db': 'test'}); el = time.perf_counter() - t0
    print(f'    空闲 {el:4.1f} s 后 getMore:' + (f'成功(返回 {len(r3["cursor"]["nextBatch"])} 个)' if r3.get('ok') == 1 else f'失败 code={r3.get("code")}({r3.get("codeName")}): {r3.get("errmsg")[:60]}'))
print('  对照:pymongo 的游标(隐式会话)空闲 15 秒后(超过 3 秒的游标超时)仍然可用:', end='')
cur = db.t.find({}, batch_size=10); [next(cur) for _ in range(10)]; time.sleep(15)
try: [next(cur) for _ in range(10)]; print('可以继续读(游标绑定在会话上,由会话超时管理,默认 30 分钟)')
except CursorNotFound: print('也被回收了')
cur.close()
print('== 五:noCursorTimeout:永不超时,但要自己 close,否则一直占着(直到会话 30 分钟过期或服务重启)')
cur = db.t.find({}, batch_size=10, no_cursor_timeout=True); [next(cur) for _ in range(10)]
time.sleep(8)
try: [next(cur) for _ in range(10)]; print('  no_cursor_timeout 的游标空闲 8 秒(超过 cursorTimeoutMillis 3 秒)后仍可继续读')
except CursorNotFound: print('  仍被回收?')
msh(n, 'var o = db.serverStatus().metrics.cursor.open; ({noTimeout: o.noTimeout, total: o.total})', note='serverStatus 里 noTimeout 的游标数')
cur.close()
msh(n, 'db.adminCommand({setParameter: 1, cursorTimeoutMillis: 600000}).was')
print('== 六:游标不是快照:迭代期间别的线程修改已读过的文档的排序键,同一个文档会被读到两次')
fill(db.s, 20000, lambda i: {'_id': i, 'k': i}, batch=20000); db.s.create_index('k')
stop = threading.Event()
def mover():
    cc = n.client().test.s; j = 0
    while not stop.is_set() and j < 4000:
        cc.update_one({'_id': j}, {'$set': {'k': 100000 + j}}); j += 1
th = threading.Thread(target=mover); seen = []
cur = db.s.find({}, {'k': 1}).sort('k', 1).batch_size(500)
th.start()
for d in cur: seen.append(d['_id']); time.sleep(0.0002)
stop.set(); th.join()
dups = len(seen) - len(set(seen))
print(f'  按 k 排序遍历 {db.s.count_documents({}):,} 个文档时,另一线程把已经读过的文档的 k 改大:共读到 {len(seen):,} 个,其中同一个 _id 重复出现 {dups:,} 次(不同 _id {len(set(seen)):,} 个)')
n.stop()
