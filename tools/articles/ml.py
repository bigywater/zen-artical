"""MongoDB 实验辅助:在 mtmp/<name>/ 下起真实的 mongod / mongos(MongoDB 9.0.2,Homebrew),
用 mongosh 2.12 跑真实命令并原样贴输出,用 pymongo 做批量写入、计时与多线程。
隔离:每个实验自己的 dbpath、端口(9900 起)、日志;mongosh 的 HOME 指向 mtmp/_home(关了遥测)。mtmp/ 整体可删。
macOS 上 mongod 不支持 --fork,所以用 Popen 起进程;每个实验开头 reset() 杀掉上次遗留的进程。"""
import os, sys, subprocess, shutil, pathlib, time, json, re, socket, signal, threading, statistics, random, atexit, datetime
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'): os.environ.pop(k, None)
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
from rl import tee, save
from fl import ms, median, pr
import pymongo, bson
from pymongo import MongoClient
from bson import ObjectId, Int64, Decimal128, Binary, Timestamp
MT = HERE / 'mtmp'; MT.mkdir(exist_ok=True)
MHOME = MT / '_home'; MHOME.mkdir(exist_ok=True)
MONGOD = '/opt/homebrew/bin/mongod'; MONGOS = '/opt/homebrew/bin/mongos'; MONGOSH = '/opt/homebrew/bin/mongosh'
HOST = socket.gethostname()
_port = [9900]
_procs = []
BASE = datetime.datetime(2026, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)


def free_port():
    while True:
        _port[0] += 1; p = _port[0]
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1', p)) != 0: return p


def tidy(t):
    t = re.sub(r'\x1b\[[0-9;]*m', '', t).replace(str(MT), '/data').replace(str(HERE.parent), '<scratch>').replace(str(HERE), '<实验目录>')
    t = t.replace(HOST, 'host1').replace(HOST.split('.')[0], 'host1')
    t = re.sub(r'/private/tmp/claude-501/[^\s"\':]*?/scratchpad', '<scratch>', t)
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).lstrip('\n')


def reset():
    """杀掉上次实验遗留的 mongod / mongos(只杀 dbpath 在 mtmp 下的)。"""
    subprocess.run(['pkill', '-9', '-f', str(MT) + '/'], capture_output=True)
    time.sleep(0.3)


def _kill_all():
    for p in _procs:
        try:
            if p.poll() is None: p.kill()
        except Exception: pass
atexit.register(_kill_all)


def mdir(name, clean=True):
    d = MT / name
    if clean: shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True); return d


