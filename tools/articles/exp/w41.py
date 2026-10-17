import sys, os, re, struct, collections, threading, statistics, errno; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netl import *
tee('w41'); reset()
def tw_count(port=None):
    n = 0
    for l in sysout('netstat', '-an', '-p', 'tcp', timeout=60).splitlines():
        p = l.split()
        if len(p) >= 6 and p[5] == 'TIME_WAIT' and (port is None or p[3].endswith(f'.{port}') or p[4].endswith(f'.{port}')): n += 1
    return n
def serve(rcvbuf=None):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', 0)); ls.listen(4096)
    stop = threading.Event(); mode = {'close_first': False}
    def acc():
        ls.settimeout(0.2)
        while not stop.is_set():
            try: cn, _ = ls.accept()
            except socket.timeout: continue
            except OSError: break
            if mode['close_first']: cn.close()
            else:
                def h(cn=cn):
                    try: cn.recv(10)
                    except Exception: pass
                    cn.close()
                threading.Thread(target=h, daemon=True).start()
    th = threading.Thread(target=acc, daemon=True); th.start()
    return ls, ls.getsockname()[1], stop, mode

print('== 一:TIME_WAIT 持续多久:客户端主动 close 一个连接后,每 0.5 秒查一次 netstat,看这一行什么时候消失;以及系统的 MSL 设置')
for k_ in ('net.inet.tcp.msl', 'net.inet.tcp.fin_timeout'): print('  ' + sysout('sysctl', k_).strip())
ls, port, stop, mode = serve()
k = socket.create_connection(('127.0.0.1', port)); lp = k.getsockname()[1]; time.sleep(0.1); t0 = time.time(); k.close()
seen = None; gone = None
while time.time() - t0 < 50:
    st = [l.split()[5] for l in sysout('netstat', '-an', '-p', 'tcp').splitlines() if len(l.split()) >= 6 and (l.split()[3].endswith(f'.{lp}') or l.split()[4].endswith(f'.{lp}'))]
    if 'TIME_WAIT' in st and seen is None: seen = time.time() - t0
    if seen is not None and 'TIME_WAIT' not in st and gone is None: gone = time.time() - t0; break
    time.sleep(0.5)
print(f'  客户端(端口 {lp})close 之后 {seen:.1f} 秒第一次看到 TIME_WAIT,{gone:.1f} 秒时这一行消失——TIME_WAIT 持续约 {gone - seen:.1f} 秒 = 2 × MSL(2 × 15 s = 30 s)')
stop.set()

print('== 二:TIME_WAIT 的作用之一:占住四元组,防止旧连接的迟到包被新连接误收。看新连接能不能复用同一个本地端口:客户端绑定固定源端口,连接 → close → 马上用同一个源端口再连同一个服务器')
ls, port, stop, mode = serve()
src = None
for att in range(5):
    k = socket.socket(); k.bind(('127.0.0.1', 0)); src = k.getsockname()[1]; k.connect(('127.0.0.1', port)); k.close(); break
time.sleep(0.2)
for nm, reuse in (('不设 SO_REUSEADDR', False), ('设 SO_REUSEADDR', True)):
    k2 = socket.socket()
    if reuse: k2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        k2.bind(('127.0.0.1', src)); r = '绑定成功'
        try: k2.connect(('127.0.0.1', port)); r += ',connect 成功'
        except OSError as e: r += f',connect 失败:{e.strerror}'
    except OSError as e: r = f'绑定失败:{e.strerror}'
    print(f'  同一个源端口 {src}、同一个服务器,{nm}:{r}')
    k2.close(); time.sleep(0.2)
stop.set()

