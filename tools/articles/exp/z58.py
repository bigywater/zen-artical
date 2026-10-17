import sys, os, time, json, re, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z58'); R = {}
def build(name, port, jvm=()):
    n = Node(name, port, conf={'snapCount': 300}, jvm=list(jvm)).start(); z = client(f'127.0.0.1:{port}')
    rs = [z.create_async(f'/n{i}', b'x' * 50) for i in range(1500)]; [r.get() for r in rs]; z.stop(); n.stop(); return n
def v2(n): return n.dir / 'data' / 'version-2'
def snaps(n): return sorted((p for p in v2(n).iterdir() if p.name.startswith('snapshot.')), key=lambda p: int(p.name.split('.')[1], 16))
def logs(n): return sorted((p for p in v2(n).iterdir() if p.name.startswith('log.')), key=lambda p: int(p.name.split('.')[1], 16))
def boot(n, jvm=None):
    if jvm is not None: n.jvm = list(jvm)
    n.start(wipe=False, wait=False)
    for _ in range(100):
        if n.p.poll() is not None: break
        try:
            if n.mode() == 'standalone': break
        except Exception: pass
        time.sleep(0.2)
    ok = n.alive() and n.mode() == 'standalone'; cnt = kv(n.four('mntr')).get('zk_znode_count') if ok else None
    L = [re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l)[:130] for l in n.log().splitlines() if 'trust.empty :' not in l and any(k in l for k in ('Invalid snapshot', 'Severe', 'No snapshot', 'CRC', 'corrupt', 'Failed to', 'Exiting JVM', 'EOF', 'Unreasonable', 'trust.empty', 'partial', 'inconsistent', 'No snapshot'))]
    code = n.p.poll(); n.stop(); return ok, cnt, code, L
def show(label, ok, cnt, code, L):
    print(f'  [{label}] 启动{"成功" if ok else "失败"}' + (f',znode 数 {cnt}' if ok else f',退出码 {code}')); [print('     日志:', l) for l in L[-5:]]
print('== 基准:写 1500 个 znode(snapCount=300,有多个快照与日志文件)后正常重启')
n = build('z58a', 7300); S = snaps(n); print('  快照:', [p.name for p in S][-3:], '日志:', len(logs(n)), '个'); ok, cnt, code, L = boot(n); show('正常', ok, cnt, code, L); R['base'] = dict(ok=ok, cnt=cnt)
print()
print('== 一:最新的快照被截断(只剩一半)')
n = build('z58b', 7301); S = snaps(n); last = S[-1]; sz = last.stat().st_size; os.truncate(last, sz // 2); print(f'  截断 {last.name}:{sz} → {sz // 2} 字节'); ok, cnt, code, L = boot(n); show('快照截断', ok, cnt, code, L); R['trunc'] = dict(ok=ok, cnt=cnt, log=L[-5:])
print()
print('== 二:最新的快照被清零(0 字节文件,比如磁盘满时写了一半)')
n = build('z58c', 7302); S = snaps(n); open(S[-1], 'wb').close(); ok, cnt, code, L = boot(n); show('快照 0 字节', ok, cnt, code, L); R['empty'] = dict(ok=ok, cnt=cnt, log=L[-5:])
print()
print('== 三:所有快照都被删掉,只剩事务日志(默认拒绝启动,避免静默丢数据;-Dzookeeper.snapshot.trust.empty=true 可以放行)')
n = build('z58d', 7303)
for p in snaps(n): p.unlink()
ok, cnt, code, L = boot(n); show('无快照(默认)', ok, cnt, code, L); R['nosnap'] = dict(ok=ok, cnt=cnt, code=code, log=L[-5:])
ok, cnt, code, L = boot(n, ['-Dzookeeper.snapshot.trust.empty=true']); show('无快照 + trust.empty=true', ok, cnt, code, L); R['nosnap_trust'] = dict(ok=ok, cnt=cnt)
print()
print('== 四:事务日志被破坏:(a) 破坏最后一条事务的尾部;(b) 破坏日志中间(后面还有有效事务)')
def corrupt(n, where):
    lg = logs(n)[-1]; raw = lg.read_bytes(); used = len(raw.rstrip(b'\0')); ba = bytearray(raw[:used + 16])
    pos = used - 24 if where == 'tail' else used // 2; ba[pos:pos + 16] = b'\xff' * 16
    with open(lg, 'r+b') as f: f.seek(0); f.write(bytes(ba))
    return lg.name, used, pos
n = build('z58e', 7304); nm, used, pos = corrupt(n, 'tail'); print(f'  (a) 破坏 {nm}(有效数据约 {used} 字节)末尾处偏移 {pos} 的 16 字节'); ok, cnt, code, L = boot(n); show('(a) 日志尾部损坏', ok, cnt, code, L); R['logtail'] = dict(ok=ok, cnt=cnt, code=code, log=L[-5:])
n = build('z58g', 7305); nm, used, pos = corrupt(n, 'mid'); print(f'  (b) 破坏 {nm}(有效数据约 {used} 字节)中间偏移 {pos} 的 16 字节'); ok, cnt, code, L = boot(n); show('(b) 日志中间损坏', ok, cnt, code, L); R['logmid'] = dict(ok=ok, cnt=cnt, code=code, log=L[-5:])
print()
n = build('z58h', 7306); lg = logs(n)[-1]; raw = lg.read_bytes(); used = len(raw.rstrip(b'\0')); ba = bytearray(raw); ba[used - 30:used] = b'\0' * 30
with open(lg, 'wb') as f: f.write(bytes(ba))
print(f'  (c) 模拟断电造成的「撕裂写」:把 {lg.name}(有效数据约 {used} 字节)最后 30 字节清零(最后一条事务只写了一半)'); ok, cnt, code, L = boot(n); show('(c) 最后一条事务写了一半', ok, cnt, code, L); R['logtorn'] = dict(ok=ok, cnt=cnt, code=code, log=L[-5:])
print()
print('== 五:集群里的补救:一个节点的数据损坏,清空它的数据目录让它从 leader 同步(见第 42 篇的 SNAP)')
e = Ensemble('z58f', 3, base=7310).start(); z = client(e.hosts()); [z.create(f'/n{i}', b'x') for i in range(200)]; z.stop()
f = e.followers()[0]; f.stop(); shutil.rmtree(f.dir / 'data' / 'version-2'); (f.dir / 'data' / 'version-2').mkdir(); f.start(wipe=False, wait=False)
for _ in range(100):
    if f.mode() == 'follower': break
    time.sleep(0.2)
print('  清空数据目录后重启,Mode =', f.mode(), '| znode 数', kv(f.four('mntr')).get('zk_znode_count'), '| leader 的 zk_znode_count =', kv(e.leader().four('mntr')).get('zk_znode_count')); R['wipe_rejoin'] = dict(mode=f.mode(), cnt=kv(f.four('mntr')).get('zk_znode_count'))
e.stop(); save('z58', R)
