import sys, os, time, json, re, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z35'); R = {}
print('== 一:投票比较的规则:先比 epoch、再比 zxid、最后比 sid。场景:数据落后的节点 sid 更大,能不能当选?')
e = Ensemble('z35', 3, base=7300).start(); ld = e.leader(); fos = sorted(e.followers(), key=lambda n: n.myid); lowf, highf = fos[0], fos[1]
print(f'  leader = {ld.name}(sid {ld.myid});follower:{lowf.name}(sid {lowf.myid})、{highf.name}(sid {highf.myid})')
z = client(f'127.0.0.1:{ld.cport}'); z.create('/a', b'1'); highf.stop(); time.sleep(0.5)
[z.create(f'/gap{i}', b'x') for i in range(50)]; z.stop()
print(f'  停掉 sid 更大的 {highf.name},再写 50 个 znode;然后杀掉 leader {ld.name},重启 {highf.name}(它的 zxid 落后)')
ld.kill(); highf.start(wipe=False, wait=False)
t0 = time.perf_counter()
while time.perf_counter() - t0 < 40:
    if any(n.alive() and n.mode() == 'leader' for n in (lowf, highf)): break
    time.sleep(0.1)
new = lowf if lowf.mode() == 'leader' else highf
print(f'  新 leader = {new.name}(sid {new.myid});{lowf.name} 的 zxid = {lowf.srvr().get("zxid")}、{highf.name} 的 zxid = {highf.srvr().get("zxid")}')
print(f'  → 有最新数据的 {lowf.name} 当选,尽管 sid 更小' if new is lowf else '  → sid 更大的当选了(与预期不符,见下)'); R['stale'] = dict(new=new.name, lowf=lowf.name, winner_is_fresh=new is lowf)
print('  落后节点的投票日志(它先投给自己,收到对方的更优选票后改投):')
L = [l for l in highf.log().splitlines() if 'Notification: my state:LOOKING' in l or 'New election' in l][-5:]
for l in L:
    m = re.search(r'(\d+:\d+:\d+\.\d+).*New election. My id = (\d+), proposed zxid=(0x\w+)', l)
    if m: print(f'    {m.group(1)}  新一轮选举:我(sid {m.group(2)})提议 zxid={m.group(3)}'); continue
    m = re.search(r'(\d+:\d+:\d+\.\d+).*n.sid:(\d+), n.state:(\w+), n.leader:(\d+).*n.zxid:(0x\w+)', l)
    if m: print(f'    {m.group(1)}  收到 sid={m.group(2)}({m.group(3)})的选票:选 sid={m.group(4)},它的 zxid={m.group(5)}')
e.stop()
print()
print('== 二:所有节点数据一样时(新集群同时启动),谁当选?5 次独立启动,统计当选的 sid')
cnt = collections.Counter()
for r in range(5):
    e = Ensemble(f'z35b{r}', 3, base=7320).start(); cnt[e.leader().myid] += 1; e.stop()
print('  5 次启动的 leader sid 分布:', dict(sorted(cnt.items())), '(数据相同时 sid 大的占优,但谁先凑够多数派取决于启动时机)'); R['equal'] = dict(cnt)
save('z35', R)
