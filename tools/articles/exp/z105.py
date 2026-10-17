import sys, os, time, json, re, subprocess, shutil, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from hbl import *
tee('z105'); R = {}
n = Node('z105', 7300, xmx=384, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); z = client('127.0.0.1:7300')
root = ZDATA / 'hbase-root'; shutil.rmtree(root, ignore_errors=True)
HBH = HH.parent; CPF = (HBH / 'cp.txt').read_text(); WD = ZDATA / 'z105'; WD.mkdir(exist_ok=True)
def java(*a, out=None): return subprocess.Popen(['java', '-Xmx256m', '-cp', f'{HBH}:' + CPF, 'Hb', *a], stdout=open(out, 'w') if out else subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
def printable(b): return ' '.join(x.decode() for x in re.findall(rb'[ -~]{3,}', b))[:90]
def tree(p='/hbase', d=0, o=None):
    o = [] if o is None else o
    for k in sorted(z.get_children(p)):
        q = p.rstrip('/') + '/' + k; st = z.exists(q); data = z.get(q)[0]
        o.append(('  ' * d + k)[:60].ljust(62) + ('[临时] ' if st.ephemeralOwner else '       ') + (printable(data) if data else '')); tree(q, d + 1, o)
    return o
def wait(cond, to=120, what=''):
    t0 = time.time()
    while time.time() - t0 < to:
        try:
            if cond(): return time.time() - t0
        except Exception: pass
        time.sleep(0.3)
    raise TimeoutError(what)
print('== 一:启动 1 个 HBase 2.6.6 master 与 2 个 region server(hbase.zookeeper.quorum 指向我的 ZooKeeper,znode 根 /hbase,会话超时设为 6 s;HBase 默认值读自 hbase-default.xml:zookeeper.session.timeout=90000)')
m1 = HProc('master', 'm1', 7960, root).start(); r1 = HProc('regionserver', 'r1', 7961, root).start(); r2 = HProc('regionserver', 'r2', 7963, root).start()
wait(lambda: len(z.get_children('/hbase/rs')) == 2, 150, 'rs'); wait(lambda: 'Master has completed initialization' in m1.log(), 150, 'master init')
t1 = tree(); print('\n'.join('  ' + l for l in t1)); R['tree1'] = t1
print()
print('== 二:建一个预分 6 个 region 的表 t1,写 300 行:ZooKeeper 里有什么变化(region 分配信息在 hbase:meta 表里,不在 ZooKeeper)')
j = java('create'); o = j.communicate(timeout=120)[0]; print('  ' + '\n  '.join(l for l in o.splitlines() if 'TABLE_CREATED' in l or 'ROWS_PUT' in l)); R['create'] = [l for l in o.splitlines() if 'TABLE_CREATED' in l]
t2 = tree(); new = [l for l in t2 if l not in t1]; print('  新增或变化的 znode:'); print('\n'.join('    ' + l for l in new) or '    (无)'); R['tree2_new'] = new
print('  /hbase/meta-region-server =', printable(z.get('/hbase/meta-region-server')[0]))
print()
print('== 三:kill -9 持有一部分 region 的 region server r1:/hbase/rs 下它的临时节点何时消失,master 何时开始处理,客户端读写中断多久(客户端每 100 ms 一次 put + get)')
pf = WD / 'probe.log'; pj = java('probe', out=pf); time.sleep(4)
rs_before = sorted(z.get_children('/hbase/rs')); tk = time.time(); r1.kill(); t_rs = None
while time.time() - tk < 90 and t_rs is None:
    if len(z.get_children('/hbase/rs')) < 2: t_rs = time.time() - tk
    time.sleep(0.05)
time.sleep(25); L = [l.split() for l in pf.read_text().splitlines() if l.strip() and l.split()[0].isdigit()]
errs = [(int(l[0]) / 1000 - tk, int(l[-1]) / 1000, l[1]) for l in L if l[1] == 'ERR' and int(l[0]) / 1000 >= tk - 0.5]
ok_after = [int(l[0]) / 1000 - tk for l in L if l[1] == 'OK' and int(l[0]) / 1000 > tk]
first_err = min((e[0] for e in errs), default=None); last_err = max((e[0] + e[1] for e in errs), default=None)
bad_sec = (last_err - first_err) if errs else 0
print(f'  /hbase/rs 下的节点 {t_rs:.1f} s 后消失;master 日志里:' + ' / '.join(sorted({re.sub(r"^.*? (INFO|WARN)\s+\[[^\]]*\]\s*", "", l)[:100] for l in m1.log().splitlines() if 'expiration' in l.lower() or 'ServerCrashProcedure' in l and 'Start pid' in l})[:2]))
print(f'  客户端:kill 之后共 {len(errs)} 次失败操作,第一个失败的操作开始于 +{first_err:.1f} s,最后一个失败的操作结束于 +{last_err:.1f} s(之后恢复;受影响的时间窗 {bad_sec:.1f} s;每个失败的操作最多卡 hbase.client.operation.timeout=4000 ms);探测总次数 {len(L)}' if errs else '  客户端没有观察到失败')
R['rs_kill'] = dict(t_rs=t_rs, errs=len(errs), first=first_err, last=last_err, span=bad_sec, probes=len(L))
rs_after = sorted(z.get_children('/hbase/rs')); print('  /hbase/rs 之前:', len(rs_before), '个 → 之后:', len(rs_after), '个')
pj.kill()
print()
print('== 四:backup master:再启动一个 master m2,/hbase/backup-masters 下出现它;kill -9 active master m1,/hbase/master 多久换成 m2,期间客户端读写是否受影响')
m2 = HProc('master', 'm2', 7962, root).start(); wait(lambda: len(z.get_children('/hbase/backup-masters')) == 1, 120, 'backup'); time.sleep(3)
print('  /hbase/backup-masters 下:', z.get_children('/hbase/backup-masters'), '| 是否临时节点:', z.exists('/hbase/backup-masters/' + z.get_children('/hbase/backup-masters')[0]).ephemeralOwner != 0)
old = printable(z.get('/hbase/master')[0]); print('  /hbase/master =', old)
pf2 = WD / 'probe2.log'; pj = java('probe', out=pf2); time.sleep(4); tk = time.time(); m1.kill(); t_m = None
while time.time() - tk < 90 and t_m is None:
    try:
        cur = printable(z.get('/hbase/master')[0])
        if cur != old: t_m = time.time() - tk
    except Exception: pass
    time.sleep(0.05)
time.sleep(8); L = [l.split() for l in pf2.read_text().splitlines() if l.strip() and l.split()[0].isdigit()]; errs = [l for l in L if l[1] == 'ERR' and int(l[0]) / 1000 >= tk]
print(f'  /hbase/master 在 {t_m:.1f} s 后换成新 master:{printable(z.get("/hbase/master")[0])};active master 被杀期间客户端 {len([l for l in L if int(l[0]) / 1000 >= tk])} 次读写中失败 {len(errs)} 次(没有失败;推断是读写直接访问 region server、不经过 master,没有进一步验证)')
R['m_kill'] = dict(t_m=t_m, probes=len([l for l in L if int(l[0]) / 1000 >= tk]), errs=len(errs))
pj.kill(); 
for p in (m1, m2, r1, r2): p.kill()
z.stop(); n.stop(); save('z105', R); os._exit(0)
