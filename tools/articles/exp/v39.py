import sys, os, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
tee('v39'); reset()
print('nginx 优雅摘流:reload(-s reload / SIGHUP)、quit(-s quit / SIGQUIT)、stop(-s stop / SIGTERM)三种方式,以及 worker_shutdown_timeout。上游是本进程里的 Python 服务(可以设置每个请求要多久);nginx 1.31.6 单 master + 1 个 worker。用 ps 看 master 的子进程,旧 worker 会显示成 “nginx: worker process is shutting down”')
SLOW = Svc(lambda h: (time.sleep(float(h.path.split('t=')[1]) if 't=' in h.path else 0.0), h.reply(200, b'done'))[1], backlog=256)
def conf(extra=''):
    return f'upstream u {{ server 127.0.0.1:{SLOW.port}; }} {extra} server {{ listen {{port}}; location / {{ proxy_pass http://u; }} }}'
def workers(ng):
    out = sh(f'ps -o pid=,command= -p $(pgrep -P {ng.p.pid} | tr "\\n" "," | sed "s/,$//") 2>/dev/null')
    ws = [l.strip() for l in out.splitlines() if 'worker' in l]
    return len(ws), sum(1 for l in ws if 'shutting down' in l)

# ============ 一 ============
print('== 一:reload 时在途的请求。client 发一个要 3 s 的请求(/?t=3),0.5 s 之后 reload。观察:在途请求有没有完成;reload 之后新请求(新连接)是不是马上就由新 worker 处理;旧 worker 什么时候退出。比较默认与 worker_shutdown_timeout 1s')
rows = []
for name, extra in (('默认', ''), ('worker_shutdown_timeout 1s', 'worker_shutdown_timeout 1s;')):
    ng = Nginx('v39a', conf()).start()
    if extra:
        txt = (ng.d / 'nginx.conf').read_text().replace('worker_processes 1;', 'worker_processes 1; ' + extra); (ng.d / 'nginx.conf').write_text(txt); subprocess.run(['nginx', '-c', str(ng.d / 'nginx.conf'), '-p', str(ng.d), '-s', 'reload'], capture_output=True); time.sleep(0.5)
    res = {}
    def slow():
        t0 = time.perf_counter(); r = rpc(ng.port, '/?t=3', 10.0, keepalive=False); res['slow'] = (r[0], time.perf_counter() - t0)
    th = threading.Thread(target=slow); th.start(); time.sleep(0.5)
    subprocess.run(['nginx', '-c', str(ng.d / 'nginx.conf'), '-p', str(ng.d), '-s', 'reload'], capture_output=True); t_rl = time.perf_counter(); time.sleep(0.3)
    nw0 = workers(ng); t0 = time.perf_counter(); fast = rpc(ng.port, '/', 5.0, keepalive=False); fast_dt = time.perf_counter() - t0
    gone = None
    for _ in range(80):
        time.sleep(0.1)
        if workers(ng)[1] == 0 and workers(ng)[0] == 1: gone = time.perf_counter() - t_rl; break
    th.join(); ng.stop()
    rows.append((name, f"{res['slow'][0]} · {res['slow'][1]:.2f} s", f'reload 后 0.3 s:{nw0[0]} 个 worker(其中 {nw0[1]} 个在 shutting down)', f'{fast[0]} · {fast_dt * 1000:.0f} ms', f'{gone:.1f} s' if gone else '未退出'))
table(rows, ['配置', '在途的 3 s 请求', 'reload 之后的进程', 'reload 之后的新请求', '旧 worker 在 reload 之后多久退出'])
print('  reload 不会打断在途的请求:旧 worker 把手上的请求处理完才退出,新 worker 马上开始接新连接;设了 worker_shutdown_timeout 之后,到点旧 worker 强行关闭还没结束的连接,在途请求会失败')

# ============ 二 ============
print('== 二:长连接让旧 worker 堆积。上游是个一直不结束的流(每 0.5 s 发一个事件)。依次做 3 轮:每一轮先打开 2 条 SSE 式的长连接(它们落在当时的 worker 上),再 reload,隔 1 s 数一次 worker 进程;3 轮之后再等 2.5 s,数 worker,并看 client 的 6 条长连接是否还活着(能收到新事件为活着,读到 EOF 为被断开);最后关掉所有 client 连接,1 s 之后再数 worker')
def stream_backend(c):
    read_req(c); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\n\r\n')
    try:
        while True: c.sendall(b'5\r\ndata\n\r\n'); time.sleep(0.5)
    except Exception: pass
