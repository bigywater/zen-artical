import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tfo_common import *
tee('w60e'); reset()
def raw_syns(path, port):
    by = {}
    for p in tcp_pkts(path):
        if p['fl'] & 0x12 == 0x02 and p['dp'] == port:
            L = by.setdefault(p['sp'], []); cur = (p['plen'], tuple(topt(p)))
            if not L or L[-1] != cur: L.append(cur)
    return list(by.values())
def fmt(L): return ' → '.join(f'{pl}B/{"TFO" + str(o[0]) if o else "无TFO"}' for pl, o in L)
for n in (21, 22): tfolab('alias', 'add', n)
try:
    print('== 八:停用的范围与恢复:上一节(七)把 127.77.0.21 的 TFO 停用之后(同一个别名,约十几分钟内),(1)同一个目的地换一个端口,(2)换一个没用过的目的地 127.77.0.22,各连 3 次 connectx(服务端开 TFO);(3)继续每 60 秒对 127.77.0.21 连一次,最长 40 分钟,直到连续 2 次 SYN 里又带数据')
    for nm, host in (('同一目的地、新端口', '127.77.0.21'), ('新目的地 127.77.0.22', '127.77.0.22')):
        port = lab_port(); th, got = server(host, port, True, 3)
        with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
            for i in range(3): client(host, port, b'hello%d' % i).close(); time.sleep(0.2)
            th.join(); time.sleep(0.3)
        print(f'  {nm}:' + ';'.join(fmt(s) for s in raw_syns(c.pcap, port)))
    port = lab_port(); th, got = server('127.77.0.21', port, True, 60); t0 = time.time(); n_ok = 0; rows = []
    with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
        for j in range(41):
            try: client('127.77.0.21', port, b'poll%02d' % j).close()
            except Exception: pass
            time.sleep(0.5); S_ = raw_syns(c.pcap, port); last = S_[-1][-1] if S_ else None
            rows.append((round(time.time() - t0), last))
            n_ok = n_ok + 1 if last and last[0] > 0 else 0
            if n_ok >= 2: break
            time.sleep(59.5)
    for t, l in rows[:4] + (rows[-3:] if len(rows) > 4 else []): print(f'    +{t:>5} s:{l[0]}B/{"TFO" + str(l[1][0]) if l[1] else "无TFO"}')
    print(f'  共轮询 {len(rows)} 次,覆盖 {rows[-1][0]} 秒;最后一次 SYN 载荷 {rows[-1][1][0]} 字节;' + ('已恢复' if n_ok >= 2 else '没有恢复'))
finally:
    for n in (21, 22): tfolab('alias', 'del', n)
    netlab('off')
