import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f148'); R = {}
import threading, random, statistics, http.client as hc
APP = '''
import threading, time
from flask import Flask, request, jsonify
app = Flask(__name__)
EVENTS = []; COND = threading.Condition()
@app.post("/publish")
def publish():
    with COND: EVENTS.append({"id": len(EVENTS) + 1, "t": time.time()}); COND.notify_all()
    return jsonify(id=len(EVENTS))
@app.get("/poll")
def poll():
    since = int(request.args.get("since", "0")); timeout = float(request.args.get("timeout", "3"))
    with COND:
        COND.wait_for(lambda: len(EVENTS) > since, timeout=timeout); new = EVENTS[since:]
    return (jsonify(events=new), 200) if new else ("", 204)
@app.get("/ping")
def ping(): return "pong"
'''
d = mkapp('f148', {'app.py': APP})
def call(port, method, path, timeout=30):
    c = hc.HTTPConnection('127.0.0.1', port, timeout=timeout); t0 = time.perf_counter(); c.request(method, path); r = c.getresponse(); b = r.read(); c.close(); return r.status, b, ms(t0)
G = ['gunicorn', '-b', '127.0.0.1:{port}', '-w', '1']
print('== 一:消息送达延迟:长轮询 vs 每秒短轮询(各 10 条消息,随机时刻发布)')
R['delay'] = {}
with Server(d, G + ['-k', 'gthread', '--threads', '8', 'app:app']) as s:
    time.sleep(1.0)
    delays = []
    seen = [0]
    def long_poller(n):
        for _ in range(n):
            while True:
                st, b, _ = call(s.port, 'GET', f'/poll?since={seen[0]}&timeout=5')
                if st == 200:
                    ev = json.loads(b)['events']; seen[0] += len(ev); delays.extend(time.time() - e['t'] for e in ev); break
    th = threading.Thread(target=long_poller, args=(10,)); th.start()
    for _ in range(10): time.sleep(random.uniform(0.2, 0.8)); call(s.port, 'POST', '/publish')
    th.join(); print(f'  长轮询:送达延迟中位数 {statistics.median(delays) * 1000:.1f} ms,最大 {max(delays) * 1000:.1f} ms'); R['delay']['long'] = [statistics.median(delays) * 1000, max(delays) * 1000]
with Server(d, G + ['-k', 'gthread', '--threads', '8', 'app:app']) as s:
    time.sleep(1.0); delays = []; seen = [0]; stop = threading.Event()
    def short_poller():
        while not stop.is_set():
            st, b, _ = call(s.port, 'GET', f'/poll?since={seen[0]}&timeout=0')
            if st == 200: ev = json.loads(b)['events']; seen[0] += len(ev); delays.extend(time.time() - e['t'] for e in ev)
            time.sleep(1.0)
    th = threading.Thread(target=short_poller); th.start()
    for _ in range(10): time.sleep(random.uniform(0.2, 0.8)); call(s.port, 'POST', '/publish')
    time.sleep(1.2); stop.set(); th.join(); print(f'  每秒短轮询:送达延迟中位数 {statistics.median(delays) * 1000:.0f} ms,最大 {max(delays) * 1000:.0f} ms'); R['delay']['short'] = [statistics.median(delays) * 1000, max(delays) * 1000]
print()
print('== 二:每个等待中的轮询占一个线程:gthread 8 个线程,8 个客户端在等,第 9 个(普通请求)')
R['cap'] = {}
for label, args in (('gthread × 1 个 worker × 8 线程', ['-k', 'gthread', '--threads', '8']), ('gevent × 1 个 worker', ['-k', 'gevent', '--worker-connections', '1000'])):
    with Server(d, G + args + ['app:app']) as s:
        time.sleep(1.0); pollers = [threading.Thread(target=lambda: call(s.port, 'GET', '/poll?since=0&timeout=3')) for _ in range(8)]; [p.start() for p in pollers]; time.sleep(0.5)
        st, b, dt = call(s.port, 'GET', '/ping'); [p.join() for p in pollers]; print(f'  {label:<30} 8 个轮询在等待时,/ping 用了 {dt:.0f} ms'); R['cap'][label] = dt
with Server(d, G + ['-k', 'gevent', '--worker-connections', '1000', 'app:app']) as s:
    time.sleep(1.0); ps = [threading.Thread(target=lambda: call(s.port, 'GET', '/poll?since=0&timeout=3', timeout=30)) for _ in range(300)]; [p.start() for p in ps]; time.sleep(1.0)
    st, b, dt = call(s.port, 'GET', '/ping'); pid_rss = subprocess.run(['pgrep', '-f', f'127.0.0.1:{s.port}'], capture_output=True, text=True).stdout.split(); rss = sum(int(subprocess.run(['ps', '-o', 'rss=', '-p', p], capture_output=True, text=True).stdout.strip() or 0) for p in pid_rss) / 1024; [p.join() for p in ps]
    print(f'  gevent 同时挂着 300 个等待中的轮询,/ping 用了 {dt:.0f} ms,整个 gunicorn(含 master)内存约 {rss:.0f} MB'); R['gevent300'] = [dt, rss]
print()
print('== 三:两次轮询之间发布的消息不能丢:用 since(游标)重新连接')
with Server(d, G + ['-k', 'gthread', '--threads', '8', 'app:app']) as s:
    time.sleep(1.0); st, b, _ = call(s.port, 'GET', '/poll?since=0&timeout=0'); call(s.port, 'POST', '/publish'); call(s.port, 'POST', '/publish'); call(s.port, 'POST', '/publish')
    st, b, _ = call(s.port, 'GET', '/poll?since=1&timeout=1'); ev = json.loads(b)['events']; print('  客户端上次收到 id=1,断开期间又发布了 2、3;重新带 since=1 轮询 → 拿到的 id:', [e['id'] for e in ev]); R['cursor'] = [e['id'] for e in ev]
    st, b, dt = call(s.port, 'GET', '/poll?since=3&timeout=1'); print(f'  之后没有新消息:since=3 轮询 → {st}(空),等了 {dt:.0f} ms 超时返回'); R['empty'] = [st, dt]
save('f148', R)