class Node:
    """一个 mongod 进程。args 里的 {port} 会被替换。"""
    def __init__(self, name, port=None, args=(), clean=True, mongos=False, cache=0.25, root=None, journal=True):
        self.name = name; self.port = port or free_port(); self.mongos = mongos
        self.d = root or mdir(name, clean); self.db = self.d / 'db'; self.db.mkdir(exist_ok=True)
        self.args = [str(a).replace('{port}', str(self.port)) for a in args]; self.cache = cache
        self.p = None
        self.logf = self.d / 'mongod.log'

    @property
    def uri(self): return f'mongodb://127.0.0.1:{self.port}'
    @property
    def addr(self): return f'127.0.0.1:{self.port}'

    def cmd(self):
        if self.mongos:
            return [MONGOS, '--port', str(self.port), '--bind_ip', '127.0.0.1', '--nounixsocket', '--logpath', str(self.logf), *self.args]
        c = [MONGOD, '--dbpath', str(self.db), '--port', str(self.port), '--bind_ip', '127.0.0.1', '--nounixsocket', '--logpath', str(self.logf)]
        if self.cache and '--wiredTigerCacheSizeGB' not in self.args: c += ['--wiredTigerCacheSizeGB', str(self.cache)]
        return c + self.args

    def start(self, wait=True, timeout=60):
        self.p = subprocess.Popen(self.cmd(), cwd=self.d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        _procs.append(self.p)
        if wait: self.wait(timeout)
        return self

    def wait(self, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.p.poll() is not None: raise RuntimeError(f'{self.name} 退出码 {self.p.returncode}\n' + self.log_tail(8))
            try:
                c = MongoClient(self.uri, directConnection=True, serverSelectionTimeoutMS=300)
                c.admin.command('ping'); c.close(); return
            except Exception: time.sleep(0.2)
        raise TimeoutError(self.name)

    def stop(self, kill=False, timeout=30):
        if self.p and self.p.poll() is None:
            self.p.send_signal(signal.SIGKILL if kill else signal.SIGTERM)
            try: self.p.wait(timeout)
            except subprocess.TimeoutExpired: self.p.kill(); self.p.wait()
        return self

    def restart(self, kill=False, args=None, wait=True):
        self.stop(kill)
        if args is not None: self.args = [str(a) for a in args]
        return self.start(wait)

    def client(self, **kw):
        kw.setdefault('directConnection', True)
        return MongoClient(self.uri, **kw)

    def log_tail(self, n=20):
        try: return '\n'.join(self.logf.read_text(errors='replace').splitlines()[-n:])
        except Exception: return ''

    def logs(self, pat=None, **match):
        """解析结构化日志(每行一个 JSON),按 msg/c/id 过滤,返回 dict 列表。"""
        out = []
        for l in self.logf.read_text(errors='replace').splitlines():
            try: j = json.loads(l)
            except Exception: continue
            if pat and not re.search(pat, l): continue
            if all(j.get(k) == v for k, v in match.items()): out.append(j)
        return out

    def du(self):
        return int(subprocess.run(f'du -sk {self.db} | cut -f1', shell=True, capture_output=True, text=True).stdout.split()[0])


def mongosh(uri, js, db='test', timeout=120, **kw):
    """用真实的 mongosh --eval 运行一段 JS,返回 (rc, 整理过的输出)。"""
    if isinstance(uri, Node): uri = uri.uri
    env = {'PATH': '/usr/bin:/bin:/opt/homebrew/bin', 'HOME': str(MHOME), 'NO_COLOR': '1', 'TERM': 'dumb', 'LANG': 'en_US.UTF-8'}
    env.update(kw)
    try:
        r = subprocess.run([MONGOSH, '--quiet', '--norc', f'{uri}/{db}' if '/' not in uri.split('//', 1)[1] else uri, '--eval', js], env=env, capture_output=True, text=True, errors='replace', timeout=timeout)
        return r.returncode, tidy(r.stdout + r.stderr)
    except subprocess.TimeoutExpired as ex:
        o = ex.stdout.decode() if isinstance(ex.stdout, bytes) else (ex.stdout or '')
        return -9, tidy(o) + '\n(超时)'


def msh(node, js, db='test', n=40, w=170, show=True, ind='  ', timeout=120, label=None, note=None, **kw):
    """打印 'db> js' 与 mongosh 的真实输出,返回输出字符串。多行 JS 的后续行用 '... ' 开头。"""
    rc, o = mongosh(node, js, db, timeout, **kw)
    if show:
        if note: print(f'{ind}# {note}')
        ls = (label or js).strip('\n').split('\n')
        print(f'{ind}{db}> {ls[0]}'.rstrip())
        for l in ls[1:]: print(f'{ind}... {l}'.rstrip())
        if o: pr(o, n, ind, w)
    return o


def msh0(node, js, db='test', **kw):
    """静默运行,返回输出。"""
    return mongosh(node, js, db, **kw)[1]


def jv(node, js, db='test'):
    """静默运行并把结果当 EJSON 解析:js 要 return 一个值,例如 'db.c.countDocuments({})'。"""
    rc, o = mongosh(node, f'EJSON.stringify(({js}), null, 0)', db)
    try: return json.loads(o)
    except Exception: raise RuntimeError(f'jv 失败: {js}\n{o}')


def bench(fn, n=5, warm=1):
    for _ in range(warm): fn()
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); fn(); ts.append((time.perf_counter() - t0) * 1000)
    return median(ts)


def fm(x): return f'{x:.0f} ms' if x >= 10 else f'{x:.1f} ms'


class ReplSet:
    """n 个 mongod 组成副本集。members: 可覆盖每个成员的配置 dict 列表(priority / votes / arbiterOnly / hidden / secondaryDelaySecs ...)。"""
    def __init__(self, name, n=3, members=None, args=(), cache=0.25, oplog=128, settings=None, rsname=None, extra_each=None):
        self.name = name; self.rs = rsname or ('rs' + name); self.nodes = []
        root = mdir(name)
        for i in range(n):
            a = ['--replSet', self.rs, '--oplogSize', str(oplog), *args, *(extra_each[i] if extra_each else [])]
            self.nodes.append(Node(f'{name}/n{i}', args=a, cache=cache, clean=True, root=mdir(f'{name}/n{i}')))
        self.members = members or [{} for _ in range(n)]; self.settings = settings

    def start(self, init=True, timeout=60):
        for nd in self.nodes: nd.start()
        if init: self.initiate(timeout)
        return self

    def config(self):
        ms_ = []
        for i, (nd, m) in enumerate(zip(self.nodes, self.members)):
            ms_.append({'_id': i, 'host': nd.addr, **m})
        c = {'_id': self.rs, 'members': ms_}
        if self.settings: c['settings'] = self.settings
        return c

    def initiate(self, timeout=60):
        c = self.nodes[0].client(); c.admin.command('replSetInitiate', self.config()); c.close()
        self.wait_primary(timeout)

    def wait_primary(self, timeout=60, exclude=()):
        t0 = time.time()
        while time.time() - t0 < timeout:
            for i, nd in enumerate(self.nodes):
                if i in exclude or nd.p is None or nd.p.poll() is not None: continue
                try:
                    c = nd.client(serverSelectionTimeoutMS=300); h = c.admin.command('hello'); c.close()
                    if h.get('isWritablePrimary'): return i
                except Exception: pass
            time.sleep(0.3)
        raise TimeoutError('没有选出 primary')

    def primary(self): return self.nodes[self.wait_primary()]

    def wait_secondaries(self, timeout=60):
        """等所有(非仲裁)成员都进入 SECONDARY / PRIMARY 状态。"""
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                c = self.primary().client(); st = c.admin.command('replSetGetStatus'); c.close()
                if all(m['stateStr'] in ('PRIMARY', 'SECONDARY', 'ARBITER') for m in st['members']): return st
            except Exception: pass
            time.sleep(0.4)
        raise TimeoutError('成员没有就绪')

    def client(self, **kw):
        return MongoClient(self.uri(), replicaSet=self.rs, **kw)

    def uri(self): return 'mongodb://' + ','.join(nd.addr for nd in self.nodes)

    def stop(self, kill=False):
        for nd in self.nodes: nd.stop(kill)


class Cluster:
    """分片集群:1 个单节点 config server 副本集 + shards 个单节点分片副本集 + 1 个 mongos。"""
    def __init__(self, name, shards=2, args=(), chunk_mb=None):
        self.name = name; root = mdir(name)
        self.cfg = Node(f'{name}/cfg', args=['--configsvr', '--replSet', 'cfg', '--oplogSize', '64'], root=mdir(f'{name}/cfg'))
        self.shards = [Node(f'{name}/sh{i}', args=['--shardsvr', '--replSet', f'sh{i}', '--oplogSize', '64', *args], root=mdir(f'{name}/sh{i}')) for i in range(shards)]
        self.mongos = None; self.chunk_mb = chunk_mb

    def start(self):
        self.cfg.start()
        c = self.cfg.client(); c.admin.command('replSetInitiate', {'_id': 'cfg', 'configsvr': True, 'members': [{'_id': 0, 'host': self.cfg.addr}]}); c.close()
        for i, s in enumerate(self.shards):
            s.start(); c = s.client(); c.admin.command('replSetInitiate', {'_id': f'sh{i}', 'members': [{'_id': 0, 'host': s.addr}]}); c.close()
        for n_ in [self.cfg] + self.shards: self._wait_primary(n_)
        self.mongos = Node(f'{self.name}/mongos', mongos=True, args=['--configdb', f'cfg/{self.cfg.addr}'], root=mdir(f'{self.name}/mongos'))
        self.mongos.start()
        c = self.mongos.client()
        for i, s in enumerate(self.shards): c.admin.command('addShard', f'sh{i}/{s.addr}')
        if self.chunk_mb:
            c.config.settings.update_one({'_id': 'chunksize'}, {'$set': {'value': self.chunk_mb}}, upsert=True)
        c.close(); return self

    def _wait_primary(self, nd, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                c = nd.client(); h = c.admin.command('hello'); c.close()
                if h.get('isWritablePrimary'): return
            except Exception: pass
            time.sleep(0.3)
        raise TimeoutError(nd.name)

    def client(self, **kw): return self.mongos.client(directConnection=False, **kw)

    def stop(self):
        for n_ in [self.mongos] + self.shards + [self.cfg]:
            if n_: n_.stop()


def sec_(title): print(f'== {title}')


def gen_docs(n, seed=1, fields=None):
    """确定性的测试文档:_id 自增,a 为 0..99 的整数,b 为 0..999 的整数,s 为 20 字符字符串。"""
    r = random.Random(seed)
    return [{'_id': i, 'a': r.randrange(100), 'b': r.randrange(1000), 's': ''.join(r.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(20))} for i in range(n)]


def jpp(o, ind=2, lvl=0):
    """把 pymongo 返回的 BSON 值格式化成 mongosh 风格的文本(用于展示 pymongo 取到的结果)。"""
    pad = ' ' * (ind * (lvl + 1)); pad0 = ' ' * (ind * lvl)
    if isinstance(o, dict):
        if not o: return '{}'
        return '{\n' + ',\n'.join(f'{pad}{k}: {jpp(v, ind, lvl + 1)}' for k, v in o.items()) + f'\n{pad0}}}'
    if isinstance(o, (list, tuple)):
        if not o: return '[]'
        if all(not isinstance(x, (dict, list)) for x in o) and len(o) <= 12: return '[ ' + ', '.join(jpp(x) for x in o) + ' ]'
        return '[\n' + ',\n'.join(f'{pad}{jpp(v, ind, lvl + 1)}' for v in o) + f'\n{pad0}]'
    if isinstance(o, ObjectId): return f"ObjectId('{o}')"
    if isinstance(o, Int64): return f"Long('{int(o)}')"
    if isinstance(o, Decimal128): return f"Decimal128('{o}')"
    if isinstance(o, datetime.datetime): return f"ISODate('{o.strftime('%Y-%m-%dT%H:%M:%S.') + '%03d' % (o.microsecond // 1000)}Z')"
    if isinstance(o, Timestamp): return f'Timestamp({{ t: {o.time}, i: {o.inc} }})'
    if isinstance(o, str): return "'" + o.replace("'", "\\'") + "'"
    if o is None: return 'null'
    if isinstance(o, bool): return 'true' if o else 'false'
    if isinstance(o, bytes): return f"Binary.createFromBase64('{__import__('base64').b64encode(o).decode()}')"
    return repr(o)


def hexdump(b, n=96, ind='  '):
    for i in range(0, min(len(b), n), 16):
        ch = b[i:i + 16]
        print(f'{ind}{i:04x}  ' + ' '.join(f'{x:02x}' for x in ch).ljust(48) + '  ' + ''.join(chr(x) if 32 <= x < 127 else '.' for x in ch))
    if len(b) > n: print(f'{ind}…(共 {len(b)} 字节)')


def setup_home():
    """首次使用:关掉 mongosh 的遥测与更新检查(写在隔离的 HOME 里)。"""
    flag = MHOME / '.setup_done'
    if flag.exists(): return
    env = {'PATH': '/usr/bin:/bin:/opt/homebrew/bin', 'HOME': str(MHOME)}
    subprocess.run([MONGOSH, '--quiet', '--nodb', '--norc', '--eval', 'disableTelemetry(); config.set("enableTelemetry", false); config.set("updateURL", "")'], env=env, capture_output=True, timeout=60)
    flag.write_text('ok')
setup_home()


# ---------- explain 摘要(JS,可拼进 msh 的脚本) ----------
EXJS = ('function chain(p) { if (!p) return ""; var s = p.stage + (p.indexName ? "(" + p.indexName + ")" : ""); '
        'if (p.inputStages) s += "[" + p.inputStages.map(chain).join(" | ") + "]"; if (p.inputStage) s += " > " + chain(p.inputStage); if (p.shards) s += "{shards}"; return s }; '
        'function ex(e) { var wp = e.queryPlanner.winningPlan; var root = wp.queryPlan || wp; var st = e.executionStats || {}; '
        'return {plan: chain(root), nReturned: st.nReturned, keysExamined: st.totalKeysExamined, docsExamined: st.totalDocsExamined, ms: st.executionTimeMillis} }; ')


def fill(coll, n, mk, batch=10000):
    """批量插入 n 个文档,mk(i) 返回第 i 个文档。"""
    for i in range(0, n, batch): coll.insert_many([mk(j) for j in range(i, min(n, i + batch))], ordered=False)