print('== 三:谁会留下 TIME_WAIT:谁先 close 谁留下。同样建立并关闭 500 个连接,客户端先关 vs 服务端先关,看 TIME_WAIT 出现在哪一侧(按端口号区分:服务端口 / 临时端口)')
for who in ('client', 'server'):
    ls, port, stop, mode = serve(); mode['close_first'] = (who == 'server')
    for i in range(500):
        k = socket.create_connection(('127.0.0.1', port))
        if who == 'client': k.close()
        else:
            k.settimeout(1)
            try: k.recv(10)
            except Exception: pass
            k.close()
    time.sleep(0.5)
    srv_side = cli_side = 0
    for l in sysout('netstat', '-an', '-p', 'tcp', timeout=60).splitlines():
        p_ = l.split()
        if len(p_) >= 6 and p_[5] == 'TIME_WAIT':
            if p_[3].endswith(f'.{port}'): srv_side += 1       # 本地端口是服务端口 → 这是服务端的套接字
            elif p_[4].endswith(f'.{port}'): cli_side += 1
    print(f'  {"客户端" if who == "client" else "服务端"}先 close:TIME_WAIT 里,服务端一侧(本地端口 = 服务端口){srv_side} 个,客户端一侧(本地是临时端口){cli_side} 个')
    stop.set(); time.sleep(0.3)
print('  所以“服务器上有大量 TIME_WAIT”往往是因为服务器主动关闭了连接(如 HTTP 短连接 Connection: close、超时踢人);客户端的 TIME_WAIT 则会占用客户端的临时端口')

print('== 四:大量 TIME_WAIT 的后果:客户端对同一个服务器连续建立再关闭很多短连接,临时端口 49152~65535(16384 个)被 TIME_WAIT 占满以后新连接会怎样')
ls, port, stop, mode = serve()
ok = 0; err = None; t0 = time.time()
for i in range(40000):
    try:
        k = socket.socket(); k.connect(('127.0.0.1', port)); k.close(); ok += 1
    except OSError as e:
        err = e; k.close(); break
dt = time.time() - t0
print(f'  连续建立 / 关闭短连接:成功 {ok} 次后' + (f'第 {ok + 1} 次失败:[Errno {err.errno}] {err.strerror}(用时 {dt:.1f} 秒)' if err else f'40000 次都成功(用时 {dt:.1f} 秒)'))
twn = tw_count(port); print(f'  此刻 netstat 里和这个服务端口有关的 TIME_WAIT 有 {twn} 个(临时端口范围一共 16384 个)')
if err:
    ok2 = bad2 = 0
    for i in range(200):
        try: k = socket.socket(); k.connect(('127.0.0.1', port)); k.close(); ok2 += 1
        except OSError: bad2 += 1; k.close()
    print(f'  失败之后立刻再试 200 次:成功 {ok2} 次、失败 {bad2} 次——端口快用完时,随机挑到已被占用的端口就失败,所以不是“一个都没剩”才失败,而是越到后面失败越频繁')
    t1 = time.time(); drained = None
    while time.time() - t1 < 60:
        left = tw_count(port)
        if left < 50: drained = time.time() - t1; break
        time.sleep(2)
    print(f'  不再建立新连接,等 TIME_WAIT 过期:{"%.0f 秒后只剩不到 50 个" % drained if drained else "60 秒内没有降到 50 个以下"}(最早的一批是 ' + f'{dt:.1f} 秒前建立的;每个 TIME_WAIT 持续约 30 秒)')
stop.set()

print('== 五:绕过 TIME_WAIT 的办法与代价:SO_LINGER(开,0)让 close() 直接发 RST,不留 TIME_WAIT;连接数同样 500 个,对比两种关闭方式留下的 TIME_WAIT 个数')
for nm, ling in (('正常 close()', False), ('SO_LINGER(开,0 秒)后 close()', True)):
    ls, port, stop, mode = serve()
    for i in range(500):
        k = socket.create_connection(('127.0.0.1', port))
        if ling: k.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        k.close()
    time.sleep(0.6)
    print(f'  客户端 {nm}:建立并关闭 500 个连接后,和这个服务端口有关的 TIME_WAIT 有 {tw_count(port)} 个')
    stop.set(); time.sleep(0.3)
print('  linger 0 把 TIME_WAIT 省掉了,但代价是:对方没读完的数据会丢,迟到的旧包也可能被新连接收到;更常见的正确做法是让客户端主动关闭 / 用连接池 / 调大临时端口范围')
