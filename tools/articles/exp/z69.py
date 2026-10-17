import sys, os, time, json, re, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z69'); R = {}
e = Ensemble('z69', 3, base=7300)
for nd in e.nodes: nd.ver = '3.8.4'
e.start()
def ver(nd):
    s = four(nd.cport, 'srvr'); m = re.search(r'Zookeeper version: (\S+?)[,-]', s) or re.search(r'Zookeeper version: (\S+)', s); return m.group(1) if m else '?'
print('== 一:起点:3 个节点全部是 ZooKeeper 3.8.4(官方发行包的 jar)')
print('  ', {nd.name: f'{ver(nd)} {nd.mode()}' for nd in e.nodes}); R['start'] = {nd.name: f'{ver(nd)} {nd.mode()}' for nd in e.nodes}
z = client(e.hosts(), timeout=15); z.create('/up', b''); acked = []; fails = [0]; stop = threading.Event(); log = []
def writer():
    i = 0
    while not stop.is_set():
        t = time.perf_counter()
        try: z.create(f'/up/n{i}', b'x'); acked.append(i); ok = True
        except Exception: ok = False; fails[0] += 1
        log.append((t, ok)); i += 1; time.sleep(0.01)
th = threading.Thread(target=writer); th.start(); time.sleep(1)
print()
print('== 二:滚动升级:先 follower、最后 leader;每个节点:停止 → 换成 3.9.6 的 jar → 启动,等它重新同步完成;一个写线程(每 10 ms 一次)持续写入')
print(f'  {"步骤":<22} {"耗时 s":>7} {"该步写入最长间隔 ms":>18}  升级后版本与角色(全体)')
steps = [n for n in e.followers()] + [e.leader()]; R['steps'] = []
for nd in steps:
    t0 = time.perf_counter(); was = nd.mode(); nd.stop(); nd.ver = '3.9.6'; nd.start(wipe=False, wait=False)
    while time.perf_counter() - t0 < 60:
        if nd.mode() in ('follower', 'leader') and nd.srvr().get('zxid') == next(n for n in e.nodes if n.mode() == 'leader').srvr().get('zxid'): break
        time.sleep(0.05)
    dt = time.perf_counter() - t0; time.sleep(1.0)
    seg = [t for t, ok in log if ok and t >= t0 - 0.2]; gaps = [b - a for a, b in zip(seg, seg[1:])]; mg = max(gaps) * 1000 if gaps else 0
    state = {n.name: f'{ver(n)} {n.mode()}' for n in e.nodes if n.alive()}; R['steps'].append(dict(node=nd.name, was=was, s=dt, gap=mg, state=state))
    print(f'  升级 {nd.name}({was}) {dt:>7.1f} {mg:>18.0f}  {state}')
stop.set(); th.join()
print()
print('== 三:升级完成后:全部是 3.9.6;写入过程中没有丢失任何已确认的写')
print('  版本与角色:', {n.name: f'{ver(n)} {n.mode()}' for n in e.nodes}); R['final'] = {n.name: f'{ver(n)} {n.mode()}' for n in e.nodes}
chk = client(e.hosts()); have = set(chk.get_children('/up')); lost = [i for i in acked if f'n{i}' not in have]
print(f'  写线程确认的写入 {len(acked)} 个,失败(异常)的调用 {fails[0]} 次;确认后丢失 {len(lost)} 个'); R['writes'] = dict(acked=len(acked), fails=fails[0], lost=len(lost))
print('  新版本的 znode 数据与升级前一致:/up 下子节点数', len(have), '| zxid 一致:', len({n.srvr().get('zxid') for n in e.nodes}) == 1); R['same_zxid'] = len({n.srvr().get('zxid') for n in e.nodes}) == 1
chk.stop(); z.stop(); e.stop(); save('z69', R)
