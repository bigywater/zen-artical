import os, sys, subprocess, tempfile, textwrap, time, signal, json

W = os.path.realpath(tempfile.mkdtemp()); os.chdir(W)
E = dict(os.environ); E.pop('HTTP_PROXY', None); E.pop('HTTPS_PROXY', None)

SVC = textwrap.dedent('''
    import os, sys, time, signal, threading, queue, atexit

    MODE = sys.argv[1]
    LOG = os.open("svc.log", os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    T0 = time.perf_counter()
    def mark(s): os.write(LOG, f"{time.perf_counter() - T0:6.3f} {s}\\n".encode())

    stop = threading.Event()
    jobs = queue.Queue()
    for i in range(1, 21): jobs.put(i)
    processed = []

    def work(i):
        mark(f"job {i} 开始")
        if MODE.endswith("stuck") and i == 3:
            time.sleep(60)                      # 下游卡死: 这个任务永远不会结束
        time.sleep(0.3)
        mark(f"job {i} 完成"); processed.append(i)

    def worker():
        while not stop.is_set():
            try: i = jobs.get(timeout=0.05)
            except queue.Empty: return
            work(i)

    def cleanup():
        mark(f"cleanup: 关闭连接 / 刷盘 (已完成 {len(processed)} 个, 队列里还剩 {jobs.qsize()} 个未处理)")

    atexit.register(cleanup)

    if MODE == "flag" or MODE == "flag_stuck":
        signal.signal(signal.SIGTERM, lambda s, f: (mark("收到 SIGTERM: 只设置停止标志"), stop.set()))
    elif MODE == "exit_nondaemon" or MODE == "exit_daemon":
        signal.signal(signal.SIGTERM, lambda s, f: (mark("收到 SIGTERM: 处理函数里直接 sys.exit(0)"), sys.exit(0)))
    elif MODE == "flag_watchdog_stuck":
        def h(s, f):
            mark("收到 SIGTERM: 设置停止标志, 并启动 1.0 秒的看门狗")
            stop.set(); threading.Timer(1.0, lambda: (mark("看门狗超时: os._exit(1)"), os._exit(1))).start()
        signal.signal(signal.SIGTERM, h)
    # MODE == "default": 不注册任何处理函数

    t = threading.Thread(target=worker, daemon=(MODE == "exit_daemon"))
    t.start()
    open("ready", "w").close()
    t.join()
    mark("worker 线程结束, main 返回")
''')
open('svc.py', 'w').write(SVC)

def trial(mode, send_after=0.75, wait_exit=6.0, kill_after=None):
    for f in ('svc.log', 'ready'):
        if os.path.exists(f): os.remove(f)
    p = subprocess.Popen([sys.executable, 'svc.py', mode], env=E, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while not os.path.exists('ready'): time.sleep(0.01)
    time.sleep(send_after); t_sig = time.perf_counter(); p.send_signal(signal.SIGTERM)
    killed = False
    try: p.wait(timeout=kill_after or wait_exit)
    except subprocess.TimeoutExpired:
        if kill_after: killed = True; p.kill(); p.wait()
        else: p.kill(); p.wait(); killed = True
    took = time.perf_counter() - t_sig
    log = open('svc.log').read().strip().splitlines() if os.path.exists('svc.log') else []
    return {'mode': mode, 'rc': p.returncode, 'took': took, 'killed_by_parent': killed, 'log': log}

cases = [
    ("default", "不写任何处理函数(默认处置)", None),
    ("flag", "处理函数只设置「停止标志」,工作线程做完手头的活再退出", None),
    ("exit_nondaemon", "处理函数里直接 sys.exit(0),工作线程是普通线程", 3.0),
    ("exit_daemon", "处理函数里直接 sys.exit(0),工作线程是守护线程", None),
    ("flag_stuck", "设置停止标志,但当前任务卡死(下游不返回)", 3.0),
    ("flag_watchdog_stuck", "设置停止标志 + 1 秒看门狗,当前任务卡死", None),
]
results = []
for mode, label, kill_after in cases:
    r = trial(mode, kill_after=kill_after); r['label'] = label; results.append(r)
    how = "由父进程 SIGKILL(等了 %.1f 秒仍未退出)" % kill_after if r['killed_by_parent'] else "自己退出"
    rc = r['rc']; rcs = f"退出码 {rc}" if rc >= 0 else f"被信号 {-rc} 终止"
    print(f"== {mode}: {label} ==")
    print(f"  SIGTERM 发出后 {r['took']:.2f} 秒进程结束 | {rcs} | {how}")
    for l in r['log']: print("    " + l)
    print()
json.dump(results, open(os.path.join(os.environ['HERE'], 'out/110.json'), 'w'), ensure_ascii=False)
