import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f78'); R = {}
import socketio, requests, redis as redis_lib
RP = 9652
rdir = FT / 'f78_redis'; shutil.rmtree(rdir, ignore_errors=True); rdir.mkdir(parents=True)
rproc = subprocess.Popen(['/opt/homebrew/bin/redis-server', '--port', str(RP), '--bind', '127.0.0.1', '--save', '', '--appendonly', 'no', '--dir', str(rdir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try: redis_lib.Redis(port=RP).ping(); break
    except Exception: time.sleep(0.1)
APP = '''
import os, time
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
app = Flask(__name__)
mq = os.environ.get("MQ") or None
sio = SocketIO(app, async_mode="threading", message_queue=mq, ping_interval=float(os.environ.get("PI", "25")), ping_timeout=float(os.environ.get("PT", "20")), cors_allowed_origins="*")
LOG = os.environ.get("LOGF", "/dev/null")
def log(s):
    with open(LOG, "a") as f: f.write(f"{time.time():.3f} {s}\\n")
@sio.on("connect")
def on_connect(auth):
    log(f"connect sid={request.sid} auth={auth} transport={request.args.get('transport')}")
    if isinstance(auth, dict) and auth.get("token") == "bad": return False
@sio.on("disconnect")
def on_disconnect(reason=None):
    log(f"disconnect sid={request.sid} reason={reason}")
@sio.on("echo")
def echo(data): return {"pid": os.getpid(), "echo": data}
@sio.on("join")
def j(room): join_room(room); emit("joined", {"room": room, "pid": os.getpid()})
@sio.on("to_room")
def to_room(d): emit("room_msg", d["msg"], to=d["room"], include_self=d.get("self", True))
@sio.on("bcast")
def bcast(msg): emit("bcast", {"msg": msg, "from_pid": os.getpid()}, broadcast=True, include_self=False)
@sio.on("whoami")
def whoami(): return os.getpid()
@app.get("/health")
def health(): return "ok"
'''
d = mkapp('f78', {'app.py': APP})
LOGF = d / 'events.log'
def Srv(workers=1, **extra):
    LOGF.write_text('')
    return Server(d, ['gunicorn', '-b', '127.0.0.1:{port}', '-k', 'gthread', '--threads', '40', '--workers', str(workers), 'app:app'], LOGF=LOGF, **extra)
def waitfor(cond, t=5):
    t0 = time.time()
    while time.time() - t0 < t:
        if cond(): return True
        time.sleep(0.02)
    return False
try:
    print('== 一:握手的原始样子:先用普通 HTTP 轮询握手(EIO=4),看服务端发来的第一个包')
    with Srv() as s:
        u = f'http://127.0.0.1:{s.port}/socket.io/'
        r = requests.get(u, params={'EIO': 4, 'transport': 'polling'}); print('  GET /socket.io/?EIO=4&transport=polling →', r.status_code, r.headers.get('Content-Type')); print('  正文:', r.text[:200]); R['hs'] = r.text
        sid = json.loads(r.text[1:])['sid']
        r2 = requests.post(u, params={'EIO': 4, 'transport': 'polling', 'sid': sid}, data='40'); print('  POST 40(Socket.IO 的 CONNECT 包)→', r2.status_code, repr(r2.text))
        r3 = requests.get(u, params={'EIO': 4, 'transport': 'polling', 'sid': sid}); print('  GET 轮询取回 → ', r3.status_code, r3.text[:80]); R['conn_pkt'] = r3.text[:80]
        r4 = requests.post(u, params={'EIO': 4, 'transport': 'polling', 'sid': sid}, data='421["echo","hi"]')
        pk = []
        for _ in range(3):
            t_ = requests.get(u, params={'EIO': 4, 'transport': 'polling', 'sid': sid}, timeout=3).text; pk.append(t_[:90])
            if '431' in t_: break
        print('  发带 ack 编号的事件 421["echo","hi"] 后,轮询依次取回:', pk); R['evt'] = pk
        r6 = requests.get(u, params={'EIO': 4, 'transport': 'polling', 'sid': 'nope'}); print('  用不存在的 sid 轮询 →', r6.status_code, r6.text[:80]); R['badsid'] = [r6.status_code, r6.text[:80]]
    print()
    print('== 二:python-socketio 客户端先走轮询、再升级到 WebSocket:量升级耗时')
    with Srv() as s:
        c = socketio.Client(); ts = []; t0 = time.perf_counter(); c.connect(f'http://127.0.0.1:{s.port}', transports=['polling', 'websocket'], wait_timeout=5)
        tconn = ms(t0); ts.append((round(tconn), c.transport()))
        waitfor(lambda: c.transport() == 'websocket'); ts.append((round(ms(t0)), c.transport()))
        print(f'  connect() 返回时(+{ts[0][0]} ms)传输方式:{ts[0][1]};升级后(+{ts[1][0]} ms):{ts[1][1]}'); R['upg'] = ts
        print('  服务端事件日志:', [l.split(' ', 1)[1][:90] for l in LOGF.read_text().splitlines()])
        c.disconnect(); time.sleep(0.2)
        c2 = socketio.Client(); c2.connect(f'http://127.0.0.1:{s.port}', transports=['websocket'], wait_timeout=5); print('  只允许 websocket 时 transport =', c2.transport()); R['ws_only'] = c2.transport(); c2.disconnect()
        c3 = socketio.Client(); c3.connect(f'http://127.0.0.1:{s.port}', transports=['polling'], wait_timeout=5); time.sleep(1.5); print('  只允许 polling 时 transport =', c3.transport(), '(1.5 秒后仍是)'); R['poll_only'] = c3.transport(); c3.disconnect()
    print()
    print('== 三:事件、ack 回调、连接时的 auth 与拒绝连接')
    with Srv() as s:
        c = socketio.Client(); c.connect(f'http://127.0.0.1:{s.port}', auth={'token': 'good'}, transports=['websocket'])
        res = c.call('echo', {'a': 1}, timeout=3); print('  call("echo", {a:1}) 的返回值(来自服务端处理函数的 return,即 ack):', res); R['ack'] = res
        got = []; c.on('joined', lambda d: got.append(d)); c.emit('join', 'r1'); waitfor(lambda: got); print('  服务端 emit 回来的事件 joined:', got); c.disconnect()
        c = socketio.Client()
        try: c.connect(f'http://127.0.0.1:{s.port}', auth={'token': 'bad'}, transports=['websocket'], wait_timeout=3); r_ = '连上了'
        except Exception as e: r_ = f'{type(e).__name__}: {e}'
        print('  connect 处理函数 return False 时客户端:', r_); R['reject'] = r_
        print('  服务端日志:', [l.split(' ', 1)[1][:100] for l in LOGF.read_text().splitlines() if 'bad' in l or 'good' in l])
    print()
    print('== 四:房间与广播:3 个客户端,A、B 加入 r1,C 不加入;在房间里发消息')
    with Srv() as s:
        cl = {}; recv = {k: [] for k in 'ABC'}
        for k in 'ABC':
            c = socketio.Client(); c.on('room_msg', (lambda k: lambda m: recv[k].append(m))(k)); c.on('bcast', (lambda k: lambda m: recv[k].append(('bcast', m['msg'])))(k)); c.connect(f'http://127.0.0.1:{s.port}', transports=['websocket']); cl[k] = c
        for k in 'AB': cl[k].call('join', 'r1', timeout=3)
        cl['A'].emit('to_room', {'room': 'r1', 'msg': 'm1'}); time.sleep(0.4)
        print('  A 向 r1 发 m1(include_self=True):', {k: recv[k] for k in 'ABC'}); R['room'] = {k: list(recv[k]) for k in 'ABC'}
        for k in 'ABC': recv[k].clear()
        cl['A'].emit('to_room', {'room': 'r1', 'msg': 'm2', 'self': False}); time.sleep(0.4)
        print('  A 向 r1 发 m2(include_self=False):', {k: recv[k] for k in 'ABC'}); R['room2'] = {k: list(recv[k]) for k in 'ABC'}
        for k in 'ABC': recv[k].clear()
        cl['A'].emit('bcast', 'hello all'); time.sleep(0.4)
        print('  A 广播 bcast(include_self=False):', {k: recv[k] for k in 'ABC'}); R['bcast'] = {k: list(recv[k]) for k in 'ABC'}
        for c in cl.values(): c.disconnect()
    print()
    print('== 五:断线检测:正常断开 vs 客户端进程被 kill -9(服务端 ping_interval=1 秒、ping_timeout=1 秒)')
    CLI = '''
import socketio, time, sys
c = socketio.Client(); c.connect("http://127.0.0.1:%d", transports=["websocket"]); print("connected", flush=True); time.sleep(60)
'''
    with Srv(PI=1, PT=1) as s:
        c = socketio.Client(); c.connect(f'http://127.0.0.1:{s.port}', transports=['websocket']); time.sleep(0.3); c.disconnect(); time.sleep(0.5)
        lines = [l for l in LOGF.read_text().splitlines() if ' disconnect ' in l]; rs = [l.split('reason=')[1] for l in lines]; print('  客户端主动 disconnect():服务端 disconnect 的 reason =', rs); R['clean'] = rs
        LOGF.write_text('')
        p = subprocess.Popen([PY, '-c', CLI % s.port], stdout=subprocess.PIPE, text=True); p.stdout.readline(); time.sleep(0.5)
        t_kill = time.time(); p.kill(); p.wait()
        waitfor(lambda: ' disconnect ' in LOGF.read_text(), 10); ln = [l for l in LOGF.read_text().splitlines() if ' disconnect ' in l]
        t_d = float(ln[0].split()[0]); print(f'  kill -9 客户端进程(系统关掉 TCP 连接):服务端 {t_d - t_kill:.2f} 秒后触发 disconnect,reason={ln[0].split("reason=")[1]}'); R['kill'] = [round(t_d - t_kill, 2), ln[0].split('reason=')[1]]
        LOGF.write_text('')
        p = subprocess.Popen([PY, '-c', CLI % s.port], stdout=subprocess.PIPE, text=True); p.stdout.readline(); time.sleep(0.5)
        t_stop = time.time(); p.send_signal(signal.SIGSTOP)
        waitfor(lambda: ' disconnect ' in LOGF.read_text(), 15); ln = [l for l in LOGF.read_text().splitlines() if ' disconnect ' in l]
        if ln: t_d = float(ln[0].split()[0]); print(f'  SIGSTOP 冻住客户端(进程还在、TCP 连接没关,只是不回应 ping):服务端 {t_d - t_stop:.2f} 秒后触发 disconnect,reason={ln[0].split("reason=")[1]}'); R['stop'] = [round(t_d - t_stop, 2), ln[0].split('reason=')[1]]
        else: print('  15 秒内没有触发 disconnect'); R['stop'] = None
        p.send_signal(signal.SIGCONT); p.kill(); p.wait()
    print()
    print('== 六:两个 gunicorn worker:没有 message_queue 时广播只到同一个 worker 上的客户端;配上 redis 消息队列后到全部')
    for label, mq in (('无 message_queue', ''), (f'message_queue=redis://127.0.0.1:{RP}', f'redis://127.0.0.1:{RP}')):
        with Srv(workers=2, MQ=mq) as s:
            time.sleep(0.5); cl = []; got = []; pids = []
            for i in range(8):
                c = socketio.Client(); c.on('bcast', (lambda i: lambda m: got.append(i))(i)); c.connect(f'http://127.0.0.1:{s.port}', transports=['websocket']); pids.append(c.call('whoami', timeout=3)); cl.append(c)
            cl[0].emit('bcast', 'x'); time.sleep(0.8)
            dist = {p: pids.count(p) for p in set(pids)}; print(f'  {label:<42} 8 个客户端分布在 {len(dist)} 个 worker({sorted(dist.values())}),A 广播(不含自己)后收到的客户端数:{len(got)}(最多 7)'); R.setdefault('mq', {})[label] = [sorted(dist.values()), len(got)]
            for c in cl: c.disconnect()
    print()
    print('== 七:一次请求-响应的往返延迟:polling vs websocket(同一个 echo 事件,本机,50 次取中位数)')
    with Srv() as s:
        for tr in (['polling'], ['websocket']):
            c = socketio.Client(); c.connect(f'http://127.0.0.1:{s.port}', transports=tr); c.call('echo', 1, timeout=3); L = []
            for i in range(50): t0 = time.perf_counter(); c.call('echo', i, timeout=3); L.append(ms(t0))
            print(f'  {tr[0]:<10} 中位数 {median(L):.2f} ms,最大 {max(L):.1f} ms'); R.setdefault('rtt', {})[tr[0]] = [median(L), max(L)]; c.disconnect()
finally:
    rproc.terminate(); rproc.wait(5)
save('f78', R)
