import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
from etcdt import Etcd, b64
import base64 as b64mod
tee('v42'); reset()
print('etcd 3.7.2 的 watch:客户端可以指定 start_revision,从某个历史版本开始监听——断线重连时用“最后看到的 revision + 1”就不会丢事件;历史版本被 compaction 压缩掉之后就拿不到了,必须重新 list 再 watch。单节点,通过 HTTP/JSON 网关的流式 /v3/watch 操作(每个响应一行 JSON)')
import shutil; shutil.rmtree(TT / 'etcd_v42_0', ignore_errors=True); E1 = Etcd('v42', n=1).start()
dec = lambda s: b64mod.b64decode(s).decode()
def put(k, v): return int(E1.call(0, '/v3/kv/put', {'key': b64(k), 'value': b64(v)})[1]['header']['revision'])
def rev(): return int(E1.call(0, '/v3/kv/range', {'key': b64('/x'), 'limit': 1, 'serializable': False})[1]['header']['revision'])
class Watch:
    """流式 watch:后台线程读响应行,把 (收到时刻, 响应 JSON) 放进列表"""
    def __init__(self, prefix, start_rev=None, prev_kv=False, progress=False):
        self.msgs = []; self.lk = threading.Lock(); self.stop = False
        c = http.client.HTTPConnection('127.0.0.1', E1.CP[0], timeout=60); self.c = c
        cr = {'key': b64(prefix), 'range_end': b64(prefix[:-1] + chr(ord(prefix[-1]) + 1))}
        if start_rev: cr['start_revision'] = str(start_rev)
        if prev_kv: cr['prev_kv'] = True
        if progress: cr['progress_notify'] = True
        c.request('POST', '/v3/watch', json.dumps({'create_request': cr}), {'Content-Type': 'application/json'}); self.r = c.getresponse()
        self.th = threading.Thread(target=self._read, daemon=True); self.th.start()
    def _read(self):
        try:
            while not self.stop:
                line = self.r.fp.readline()
                if not line: break
                line = line.strip()
                if not line.startswith(b'{'): continue                    # 响应是 chunked 的:跳过块大小行和空行,只解析 JSON 行
                d = json.loads(line); t = time.perf_counter()
                with self.lk: self.msgs.append((t, d.get('result', d)))
        except Exception: pass
    def events(self):
        out = []
        with self.lk:
            for t, m in self.msgs:
                for e in m.get('events', []) or []: out.append((t, e.get('type', 'PUT'), dec(e['kv']['key']), int(e['kv']['mod_revision'])))
        return out
    def close(self):
        self.stop = True
        try: self.c.sock.shutdown(socket.SHUT_RDWR)          # 先断开 socket 叫醒阻塞在读上的线程;直接 close 会和读线程持有的缓冲区锁死锁
        except Exception: pass
        self.th.join(2)
        try: self.c.close()
        except Exception: pass

# ============ 一 ============
print('== 一:断线重连不丢事件。watcher 监听前缀 /svc/;写入线程持续 put /svc/k0…。第 1 阶段 watcher 在线,收到 10 个事件后断开;断开期间(2 s)又写入 50 个 key;之后重连。比较重连方式:(a) 从当前开始监听(不带 start_revision);(b) start_revision = 最后看到的 revision + 1')
rows = []
for name, use_rev in (('(a) 不带 start_revision(从现在开始)', False), ('(b) start_revision = 最后看到的 revision + 1', True)):
    base = f'/svc{int(use_rev)}/'; w = Watch(base)
    last = 0
    for i in range(10): last = put(base + f'k{i}', 'v')
    time.sleep(0.4); seen1 = w.events(); w.close(); last_seen = max(e[3] for e in seen1) if seen1 else 0
    for i in range(10, 60): put(base + f'k{i}', 'v')
    w2 = Watch(base, start_rev=(last_seen + 1) if use_rev else None); put(base + 'k60', 'v'); time.sleep(0.5); seen2 = w2.events(); w2.close()
    names1 = {e[2] for e in seen1}; names2 = {e[2] for e in seen2}; allseen = names1 | names2; missing = sum(1 for i in range(61) if base + f'k{i}' not in allseen); dup = len(names1 & names2)
    rows.append((name, len(seen1), len(seen2), f'{missing} / 61', dup))
table(rows, ['重连方式', '断开前收到', '重连后收到', '整个过程没收到的 key', '重复收到的 key'])
print('  从“现在”开始监听时,断开的 2 秒里写入的 50 个事件永远丢了;带上最后看到的 revision + 1 重连,事件一个不丢、也没有重复')

