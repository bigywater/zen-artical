import sys, os, signal, subprocess, textwrap, json, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p34')
d = pdir('p34')
env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
def srv(h): time.sleep(0.3); h.reply(200, b'ok')

# 子进程:asyncio 爬虫,抓 200 个 URL,8 个并发。mode 决定怎么处理 SIGINT
CHILD = textwrap.dedent(r"""
    import sys, asyncio, signal, json, time, aiohttp
    mode, port, N = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    log = []
    async def main():
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        q = asyncio.Queue()
        for i in range(N): q.put_nowait(i)
        done = []; started = []
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
            async def worker():
                while not (mode in ("graceful", "graceful_drain") and stop.is_set()):
                    try: i = q.get_nowait()
                    except asyncio.QueueEmpty: return
                    started.append(i)
                    try:
                        async with s.get(f"http://127.0.0.1:{port}/p/{i}") as r: await r.read()
                        done.append(i)
                    except asyncio.CancelledError:
                        log.append(f"取消:{i}"); raise
            if mode == "default":
                pass
            elif mode in ("graceful", "graceful_drain"):
                loop.add_signal_handler(signal.SIGINT, stop.set)
            ws = [asyncio.create_task(worker()) for _ in range(8)]
            try:
                await asyncio.gather(*ws)
            finally:
                print(json.dumps(dict(done=len(done), started=len(started), left_in_queue=q.qsize(), log=log[:3], nlog=len(log))), flush=True)
    try: asyncio.run(main())
    except KeyboardInterrupt: print(json.dumps(dict(keyboardinterrupt=True)), flush=True)
""")
(d / 'c.py').write_text(CHILD)
N = 200
def run(mode, sig=signal.SIGINT, delay=0.3, n=N, wave=8):
    """等服务器收到第一批 wave 个(都在途)请求后立刻发信号,返回子进程的行为。"""
    def srv_d(h): time.sleep(delay); h.reply(200, b'ok')
    with Srv(srv_d) as sv:
        p = subprocess.Popen([sys.executable, str(d / 'c.py'), mode, str(sv.port), str(n)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        for _ in range(400):
            if len(sv.log) >= wave: break
            time.sleep(0.01)
        t0 = time.perf_counter(); p.send_signal(sig)
        try: out, err = p.communicate(timeout=30)
        except subprocess.TimeoutExpired: p.kill(); out, err = p.communicate(); err += '(超时被强制杀掉)'
        el = ms(t0)
        js = [json.loads(l) for l in out.splitlines() if l.strip().startswith('{')]
        return dict(rc=p.returncode, el=el, js=js, err=err.strip().splitlines()[-1][:90] if err.strip() else '', recv=len(sv.log))

print('== 一:不处理信号的默认行为:8 个请求在途时,爬虫收到 SIGINT(Ctrl-C)')
r = run('default')
print(f'  退出码 {r["rc"]}(脚本里捕获了 KeyboardInterrupt,所以是 0),从发信号到退出 {r["el"]:.0f} ms')
for j in r['js']: print(f'  进程最后的输出:{j}')
print(f'  服务器共收到 {r["recv"]} 个请求;asyncio.run 在收到 SIGINT 时取消了主任务,在途的请求被取消(连接被关闭),队列里剩下的 URL 没有被处理')
print('== 二:自己用 loop.add_signal_handler 捕获 SIGINT,设标志,让每个 worker 做完手头的请求就退出')
r = run('graceful'); j = r['js'][-1]
print(f'  退出码 {r["rc"]},发信号后 {r["el"]:.0f} ms 退出(服务器每个请求 0.3 秒);完成 {j["done"]} 个,开始过 {j["started"]} 个,队列里还剩 {j["left_in_queue"]} 个没开始;被取消的请求 {j["nlog"]} 个')
print(f'  服务器共收到 {r["recv"]} 个请求;完成数 = 开始数 → 没有请求被半路丢掉;剩下的 {j["left_in_queue"]} 个 URL 还留在队列里,可以保存下来下次再抓')
print('== 三:不同信号:不处理信号时 SIGTERM 与 SIGKILL;只给 SIGINT 装了处理器时来 SIGTERM')
for sig, nm in ((signal.SIGTERM, 'SIGTERM'), (signal.SIGKILL, 'SIGKILL')):
    r = run('default', sig)
    print(f'  不处理信号时收到 {nm}:退出码 {r["rc"]}(负数表示被该信号杀死),{r["el"]:.0f} ms 退出;进程有没有机会输出收尾信息:{bool(r["js"])}')
r = run('graceful', signal.SIGTERM)
print(f'  只给 SIGINT 装了处理器时收到 SIGTERM:退出码 {r["rc"]},{r["el"]:.0f} ms 退出;进程有没有机会输出收尾信息:{bool(r["js"])}')
print('== 四:优雅停止的代价:从发信号到退出的时间取决于在途请求还要多久(第一批 8 个请求刚到达服务器时发 SIGINT)')
for delay in (0.3, 1.0, 2.0):
    r = run('graceful', delay=delay); j = r['js'][-1]
    print(f'  服务器每个请求 {delay} 秒:发信号后 {r["el"]:.0f} ms 退出;完成 {j["done"]} 个,队列里剩 {j["left_in_queue"]} 个')
purge()
