import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z30'); R = {}
def trial(n, kill_idx, base):
    e = Ensemble(f'z30-{n}', n, base=base).start()
    z = client(e.hosts()); z.create('/keep', b'v'); z.stop()
    for i in kill_idx: e.nodes[i].kill()
    time.sleep(3)
    alive = [nd for nd in e.nodes if nd.alive()]
    ok = can_write(','.join(f'127.0.0.1:{nd.cport}' for nd in alive), timeout=6, start_timeout=8)
    modes = [nd.mode() or '不服务' for nd in alive]
    e.stop(); return ok, modes
print('== 一:多数派 = 节点数的一半以上(⌊N/2⌋+1):逐个组合杀掉 k 个节点,剩下的能不能写')
print(f'  {"节点数 N":>8} {"多数派":>6} {"杀掉 k":>6} {"剩余模式":<34} {"能写?":<6}')
R['rows'] = []
for n, ks in ((3, (1, 2)), (4, (1, 2)), (5, (2, 3))):
    for k in ks:
        ok, modes = trial(n, list(range(k)), 7300 + n * 10 + k)
        R['rows'].append((n, n // 2 + 1, k, modes, ok)); print(f'  {n:>8} {n // 2 + 1:>6} {k:>6} {str(modes):<34} {"能" if ok else "不能":<6}')
save('z30', R)
