import sys, os, time, json, re, subprocess, signal, threading; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z52'); R = {}
n = Node('z52', 7300, conf={'tickTime': 1000}).start(); w = client('127.0.0.1:7300'); w.ensure_path('/services/web')
INST = "import sys, time, os, signal; sys.path.insert(0, '.')\nfrom zkl import client\nz = client('127.0.0.1:7300', timeout=%d); z.create('/services/web/inst-%s', b'host:1', ephemeral=True); print('up', flush=True)\nmode = '%s'\nif mode == 'close': time.sleep(1); z.stop(); z.close()\nelif mode == 'kill': time.sleep(1); os.kill(os.getpid(), signal.SIGKILL)\nelse: time.sleep(300)\n"
def trial(mode, timeout_s, tag):
    gone = {}; t0 = [None]
    kids0 = set(w.get_children('/services/web'))
    def watch(ev):
        cur = set(w.get_children('/services/web', watch=watch))
        if f'inst-{tag}' not in cur and 'at' not in gone and t0[0] is not None: gone['at'] = time.perf_counter()
    w.get_children('/services/web', watch=watch)
    p = subprocess.Popen([sys.executable, '-c', INST % (timeout_s, tag, mode)], cwd=HERE, stdout=subprocess.PIPE, text=True); p.stdout.readline()
    assert f'inst-{tag}' in w.get_children('/services/web')
    if mode == 'freeze': time.sleep(0.5); t0[0] = time.perf_counter(); p.send_signal(signal.SIGSTOP)
    else:
        time.sleep(1.0); t0[0] = time.perf_counter(); p.wait()
        if mode == 'kill': pass
    for _ in range(400):
        if 'at' in gone: break
        time.sleep(0.05)
    p.kill(); return (gone['at'] - t0[0]) * 1000 if 'at' in gone else None
print('== 一:服务实例注册成临时节点,另一个客户端 watch 它的父节点。实例消失多久后,watcher 才发现?(tickTime=1000 ms)')
print(f'  {"消失方式":<26} {"会话超时":>8} {"watcher 发现用时 ms":>20}')
R['rows'] = []
for mode, lbl in (('close', '正常退出(close 会话)'), ('kill', 'kill -9(没来得及 close)'), ('freeze', '进程冻结(SIGSTOP,如长 GC)')):
    for to in ((None,) if mode == 'close' else (3, 10)):
        t = trial(mode, to or 6, f'{mode}{to or 0}'); R['rows'].append((lbl, to, t)); print(f'  {lbl:<26} {("%d s" % to) if to else "6 s":>8} {("%.0f" % t) if t else "(未发现)":>20}')
print()
print('== 二:Watcher 自己看到的延迟包括什么:会话超时 + 服务端检查会话过期的粒度(tickTime)——kill -9 的会话超时 3 s 与 10 s 的差值')
a = [x[2] for x in R['rows'] if x[0].startswith('kill') and x[1] == 3][0]; b = [x[2] for x in R['rows'] if x[0].startswith('kill') and x[1] == 10][0]
print(f'  3 s → {a:.0f} ms;10 s → {b:.0f} ms;差 {b - a:.0f} ms(≈ 7000 ms 的超时差)'); R['diff'] = b - a
w.stop(); n.stop(); save('z52', R)
