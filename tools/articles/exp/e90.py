import subprocess, sys, os, tempfile, time, signal, json, textwrap

W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
SCRIPT = textwrap.dedent('''
    import atexit, os, sys, time, signal, threading
    MODE = sys.argv[1]
    LOG = os.open("marks.log", os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    def mark(s): os.write(LOG, (s + "\\n").encode())
    atexit.register(lambda: mark("atexit"))
    class Res:
        def __del__(self): mark("__del__")
    r = Res()                                  # 模块级对象, 解释器清理时才会被销毁
    if MODE == "sigterm_handler":
        signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    print("缓冲区里的一行 print (没有 flush)", end="")     # stdout 是管道: 块缓冲
    try:
        if MODE == "return": pass
        elif MODE == "exception": raise RuntimeError("boom")
        elif MODE == "sys_exit": sys.exit(3)
        elif MODE == "os_exit": os._exit(4)
        elif MODE == "abort": os.abort()
        elif MODE == "thread_exception":
            t = threading.Thread(target=lambda: 1 / 0); t.start(); t.join()
        else:
            os.write(1, b"")                   # 让父进程知道我们到这里了
            open("ready", "w").close(); time.sleep(30)
    finally:
        mark("finally")
''')
open('t.py', 'w').write(SCRIPT)
def clean_env():
    e = dict(os.environ); e.pop('HTTP_PROXY', None); e.pop('HTTPS_PROXY', None); return e
def trial(mode, sig=None):
    for f in ('marks.log', 'ready'):
        if os.path.exists(f): os.remove(f)
    p = subprocess.Popen([sys.executable, 't.py', mode], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=clean_env())
    if sig is not None:
        for _ in range(200):
            if os.path.exists('ready'): break
            time.sleep(0.05)
        time.sleep(0.1); p.send_signal(sig)
    out, err = p.communicate(timeout=60)
    marks = open('marks.log').read().split() if os.path.exists('marks.log') else []
    return p.returncode, marks, out.decode(), err.decode().strip().splitlines()[-1:] if err.strip() else []

cases = [
    ("正常执行到末尾", "return", None), ("未捕获的异常", "exception", None), ("sys.exit(3)", "sys_exit", None),
    ("os._exit(4)", "os_exit", None), ("os.abort()", "abort", None), ("子线程里未捕获的异常", "thread_exception", None),
    ("收到 SIGINT(Ctrl+C)", "sleep", signal.SIGINT), ("收到 SIGTERM(默认处理)", "sleep", signal.SIGTERM),
    ("收到 SIGTERM, 自己注册了 handler → sys.exit", "sigterm_handler", signal.SIGTERM), ("收到 SIGKILL", "sleep", signal.SIGKILL),
]
rows = []
print("== 每种退出方式下:atexit / finally / __del__ / 缓冲 print 是否执行 ==")
print(f"  {'退出方式':<40} {'退出码':>6}  atexit  finally  __del__  缓冲输出")
for name, mode, sig in cases:
    rc, marks, out, err = trial(mode, sig)
    def yn(x): return '✓' if x else '✗'
    rows.append({'name': name, 'rc': rc, 'atexit': 'atexit' in marks, 'finally': 'finally' in marks, 'del': '__del__' in marks, 'out': bool(out), 'err': err})
    rcs = f"{rc}" if rc >= 0 else f"信号{-rc}"
    print(f"  {name:<{40 - sum(1 for c in name if ord(c) > 255)}} {rcs:>6}    {yn('atexit' in marks)}       {yn('finally' in marks)}        {yn('__del__' in marks)}        {yn(bool(out))}")
print("\n  各行的 stderr 最后一行:")
for r in rows: print(f"   {r['name']}: {r['err'][0] if r['err'] else '(无)'}")
print("\n  退出码对照: SIGINT=%d SIGTERM=%d SIGKILL=%d SIGABRT=%d" % (signal.SIGINT, signal.SIGTERM, signal.SIGKILL, signal.SIGABRT))
json.dump(rows, open(os.environ['OUT'], 'w'), ensure_ascii=False)
