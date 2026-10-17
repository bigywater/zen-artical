import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tfo_common import *
tee('w60c'); reset()
def raw_syns(path, port):
    by = {}
    for p in tcp_pkts(path):
        if p['fl'] & 0x12 == 0x02 and p['dp'] == port:
            L = by.setdefault(p['sp'], [])
            cur = (p['plen'], tuple(topt(p)))
            if not L or L[-1] != cur: L.append(cur)
    return list(by.values())
def fmt(L): return ' → '.join(f'{pl}B/{"TFO" + str(o[0]) if o else "无TFO"}' for pl, o in L)
tfolab('alias', 'add', 21)
try:
    print('== 七:客户端什么时候停用 TFO:目的地 127.77.0.21,服务端开 TFO。先无丢包取 cookie 并带数据 3 次;再开 30% 丢包(每方向,单向延迟 20 ms)连 30 次,每次 connectx 带数据;看每个连接 SYN(含重传)的载荷和 TFO 选项变化;然后关掉丢包,每 10 秒连一次,最长 6 分钟,看客户端什么时候恢复在 SYN 里带数据')
    port = lab_port(); th, got = server('127.77.0.21', port, True, 3 + 30 + 40)
    t_start = time.time()
    with Cap(f'tcp port {port}', iface='lo0', write=True, snaplen=96) as c:
        for i in range(3): client('127.77.0.21', port, b'hello%02d' % i).close(); time.sleep(0.2)
        fails = 0
        with lossy(loss=30, delay=20, bw=0):
            for i in range(30):
                try: client('127.77.0.21', port, b'loss%02d' % i).close()
                except Exception as e: fails += 1
                time.sleep(0.2)
        t_off = time.time()
        rec = []; n_ok = 0
        for j in range(36):
            t0 = time.time() - t_off
            try: client('127.77.0.21', port, b'poll%02d' % j).close()
            except Exception as e: pass
            time.sleep(0.5)
            S_ = raw_syns(c.pcap, port); rec.append((round(t0), S_[-1] if S_ else None))
            if S_ and S_[-1][-1][0] > 0: n_ok += 1
            else: n_ok = 0
            if n_ok >= 2: break
            time.sleep(9.5)
        time.sleep(0.5)
    L = raw_syns(c.pcap, port)
    print(f'  连接总数 {len(L)}(前 3 个无丢包;其后 30 个在 30% 丢包下;之后每 10 秒一次);丢包阶段 connectx/recv 失败 {fails} 次')
    for i, s in enumerate(L[:3], 1): print(f'  无丢包第 {i} 个:{fmt(s)}')
    for i, s in enumerate(L[3:33], 1): print(f'  丢包第 {i:>2} 个:{fmt(s)}')
    print('  关掉丢包之后:')
    for t0, s in rec: print(f'    +{t0:>4} s:{fmt(s) if s else "无抓包"}')
    th.join(timeout=1)
finally:
    tfolab('alias', 'del', 21); netlab('off')
