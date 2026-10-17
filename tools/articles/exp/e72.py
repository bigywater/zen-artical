import selectors, socket, time, threading, json

sel = selectors.DefaultSelector()
print("DefaultSelector =", type(sel).__name__, "| 可用实现:", [n for n in ('SelectSelector','PollSelector','KqueueSelector','EpollSelector','DevpollSelector') if hasattr(selectors, n)])

lsn = socket.socket(); lsn.bind(('127.0.0.1', 0)); lsn.listen(16)
port = lsn.getsockname()[1]
clients, servers = [], []
for i in range(5):
    c = socket.create_connection(('127.0.0.1', port)); s, _ = lsn.accept()
    s.setblocking(False); clients.append(c); servers.append(s)
    sel.register(s, selectors.EVENT_READ, data=f"c{i}")
print("5 个连接已注册, 当前线程数 =", threading.active_count())
name = {id(s): f"c{i}" for i, s in enumerate(servers)}
rounds = []

def poll(label, timeout=None, read=True):
    t = time.perf_counter(); ev = sel.select(timeout); ms = (time.perf_counter()-t)*1000
    items = []
    for key, mask in ev:
        item = key.data
        if read:
            d = key.fileobj.recv(100)
            item += f" → {d!r}"
            if d == b'': sel.unregister(key.fileobj); item += " (对端已关闭, unregister)"
        items.append(item)
    print(f"{label}: select() 用时 {ms:6.1f} ms, 返回 {len(ev)} 个就绪: {items}")
    rounds.append({'label': label, 'ms': round(ms, 1), 'ready': [k.data for k, _ in ev], 'items': items})

print("\n== 一、只有部分连接有数据 ==")
clients[1].send(b"one"); clients[3].send(b"three"); time.sleep(0.05)
poll("第1轮 c1,c3 发了数据", 1)
poll("第2轮 谁都没发", 0.3)
clients[0].send(b"zero"); clients[4].close(); time.sleep(0.05)
poll("第3轮 c0 发数据, c4 关闭", 1)

print("\n== 二、水平触发:不读就一直报 ==")
clients[2].send(b"unread"); time.sleep(0.05)
for k in range(3): poll(f"  不读, 第{k+1}次 select", 1, read=False)
poll("  第4次 select 并读走", 0.2)
poll("  读走后再 select", 0.2)

print("\n== 三、EVENT_WRITE 与发送缓冲区 ==")
a = socket.create_connection(('127.0.0.1', port)); b, _ = lsn.accept(); a.setblocking(False)
sel2 = selectors.DefaultSelector(); sel2.register(a, selectors.EVENT_WRITE)
print("新连接刚建立, 可写?", [bool(m & selectors.EVENT_WRITE) for _, m in sel2.select(0)])
sent = 0
try:
    while True: sent += a.send(b"x" * 4096)
except BlockingIOError: pass
print(f"对端一直不读, 一共写进内核 {sent} 字节后 send 抛 BlockingIOError")
print("此时 select 写事件:", sel2.select(0.2), "(空 = 不可写)")
b.recv(1 << 20)
time.sleep(0.05)
print("对端读走数据后, 可写?", [bool(m & selectors.EVENT_WRITE) for _, m in sel2.select(0.2)])

print("\n== 四、一个线程 vs 一连接一线程(200 个连接, 每个 echo 20 次) ==")
def bench_sel(N=200, R=20):
    ls = socket.socket(); ls.bind(('127.0.0.1', 0)); ls.listen(N); p = ls.getsockname()[1]
    cs, ss = [], []
    for _ in range(N):
        cs.append(socket.create_connection(('127.0.0.1', p))); ss.append(ls.accept()[0])
    sl = selectors.DefaultSelector()
    for s in ss: s.setblocking(False); sl.register(s, selectors.EVENT_READ)
    th0 = threading.active_count(); t = time.perf_counter(); done = 0
    for _ in range(R):
        for c in cs: c.send(b"ping")
        got = 0
        while got < N:
            for key, _ in sl.select():
                key.fileobj.send(key.fileobj.recv(16)); got += 1
        for c in cs: c.recv(16)
    el = time.perf_counter()-t; peak = threading.active_count()
    for x in cs+ss+[ls]: x.close()
    return el, peak
def bench_thr(N=200, R=20):
    ls = socket.socket(); ls.bind(('127.0.0.1', 0)); ls.listen(N); p = ls.getsockname()[1]
    cs, ss = [], []
    for _ in range(N):
        cs.append(socket.create_connection(('127.0.0.1', p))); ss.append(ls.accept()[0])
    def worker(s):
        while True:
            d = s.recv(16)
            if not d: return
            s.send(d)
    ts = [threading.Thread(target=worker, args=(s,), daemon=True) for s in ss]
    for t_ in ts: t_.start()
    t = time.perf_counter()
    for _ in range(R):
        for c in cs: c.send(b"ping")
        for c in cs: c.recv(16)
    el = time.perf_counter()-t; peak = threading.active_count()
    for c in cs: c.close()
    for t_ in ts: t_.join()
    for x in ss+[ls]: x.close()
    return el, peak
for _ in range(1): bench_sel(20, 2)
r1 = bench_sel(); r2 = bench_thr()
print(f"selectors: {r1[0]*1000:7.1f} ms, 峰值线程数 {r1[1]}")
print(f"线程/连接: {r2[0]*1000:7.1f} ms, 峰值线程数 {r2[1]}")
json.dump({'rounds': rounds, 'sent': sent, 'sel': r1, 'thr': r2}, open('out/72.json', 'w'), ensure_ascii=False)