# ============ 二 ============
print('== 二:历史被压缩之后。写入 200 个版本的同一个 key,然后 compact 到当前 revision − 10。再分别从 (a) 一个被压缩掉的旧 revision;(b) 刚好等于 compact revision;(c) 比 compact revision 大 1 开始 watch。看 etcd 的回应')
for i in range(200): last = put('/cmp/key', f'v{i}')
cur = last; target = cur - 10
E1.call(0, '/v3/kv/compaction', {'revision': str(target), 'physical': True}); time.sleep(0.3)
rows = []
for name, sr in (('(a) 旧 revision(' + str(target - 50) + ')', target - 50), ('(b) 等于 compact revision(' + str(target) + ')', target), ('(c) compact revision + 1(' + str(target + 1) + ')', target + 1)):
    w = Watch('/cmp/', start_rev=sr); time.sleep(0.6)
    with w.lk: msgs = [m for t, m in w.msgs]
    first = next((m for m in msgs if m.get('canceled')), msgs[0] if msgs else {})
    evs = w.events(); w.close()
    rows.append((name, '被拒:canceled=%s,cancel_reason=%s,compact_revision=%s' % (first.get('canceled'), (first.get('cancel_reason') or '')[:40], first.get('compact_revision')) if first.get('canceled') else '创建成功', len(evs), f'{evs[0][3]}…{evs[-1][3]}' if evs else '-'))
table(rows, ['start_revision', '结果', '收到的事件数', '事件的 revision 范围'])
print(f'  当前 revision 是 {cur},compact 到了 {target}。比 compact revision 小的历史取不到,etcd 创建 watch 后立刻把它取消(canceled = true)并带上 compact_revision;客户端遇到这种错误必须重新 list(拿到当前全量和 header.revision),再从 header.revision + 1 开始 watch,中间被压缩掉的变化只能靠 list 的结果补上')

# ============ 三 ============
print('== 三:事件的原子性与顺序。(a) 一个 Txn 里同时 put 3 个 key,watcher 收到几个响应、几个事件、各自的 mod_revision;(b) 对前缀 delete range 删掉 3 个 key;(c) put 一个 key 的新值,请求 prev_kv 的 watcher 能看到旧值')
w = Watch('/tx/', prev_kv=True); time.sleep(0.2)
r = E1.call(0, '/v3/kv/txn', {'success': [{'request_put': {'key': b64(f'/tx/a{i}'), 'value': b64('1')}} for i in range(3)]})[1]; time.sleep(0.3)
E1.call(0, '/v3/kv/deleterange', {'key': b64('/tx/a'), 'range_end': b64('/tx/b')}); time.sleep(0.3)
put('/tx/z', 'old'); put('/tx/z', 'new'); time.sleep(0.3)
with w.lk: msgs = [m for t, m in w.msgs if m.get('events')]
rows = []
for k, m in enumerate(msgs):
    evs = m['events']; rows.append((k + 1, len(evs), ' '.join(f"{e.get('type', 'PUT')}:{dec(e['kv']['key'])}@{e['kv']['mod_revision']}" for e in evs), ' '.join(dec(e['prev_kv']['value']) if e.get('prev_kv') else '-' for e in evs)))
w.close()
table(rows, ['watch 响应序号', '事件数', '事件(类型:key@revision)', '各事件的 prev_kv 旧值'])
print('  一次 Txn 提交的 3 个 put 在同一个 revision 里,在同一个 watch 响应里一起到达;删除前缀产生一个 DELETE 事件对应一个 key,也在同一个 revision;prev_kv 让 watcher 在 PUT(第二次写 /tx/z)和 DELETE 事件里拿到修改前的值;第一次写 /tx/z 没有旧值,所以是 “-”')

# ============ 四 ============
print('== 四:有多少 watcher 时,事件多久送到。1 / 50 / 200 个 watcher 监听同一个前缀(每个一条 HTTP 流连接)。写入线程每 100 ms put 一次,共 30 次;记录从 put 返回到每个 watcher 收到该事件的延迟,汇总所有 watcher 的 p50 / p99 / 最大值')
rows = []
for nw in (1, 50, 200):
    ws = [Watch('/lat/') for _ in range(nw)]; time.sleep(0.5); sent = {}
    for i in range(30):
        t = time.perf_counter(); r = put('/lat/key', f'v{i}'); sent[r] = t; time.sleep(0.1)
    time.sleep(0.8); lat = []
    for w in ws:
        for t, typ, key, rv in w.events():
            if rv in sent: lat.append(t - sent[rv])
    for w in ws: w.close()
    rows.append((nw, len(lat), f'{pct(lat, 50) * 1000:.2f} ms', f'{pct(lat, 99) * 1000:.2f} ms', f'{max(lat) * 1000:.2f} ms'))
table(rows, ['watcher 数', '收到的事件总数', '延迟 p50', 'p99', '最大'])
E1.procs[0].kill()
