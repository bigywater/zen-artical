import sys, os, signal, subprocess, textwrap, random, json, sqlite3, collections; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pl import *
tee('p33')
d = pdir('p33')
N = 300; BODY = 100 * 1024; EVERY = 25
CHILD = textwrap.dedent(r"""
    import sys, os, json, time, sqlite3, concurrent.futures as cf, threading
    import requests
    design, state, port, N, every = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    urls = [f"http://127.0.0.1:{port}/p/{i}" for i in range(N)]
    s = requests.Session(); s.mount("http://", requests.adapters.HTTPAdapter(pool_maxsize=16))
    lock = threading.Lock()
    corrupt = False
    results = {}
    if design in ("json_direct", "json_atomic"):
        if os.path.exists(state):
            try: results = json.load(open(state))["results"]
            except Exception: corrupt = True; results = {}
    elif design.startswith("sqlite"):
        db = sqlite3.connect(state, check_same_thread=False, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL"); db.execute("PRAGMA synchronous=NORMAL")
        db.execute("CREATE TABLE IF NOT EXISTS r(url TEXT PRIMARY KEY, body TEXT)")
        done_rows = {u for (u,) in db.execute("SELECT url FROM r")}
        results = {u: "" for u in done_rows}
    todo = [u for u in urls if u not in results]
    print(json.dumps(dict(start=1, corrupt=corrupt, already=len(results), todo=len(todo))), flush=True)
    pending_batch = []
    def snapshot():
        data = json.dumps({"results": results})
        if design == "json_atomic":
            tmp = state + ".tmp"
            with open(tmp, "w") as f: f.write(data); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, state)
        else:
            with open(state, "w") as f: f.write(data)
    def fetch(u):
        r = s.get(u, timeout=10); body = r.text
        with lock:
            results[u] = body
            if design in ("json_direct", "json_atomic"):
                if len(results) % every == 0: snapshot()
            elif design == "sqlite_each":
                db.execute("INSERT OR REPLACE INTO r VALUES(?,?)", (u, body))
            elif design == "sqlite_batch":
                pending_batch.append((u, body))
                if len(pending_batch) >= every:
                    db.execute("BEGIN"); db.executemany("INSERT OR REPLACE INTO r VALUES(?,?)", pending_batch); db.execute("COMMIT"); pending_batch.clear()
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(8) as ex: list(ex.map(fetch, todo))
    if design in ("json_direct", "json_atomic"): snapshot()
    elif design == "sqlite_batch" and pending_batch:
        db.execute("BEGIN"); db.executemany("INSERT OR REPLACE INTO r VALUES(?,?)", pending_batch); db.execute("COMMIT")
    print(json.dumps(dict(finished=1, secs=time.perf_counter() - t0, total=len(results))), flush=True)
""")
(d / 'c.py').write_text(CHILD)
env = {k: v for k, v in os.environ.items() if 'proxy' not in k.lower()}
BODYTXT = 'x' * BODY
def srv(h): time.sleep(0.01); h.reply(200, BODYTXT)

def run(design, kill_at=None, state=None, every=EVERY):
    p = subprocess.Popen([sys.executable, str(d / 'c.py'), design, state, str(SV.port), str(N), str(every)], stdout=subprocess.PIPE, text=True, env=env)
    if kill_at is not None:
        time.sleep(kill_at); p.send_signal(signal.SIGKILL); p.wait(); out = p.stdout.read(); return out
    out = p.stdout.read(); p.wait(); return out

def lastjson(out, key):
    for l in reversed([x for x in out.splitlines() if x.strip()]):
        j = json.loads(l)
        if key in j: return j
    return None

DESIGNS = [('memory', '只放内存(没有持久化)'), ('json_direct', 'JSON 快照,每 25 个 URL 直接覆盖写'), ('json_atomic', 'JSON 快照,每 25 个写临时文件 + fsync + 原子改名'), ('sqlite_each', 'SQLite(WAL),每抓完一个 URL 提交一次'), ('sqlite_batch', 'SQLite(WAL),每 25 个 URL 批量提交一次')]
TRIALS = 20
rng = random.Random(33)
with Srv(srv) as SV:
    print(f'== 一:没有崩溃时,各设计抓完 {N} 个 URL(每个响应 {BODY // 1024} KB、8 个线程)的耗时(每种 5 次取中位数)')
    base = {}
    for design, lab in DESIGNS:
        ts = []
        for t in range(5):
            st = str(d / f'{design}_run_{t}.state'); SV.reset(); out = run(design, None, st); ts.append(lastjson(out, 'finished')['secs'])
        sz = os.path.getsize(st) if os.path.exists(st) else 0
        base[design] = median(ts)
        print(f'  {lab}:{median(ts):.2f} 秒;状态文件 {sz / 1048576:.1f} MiB')

    print(f'== 二:爬的过程中,在随机时刻用 SIGKILL 杀掉爬虫进程(落在各设计自己无崩溃耗时的 15%–85% 之间),再重新启动让它从保存的状态续爬;每种设计重复 {TRIALS} 次')
    print(f'  {"设计":<34}{"状态文件损坏":>12}{"重复抓取(平均)":>14}{"重复抓取(最少/最多)":>18}{"遗漏":>6}')
    for design, lab in DESIGNS:
        dup, corrupt, miss = [], 0, 0
        for t in range(TRIALS):
            SV.reset(); st = str(d / f'{design}_{t}.state')
            kill_at = rng.uniform(0.15, 0.85) * base[design]
            run(design, kill_at, st)
            out = run(design, None, st)
            j = lastjson(out, 'start')
            corrupt += bool(j and j['corrupt'])
            cnt = collections.Counter(l['path'] for l in SV.log)
            fin = lastjson(out, 'finished')
            miss += sum(1 for i in range(N) if cnt[f'/p/{i}'] == 0) if fin and fin['total'] == N else N
            dup.append(sum(cnt.values()) - N)
        print(f'  {lab:<30}{corrupt:>8} / {TRIALS}{sum(dup) / TRIALS:>14.0f}{min(dup):>12} / {max(dup):<5}{miss:>6}')

    print('== 三:被杀的那一刻,服务器已经收到了多少个不同的 URL、状态文件里保存了多少个(6 次的结果,每项 = 服务器收到 / 文件里保存)')
    for design, lab in DESIGNS[1:]:
        have = []
        for t in range(6):
            st = str(d / f'{design}_c_{t}.state'); SV.reset(); run(design, rng.uniform(0.3, 0.7) * base[design], st)
            n_srv = len({l['path'] for l in SV.log})
            if design.startswith('sqlite'):
                try: db = sqlite3.connect(st); n = db.execute('SELECT count(*) FROM r').fetchone()[0]
                except Exception: n = -1
            else:
                try: n = len(json.load(open(st))['results'])
                except Exception: n = -1
            have.append((n, n_srv))
        print(f'  {lab}:' + ', '.join(f'{b}/{a if a >= 0 else "损坏"}' for a, b in have))
purge()
