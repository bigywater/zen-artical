import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z38'); R = {}
def split(h): v = int(h, 16); return v >> 32, v & 0xffffffff
e = Ensemble('z38', 3, base=7300).start()
def zx(nd=None): nd = nd or e.leader(); return nd.srvr().get('zxid')
print('== 一:counter 每个事务 +1:create / set / delete / 新建 + 关闭会话 / multi 各占几个')
z = client(e.hosts()); time.sleep(0.3); base = split(zx())[1]
def step(label, fn):
    global base
    fn(); time.sleep(0.2); c = split(zx())[1]; print(f'  {label:<28} counter {base} → {c}(+{c - base})'); r = (label, c - base); base = c; return r
R['ops'] = [step('create /x', lambda: z.create('/x', b'1')), step('set /x', lambda: z.set('/x', b'2')), step('delete /x', lambda: z.delete('/x')), step('get /(读)', lambda: z.get('/')), step('exists /(读)', lambda: z.exists('/')),
    step('multi(5 个 create)', lambda: (lambda t: ([t.create(f'/m{i}', b'') for i in range(5)], t.commit()))(z.transaction())),
    step('新建并立刻关闭一个会话', lambda: client(e.hosts()).stop()), step('create 临时节点(同一会话)', lambda: z.create('/eph', b'', ephemeral=True))]
print()
print('== 二:每次选出新 leader,epoch + 1(连续杀 3 次 leader,每次把它启动回来)')
R['epochs'] = []
for r in range(3):
    ld = e.leader(); ld.kill(); time.sleep(3); ld.start(wipe=False, wait=False); e.wait_quorum(); time.sleep(1.5)
    ep, ct = split(e.leader().srvr()['zxid']); R['epochs'].append(ep); print(f'  第 {r + 1} 次换 leader 之后:新 leader {e.leader().name},zxid epoch = {ep},counter = {ct}')
print()
print('== 三:一个落选 / 没有成功的选举不会增加 epoch 吗?杀掉 2 个节点(没有多数派),等 8 秒,再恢复')
ep0 = split(e.leader().srvr()['zxid'])[0]; alive = [n for n in e.nodes if n.alive()]
alive[0].kill(); alive[1].kill(); time.sleep(8); alive[0].start(wipe=False, wait=False); e.wait_quorum(); time.sleep(1.5)
ep1 = split(e.leader().srvr()['zxid'])[0]; print(f'  没有多数派的 8 秒里节点反复 LOOKING;恢复后 epoch {ep0} → {ep1}(只有成功当选才 +1,选举轮次 round 是另一个计数)'); R['no_quorum'] = (ep0, ep1)
rounds = [int(m.group(1), 16) for l in e.nodes[2].log().splitlines() for m in [re.search(r'n.round:(0x[0-9a-f]+)', l)] if m]; print('  某节点日志里出现过的 n.round 最大值(选举轮次):', hex(max(rounds)) if rounds else None); R['rounds'] = hex(max(rounds)) if rounds else None
z.stop(); e.stop(); save('z38', R)