RS = Raw(stream_backend); rows = []
def alive(s):
    s.settimeout(0.2); last = time.time()
    try:
        while time.time() - last < 1.0:
            d = s.recv(65536)
            if not d: return False
    except socket.timeout: return True
    except Exception: return False
    return True
for name, extra in (('默认', ''), ('worker_shutdown_timeout 2s', 'worker_shutdown_timeout 2s;')):
    ng = Nginx('v39b', f'upstream u {{ server 127.0.0.1:{RS.port}; }} server {{ listen {{port}}; location / {{ proxy_pass http://u; }} }}').start()
    if extra:
        txt = (ng.d / 'nginx.conf').read_text().replace('worker_processes 1;', 'worker_processes 1; ' + extra); (ng.d / 'nginx.conf').write_text(txt); subprocess.run(['nginx', '-c', str(ng.d / 'nginx.conf'), '-p', str(ng.d), '-s', 'reload'], capture_output=True); time.sleep(0.5)
    socks = []; seen = []
    for k in range(3):
        for i in range(2):
            s = socket.create_connection(('127.0.0.1', ng.port)); s.sendall(b'GET / HTTP/1.1\r\nHost: x\r\n\r\n'); socks.append(s)
        time.sleep(0.3); subprocess.run(['nginx', '-c', str(ng.d / 'nginx.conf'), '-p', str(ng.d), '-s', 'reload'], capture_output=True); time.sleep(1.0); w = workers(ng); seen.append(f'{w[0]}({w[1]})')
    time.sleep(2.5); w_after = workers(ng); n_alive = sum(1 for s in socks if alive(s))
    for s in socks:
        try: s.close()
        except Exception: pass
    time.sleep(1.0); w_end = workers(ng); ng.stop()
    rows.append((name, ' → '.join(seen), f'{w_after[0]}({w_after[1]})', f'{n_alive} / 6', f'{w_end[0]}({w_end[1]})'))
table(rows, ['配置', '每轮 reload 后 1 s 的 worker 数(括号里是 shutting down 的)', '3 轮之后再过 2.5 s', 'client 的长连接还活着的', '关掉所有 client 之后 1 s'])
print('  每次 reload 产生一个新 worker,旧 worker 只要还有一条长连接就不会退出:不设 worker_shutdown_timeout 时旧 worker 一直堆积(每次发布多一个),直到 client 自己断开;设了超时,到点长连接被强行断开(client 读到 EOF),旧 worker 才退出')

# ============ 三 ============
print('== 三:reload / quit / stop。先启动 nginx,client 发一个要 2 s 的请求,0.5 s 后对 nginx 做三种操作之一,同时每 100 ms 发一个新的快速请求(新连接),共观察 3 s。统计:在途请求的结果、新请求在操作之后的结果(成功 / 连接被拒)')
rows = []
for name, action in (('reload', 'reload'), ('quit(优雅退出)', 'quit'), ('stop(快速退出)', 'stop')):
    ng = Nginx('v39c', conf()).start(); res = {}
    def slow():
        t0 = time.perf_counter(); r = rpc(ng.port, '/?t=2', 10.0, keepalive=False); res['slow'] = (r[0], time.perf_counter() - t0)
    th = threading.Thread(target=slow); th.start(); time.sleep(0.5)
    t0 = time.perf_counter(); subprocess.run(['nginx', '-c', str(ng.d / 'nginx.conf'), '-p', str(ng.d), '-s', action], capture_output=True)
    fast = []
    while time.perf_counter() - t0 < 3.0:
        r = rpc(ng.port, '/', 2.0, keepalive=False); fast.append((time.perf_counter() - t0, r[0])); time.sleep(0.1)
    th.join(); cnt = collections.Counter(st for t, st in fast)
    try: ng.p.wait(3)
    except Exception: pass
    rows.append((name, f"{res['slow'][0]} · {res['slow'][1]:.2f} s", dict(cnt)))
    ng.stop()
table(rows, ['操作', '在途的 2 s 请求', '操作之后 3 s 里新请求的结果(状态码:个数)'])
print('  quit 让 master 立刻关闭监听端口、不再接新连接,等在途请求处理完再退出:在途请求成功,但新连接在 nginx 退出前后一直被拒绝(状态是 error 表示连接被拒或重置),在发布时应当先把流量摘走再 quit;stop 立刻结束,在途请求失败;reload 监听端口不关,新连接一直成功')
