import sys, os, time, json, re, shutil, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z59'); R = {}
print('== 一:不停机的备份:写入进行中,直接复制数据目录(version-2),再用副本启动一个新节点——能启动吗、数据是否一致(5 次)')
n = Node('z59a', 7300, conf={'snapCount': 2000}).start(); z = client('127.0.0.1:7300'); z.create('/w', b'')
stop = threading.Event(); cnt = [0]
def writer():
    while not stop.is_set():
        try: z.create(f'/w/n{cnt[0]}', b'x' * 50); cnt[0] += 1
        except Exception: pass
th = threading.Thread(target=writer); th.start(); time.sleep(1)
print(f'  {"次":>2} {"复制时源节点 znode 数":>20} {"副本启动":>8} {"副本 znode 数":>12} {"副本 ≤ 源":>8}')
R['trials'] = []
for t in range(5):
    time.sleep(0.5); src = kv(n.four('mntr')).get('zk_znode_count'); dst = ZDATA / f'z59copy{t}'; shutil.rmtree(dst, ignore_errors=True); shutil.copytree(n.dir / 'data', dst / 'data'); src2 = int(kv(n.four('mntr')).get('zk_znode_count'))
    c = Node(f'z59copy{t}', 7310 + t); c.dir = dst; (dst / 'zoo.cfg').write_text(c.cfg_text().replace(str(ZDATA / f'z59copy{t}' / 'data'), str(dst / 'data'))); (dst / 'logback.xml').write_text(LOGBACK % (dst / 'zk.log', 'INFO'))
    try:
        c.start(wipe=False, timeout=30); cc = int(kv(c.four('mntr')).get('zk_znode_count')); ok = True
    except Exception as e: cc = None; ok = False
    R['trials'].append(dict(src=int(src), ok=ok, copy=cc)); print(f'  {t + 1:>2} {src:>20} {"成功" if ok else "失败":>8} {str(cc):>12} {"是" if cc is not None and cc <= src2 else "否":>8}'); c.stop()
stop.set(); th.join(); z.stop(); n.stop()
print()
print('== 二:只备份最近一个快照(不带事务日志):恢复后丢掉快照之后的写入')
n = Node('z59b', 7300, conf={'snapCount': 1000}).start(); z = client('127.0.0.1:7300'); rs = [z.create_async(f'/n{i}', b'x') for i in range(3500)]; [r.get() for r in rs]; time.sleep(0.5)
total = int(kv(n.four('mntr')).get('zk_znode_count')); v2 = n.dir / 'data' / 'version-2'; sn = sorted((p for p in v2.iterdir() if p.name.startswith('snapshot.')), key=lambda p: int(p.name.split('.')[1], 16))[-1]
z.stop(); n.stop(); dst = ZDATA / 'z59snap'; shutil.rmtree(dst, ignore_errors=True); (dst / 'data' / 'version-2').mkdir(parents=True); shutil.copy(sn, dst / 'data' / 'version-2' / sn.name)
c = Node('z59snap', 7311); c.dir = dst; (dst / 'zoo.cfg').write_text(c.cfg_text().replace(str(ZDATA / 'z59snap' / 'data'), str(dst / 'data'))); (dst / 'logback.xml').write_text(LOGBACK % (dst / 'zk.log', 'INFO')); c.start(wipe=False)
print(f'  源节点 znode 数 {total};只用快照 {sn.name} 恢复:znode 数 {kv(c.four("mntr")).get("zk_znode_count")}(快照之后的写入没有了)'); R['snap_only'] = dict(src=total, restored=int(kv(c.four('mntr')).get('zk_znode_count'))); c.stop()
print()
print('== 三:集群里用旧备份恢复一个节点:它会从 leader 追上最新数据(不会把集群拖回旧状态)')
e = Ensemble('z59c', 3, base=7320).start(); z = client(e.hosts()); [z.create(f'/a{i}', b'x') for i in range(100)]; time.sleep(0.5)
f = e.followers()[0]; f.stop(); old = ZDATA / 'z59old'; shutil.rmtree(old, ignore_errors=True); shutil.copytree(f.dir / 'data', old); f.start(wipe=False, wait=False); time.sleep(2)
zz = client(e.hosts()); [zz.create(f'/b{i}', b'x') for i in range(300)]; zz.stop()
f.stop(); shutil.rmtree(f.dir / 'data'); shutil.copytree(old, f.dir / 'data'); nb = len(e.leader().log().splitlines()); f.start(wipe=False, wait=False)
for _ in range(100):
    if f.mode() == 'follower' and f.srvr().get('zxid') == e.leader().srvr().get('zxid'): break
    time.sleep(0.1)
print(f'  用 300 个写入之前的旧备份恢复 {f.name} 后:Mode {f.mode()},znode 数 {kv(f.four("mntr")).get("zk_znode_count")}(leader 上 {kv(e.leader().four("mntr")).get("zk_znode_count")}),追上用的是', [re.search(r'Sending (DIFF|snapshot)', l).group(1) for l in e.leader().log().splitlines()[nb:] if re.search(r'Sending (DIFF|snapshot)', l)]); R['old_node'] = dict(cnt=kv(f.four('mntr')).get('zk_znode_count'), leader=kv(e.leader().four('mntr')).get('zk_znode_count'))
z.stop(); e.stop(); save('z59', R)
