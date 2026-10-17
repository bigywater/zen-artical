import sys, os, time, json, re, statistics, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z34'); R = {}
e = Ensemble('z34', 3, base=7300, conf={'tickTime': 2000}).start()
def tod(): n = datetime.datetime.now(); return n.hour * 3600 + n.minute * 60 + n.second + n.microsecond / 1e6
print('== 一:杀掉 leader 之后的选举:5 次(每次都把被杀的节点重新启动回来)。三个时间:新 leader 出现、第一次写入成功、日志里的 LEADER ELECTION TOOK')
print(f'  {"次":>2} {"被杀":<7} {"新 leader":<9} {"出现(ms)":>9} {"写成功(ms)":>11} {"选举耗时(日志,ms)":>18}')
R['runs'] = []
for r in range(5):
    ld = e.leader(); alive = [n for n in e.nodes if n is not ld]
    t0 = time.perf_counter(); ld.kill(); newl = None; tw = None
    while time.perf_counter() - t0 < 30:
        if newl is None:
            for n in alive:
                if n.mode() == 'leader': newl = n; tl_ = (time.perf_counter() - t0) * 1000
        if newl is not None and tw is None and can_write(','.join(f'127.0.0.1:{n.cport}' for n in alive), timeout=4, start_timeout=2): tw = (time.perf_counter() - t0) * 1000
        if tw is not None: break
        time.sleep(0.02)
    took = [int(m.group(1)) for l in log_lines(newl, ['LEADING - LEADER ELECTION TOOK']) for m in [re.search(r'TOOK - (\d+)', l)] if m][-1]
    R['runs'].append(dict(killed=ld.name, new=newl.name, appear=tl_, write=tw, took=took)); print(f'  {r + 1:>2} {ld.name:<7} {newl.name:<9} {tl_:>9.0f} {tw:>11.0f} {took:>18}')
    ld.start(wipe=False, wait=False); e.wait_quorum(); time.sleep(1)
ap = [x['appear'] for x in R['runs']]; wr = [x['write'] for x in R['runs']]
print(f'  中位数:新 leader 出现 {statistics.median(ap):.0f} ms,第一次写成功 {statistics.median(wr):.0f} ms;最小 / 最大(写成功):{min(wr):.0f} / {max(wr):.0f} ms'); R['med'] = dict(appear=statistics.median(ap), write=statistics.median(wr), mn=min(wr), mx=max(wr))
print()
print('== 二:一次选举里的选票交换(follower 日志里的 Notification 行,只列关键字段)')
nd = e.followers()[0]; lg = [l for l in nd.log().splitlines() if 'Notification: my state' in l][-6:]
for l in lg:
    m = re.search(r'(\d+:\d+:\d+\.\d+).*my state:(\w+); n.sid:(\d+), n.state:(\w+), n.leader:(\d+), n.round:(0x\w+), n.peerEpoch:(0x\w+), n.zxid:(0x\w+)', l)
    if m: print(f'  {m.group(1)}  我是 {m.group(2):<9} 收到 sid={m.group(3)} 的通知:它的状态 {m.group(4):<9} 它投给 {m.group(5)}  round={m.group(6)} peerEpoch={m.group(7)} zxid={m.group(8)}')
R['notif'] = [l[:150] for l in lg]
e.stop(); save('z34', R)
