import sys, os, subprocess, textwrap, json, resource; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p24')
d = pdir('p24')
def slow(h): time.sleep(0.3); h.reply(200, b'ok')
env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}

CHILD = textwrap.dedent(r'''
    import sys, os, json, resource, asyncio, time, collections, concurrent.futures as cf
    mode, port, limit, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    hard = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard))
    import requests, aiohttp
    url = f"http://127.0.0.1:{port}/"
    def nfd(): return len(os.listdir("/dev/fd")) - 1
    out = dict(fd0=nfd())
    if mode == "aio":
        errs = collections.Counter(); st = dict(ok=0, peak=0)
        async def main():
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
                async def one():
                    try:
                        async with s.get(url) as r: await r.read(); st["ok"] += 1
                    except Exception as e:
                        oe = getattr(e, "os_error", None)
                        errs[f"{type(e).__name__}:{type(oe).__name__}:{getattr(oe, 'errno', None)}"] += 1
                async def watch():
                    while True:
                        try: st["peak"] = max(st["peak"], nfd())
                        except OSError: st["peak"] = max(st["peak"], limit)    # 连数描述符本身都失败了:说明已经顶到上限
                        await asyncio.sleep(0.01)
                w = asyncio.create_task(watch())
                await asyncio.gather(*[one() for _ in range(n)]); w.cancel()
        asyncio.run(main()); out.update(ok=st["ok"], errs=dict(errs), peak=st["peak"])
    elif mode == "req":
        s = requests.Session(); s.mount("http://", requests.adapters.HTTPAdapter(pool_maxsize=n))
        def root_of(e):
            seen = 0
            while seen < 12:
                nxt = None
                for a in getattr(e, "args", ()):
                    if isinstance(a, BaseException): nxt = a; break
                if nxt is None: nxt = getattr(e, "reason", None) if isinstance(getattr(e, "reason", None), BaseException) else (e.__cause__ or e.__context__)
                if nxt is None: return e
                e = nxt; seen += 1
            return e
        def one(_):
            try: s.get(url); return "ok"
            except Exception as e:
                r = root_of(e); return f"{type(e).__name__}:{type(r).__name__}:{getattr(r, 'errno', None)}"
        with cf.ThreadPoolExecutor(n) as ex: res = list(ex.map(one, range(n)))
        c = collections.Counter(res); out.update(ok=c.pop("ok", 0), errs=dict(c))
    elif mode in ("hold", "hold_bytes", "hold_close", "hold_session"):
        keep = []; sess = requests.Session() if mode == "hold_session" else None
        try:
            for i in range(n):
                r = (sess or requests).get(url + "fast")
                if mode == "hold_bytes": keep.append(r.content)
                elif mode == "hold_close": r.close(); keep.append(r)
                else: keep.append(r)
            try: fd = nfd()
            except OSError: fd = -1
            out.update(done=len(keep), fd=fd)
        except Exception as e:
            try: fd = nfd()
            except OSError: fd = limit
            out.update(done=len(keep), fd=fd, err=type(e).__name__)
    elif mode == "delta":
        before = nfd()
        async def main():
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as s:
                async def one():
                    async with s.get(url) as r: await asyncio.sleep(0.2); await r.read()
                t = [asyncio.create_task(one()) for _ in range(n)]
                await asyncio.sleep(0.15); mid = nfd(); await asyncio.gather(*t)
                return mid
        mid = asyncio.run(main()); out.update(before=before, mid=mid)
    print(json.dumps(out))
''')
(d / 'c.py').write_text(CHILD)
def child(mode, port, limit, n, timeout=120):
    o = subprocess.run([sys.executable, str(d / 'c.py'), mode, str(port), str(limit), str(n)], capture_output=True, text=True, env=env, timeout=timeout)
    try: return json.loads(o.stdout.strip().splitlines()[-1])
    except Exception: return {'崩溃': o.stderr.strip().splitlines()[-1][:160] if o.stderr.strip() else o.stdout[-100:]}

soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
def fast(h): h.reply(200, b'ok')
def route(h):
    if h.path.startswith('/fast'): return fast(h)
    slow(h)
print('== 一:这台机器上的限制')
print(f'  当前 shell 的 ulimit -n(软限制):{soft};硬限制:{"unlimited" if hard > 1 << 40 else hard};内核 kern.maxfilesperproc = {subprocess.run(["sysctl", "-n", "kern.maxfilesperproc"], capture_output=True, text=True).stdout.strip()}')
try:
    resource.setrlimit(resource.RLIMIT_NOFILE, (10 ** 7, hard)); print(f'  把软限制设成 10000000:{resource.getrlimit(resource.RLIMIT_NOFILE)[0]}(设置没有报错,但内核实际能给单个进程的上限仍是 kern.maxfilesperproc;这里没有去验证真能开到多少个)')
    resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
except Exception as e: print('  设置失败', e)

with Srv(route) as sv:
    P = sv.port
    print('== 二:每个并发连接占多少个文件描述符(aiohttp,打开 20 条并发连接时在进程里数 /dev/fd)')
    r = child('delta', P, 5000, 20)
    print(f'  请求发出前 {r["before"]} 个,20 条连接都在途时 {r["mid"]} 个,每条连接多出 {(r["mid"] - r["before"]) / 20:.1f} 个')

    print('== 三:把软限制压到 100(子进程里 setrlimit),并发 300 个连接(服务器每个请求停 0.3 秒)')
    r = child('aio', P, 100, 300); print(f'  aiohttp:成功 {r.get("ok")},失败 {r.get("errs")},过程中最多同时打开 {r.get("peak")} 个描述符(起点 {r.get("fd0")})' if 'ok' in r else f'  aiohttp:{r}')
    r = child('req', P, 100, 300); print(f'  requests(300 个线程):成功 {r.get("ok")},失败 {r.get("errs")}(起点 {r.get("fd0")})' if 'ok' in r else f'  requests:{r}')
    print('  对照:同样 300 并发,软限制 5000:')
    r = child('aio', P, 5000, 300); print(f'  aiohttp:成功 {r.get("ok")},失败 {r.get("errs")},最多同时打开 {r.get("peak")} 个描述符')

    print('== 四:保留 Response 对象会让连接一直开着:软限制 100,连续发 300 个很快返回的请求,把结果存进列表')
    for mode, lab in (('hold', 'results.append(requests.get(url))(保留整个 Response)'), ('hold_close', '保留 Response,但读完后调用了 r.close()'), ('hold_bytes', 'results.append(requests.get(url).content)(只保留 bytes)'), ('hold_session', '同一个 Session.get,保留整个 Response')):
        r = child(mode, P, 100, 300)
        print(f'  {lab}:完成 {r.get("done")} 个请求' + (f',第 {r["done"] + 1} 个失败({r.get("err")})' if r.get('err') else ',全部成功') + f';结束时进程里有 {r.get("fd")} 个描述符')
purge()
