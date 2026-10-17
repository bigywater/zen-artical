import sys, os, time, json, re, threading, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
import kazoo; from kazoo.client import KazooClient
from kazoo.exceptions import *
from kazoo.retry import KazooRetry
from kazoo.recipe.watchers import DataWatch
tee('z91'); R = {}
n = Node('z91', 7300, xmx=256, conf={'tickTime': 1000, 'maxClientCnxns': 500}).start(); z = client('127.0.0.1:7300')
print(f'== 一:kazoo {kazoo.__version__ if hasattr(kazoo, "__version__") else "2.11.0"} 的异常对照:每种服务端错误码对应哪个 Python 异常')
z.create('/e'); z.create('/e/c'); z.create('/eph', b'', ephemeral=True)
cases = [('create 已存在', lambda: z.create('/e')), ('get 不存在', lambda: z.get('/nope')), ('delete 有子节点', lambda: z.delete('/e')), ('set 版本不符', lambda: z.set('/e', b'x', version=99)), ('临时节点下建子节点', lambda: z.create('/eph/x')), ('create 父不存在', lambda: z.create('/a/b/c'))]
rows = []
for name, f in cases:
    try: f(); r = '无异常'
    except Exception as ex: r = type(ex).__name__
    rows.append((name, r)); print(f'  {name:<16} → {r}')
R['exc'] = rows
print()
print('== 二:同步调用 vs 异步(create_async 流水线):各创建 2000 个节点')
z.ensure_path('/s'); z.ensure_path('/a'); t0 = time.perf_counter()
for i in range(2000): z.create(f'/s/n{i}', b'x')
ts = time.perf_counter() - t0; t0 = time.perf_counter(); fs = [z.create_async(f'/a/n{i}', b'x') for i in range(2000)]; [f.get() for f in fs]; ta = time.perf_counter() - t0
print(f'  同步 {2000/ts:.0f} 个/s({ts:.2f} s);异步流水线 {2000/ta:.0f} 个/s({ta:.2f} s);异步是同步的 {ts/ta:.1f} 倍')
R['async'] = dict(sync=2000 / ts, asyn=2000 / ta)
print()
print('== 三:一个回调阻塞会拖住别的回调:kazoo 所有 watch 回调在同一个线程里执行')
z.create('/w1', b'0'); z.create('/w2', b'0'); ev = {}
DataWatch(z, '/w1', lambda d, s: (ev.__setitem__('w1', time.perf_counter()), time.sleep(2.0)) if d == b'1' else None)
DataWatch(z, '/w2', lambda d, s: ev.__setitem__('w2', time.perf_counter()) if d == b'1' else None)
time.sleep(0.5); t0 = time.perf_counter(); z.set('/w1', b'1'); time.sleep(0.05); z.set('/w2', b'1'); time.sleep(3)
print(f'  /w1 的回调睡 2 秒;/w2 在 {(ev["w2"] - t0)*1000:.0f} ms 后才收到回调(没有被阻塞则应该 < 50 ms)'); R['block'] = (ev['w2'] - t0) * 1000
print()
print('== 四:服务端不可用时:start() 的超时')
z2 = KazooClient(hosts='127.0.0.1:7399', timeout=5); t0 = time.perf_counter()
try: z2.start(timeout=3)
except Exception as ex: r = type(ex).__name__
print(f'  连一个没有服务的端口 start(timeout=3):{time.perf_counter()-t0:.1f} s 后抛 {r};state = {z2.state}'); R['start_to'] = r
try: z2.stop()
except Exception: pass
print()
print('== 五:服务端重启(短中断)与长中断时的状态序列,以及中断期间调用的行为')
def run(outage, name):
    log = []; c = client('127.0.0.1:7300', timeout=3); c.create(f'/{name}-eph', b'', ephemeral=True); sid0 = c.client_id[0]; t0 = time.perf_counter()
    c.add_listener(lambda s: log.append((time.perf_counter() - t0, str(s))))
    n.stop(); t_stop = time.perf_counter() - t0; time.sleep(0.3); res = {}
    def probe():
        tc = time.perf_counter()
        try: c.get('/'); res['r'] = '成功'
        except Exception as ex: res['r'] = type(ex).__name__
        res['at'] = time.perf_counter() - t0; res['dur'] = time.perf_counter() - tc
    th = threading.Thread(target=probe, daemon=True); th.start()
    time.sleep(max(0, outage - (time.perf_counter() - t0 - t_stop)))
    t_up_req = time.perf_counter() - t0; n.start(wipe=False); t_up = time.perf_counter() - t0; th.join(15); time.sleep(3)
    ex_ = c.exists(f'/{name}-eph') is not None; sid1 = c.client_id[0]
    seq = [(round(t, 1), s) for t, s in log]
    print(f'  服务端 SIGTERM 停止后 {outage} s 重新启动(会话超时 3 s);服务端停止发生在 +{t_stop:.1f} s,重新启动完成在 +{t_up:.1f} s')
    print(f'    listener 状态序列:{seq}')
    print(f'    中断期间发起的 get(\'/\'):{res.get("r")},发起后 {res.get("dur", -1):.1f} s 返回(相对重启完成 {res.get("at", 0) - t_up:+.1f} s)')
    print(f'    会话 id 不变:{sid0 == sid1};临时节点还在:{ex_}'); c.stop(); return dict(log=seq, same=sid0 == sid1, eph=ex_, call=res.get('r'), call_dur=res.get('dur'), call_rel=res.get('at', 0) - t_up, t_stop=t_stop, t_up=t_up)
R['short'] = run(1.0, 'short'); R['long'] = run(6.0, 'long')
z.stop(); n.stop(); save('z91', R); os._exit(0)
