import sys, os, time, json, re, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z43'); R = {}
e = Ensemble('z43', 3, base=7300).start(); hosts = e.hosts()
print('== 一:leader 崩溃时有写请求正在进行:已确认(返回成功)的写会不会丢?没确认的呢?(5 次,每次一个线程不停地创建节点,记录每个请求的结果,杀 leader 后核对)')
print(f'  {"次":>2} {"已确认":>7} {"确认后丢失":>10} {"未确认(ConnectionLoss)":>22} {"其中实际已写入":>14}')
R['runs'] = []
for r in range(5):
    z = client(hosts, timeout=10); z.ensure_path(f'/r{r}'); acked, unknown = [], []; stop = threading.Event()
    def writer():
        i = 0
        while not stop.is_set():
            p = f'/r{r}/n{i}'
            try: z.create(p, b'x'); acked.append(p)
            except Exception as ex:
                unknown.append(p)
            i += 1
    th = threading.Thread(target=writer); th.start(); time.sleep(1.0)
    ld = e.leader(); ld.kill(); time.sleep(6); stop.set(); th.join(30)
    chk = client(','.join(f'127.0.0.1:{n.cport}' for n in e.nodes if n.alive()))
    have = set(chk.get_children(f'/r{r}')); lost = [p for p in acked if p.rsplit('/', 1)[1] not in have]; present_unk = [p for p in unknown if p.rsplit('/', 1)[1] in have]
    R['runs'].append(dict(acked=len(acked), lost=len(lost), unknown=len(unknown), present=len(present_unk))); print(f'  {r + 1:>2} {len(acked):>7} {len(lost):>10} {len(unknown):>22} {len(present_unk):>14}')
    chk.stop(); z.stop(); ld.start(wipe=False, wait=False); e.wait_quorum(); time.sleep(1.5)
print('  汇总:已确认的写全部保留 =', all(x['lost'] == 0 for x in R['runs']), '| 未确认的写里实际已经写入的合计 =', sum(x['present'] for x in R['runs']), '/', sum(x['unknown'] for x in R['runs']))
print()
print('== 二:崩溃恢复的时间线(最近一次:杀 leader 之后新 leader 的日志,相对杀的时刻)——见上一篇;这里看恢复完成后三个节点的数据一致')
zx = {n.name: n.srvr().get('zxid') for n in e.nodes}; print('  三个节点的 zxid:', zx, '| 一致:', len(set(zx.values())) == 1); R['zxid_same'] = len(set(zx.values())) == 1
cnt = {}
for n in e.nodes:
    z = client(f'127.0.0.1:{n.cport}'); cnt[n.name] = sum(len(z.get_children(f'/r{r}')) for r in range(5)); z.stop()
print('  各节点上 /r0..r4 下的 znode 总数:', cnt, '| 一致:', len(set(cnt.values())) == 1); R['counts'] = cnt
e.stop(); save('z43', R)
