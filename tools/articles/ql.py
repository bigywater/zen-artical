"""RabbitMQ 实验辅助:在 qtmp/<name>/ 下起真实的 RabbitMQ 4.3.6(Homebrew,Erlang/OTP 28),
用 rabbitmqctl 跑真实命令并原样贴输出,用 pika 1.4.4(qtmp_venv)做发布 / 消费 / 计时,用管理 API(guest)读指标。
隔离:每个节点自己的数据目录、日志、端口(9500 起,每节点占 4 个:amqp、管理、分布式、stream)、节点名 rqN@localhost;
HOME 指向 qtmp/_home(自己的 .erlang.cookie),不读 /opt/homebrew/etc/rabbitmq 的全局配置;qtmp/ 整体可删。
实验脚本用 qtmp_venv/bin/python 运行。每个实验开头 reset() 杀掉上次遗留的 beam 进程(只杀数据目录在 qtmp 下的)。"""
import os, sys, subprocess, shutil, pathlib, time, json, re, socket, signal, threading, statistics, random, atexit, base64, urllib.request, urllib.error
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'): os.environ.pop(k, None)
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
from rl import tee, save
from fl import ms, median, pr
import pika
QT = HERE / 'qtmp'; QT.mkdir(exist_ok=True)
QHOME = QT / '_home'; QHOME.mkdir(exist_ok=True)
SBIN = '/opt/homebrew/sbin'
ERL = '/opt/homebrew/opt/erlang@28/bin'
HOST = socket.gethostname()
_port = [9500]
_procs = []


def free_ports(n=4):
    while True:
        _port[0] += n; p = _port[0]
        ok = True
        for q in range(p, p + n):
            with socket.socket() as s:
                if s.connect_ex(('127.0.0.1', q)) == 0: ok = False
        if ok: return [p + i for i in range(n)]


def tidy(t):
    t = re.sub(r'\x1b\[[0-9;]*m', '', t).replace(str(QT), '/data').replace(str(HERE.parent), '<scratch>').replace(str(HERE), '<实验目录>')
    t = t.replace(HOST, 'host1').replace(HOST.split('.')[0], 'host1')
    t = re.sub(r'/private/tmp/claude-501/[^\s"\':]*?/scratchpad', '<scratch>', t)
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).lstrip('\n')


def reset():
    """杀掉上次实验遗留的 RabbitMQ 节点(只杀数据目录在 qtmp 下的 beam 进程)。"""
    subprocess.run(['pkill', '-9', '-f', str(QT) + '/'], capture_output=True)
    time.sleep(0.5)


def _kill_all():
    for p in _procs:
        try:
            if p.poll() is None: os.killpg(p.pid, signal.SIGKILL)
        except Exception: pass
atexit.register(_kill_all)


def qdir(name, clean=True):
    d = QT / name
    if clean: shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True); return d


def _env(extra=None):
    e = {'HOME': str(QHOME), 'PATH': f'{ERL}:/usr/bin:/bin:{SBIN}', 'RABBITMQ_CONF_ENV_FILE': '/dev/null', 'LANG': 'en_US.UTF-8', 'TERM': 'dumb', 'NO_COLOR': '1'}
    if extra: e.update(extra)
    return e


class Node:
    """一个 RabbitMQ 节点。conf 是额外的 rabbitmq.conf 行(列表);plugins 是额外启用的插件(management 总是启用)。"""
    def __init__(self, name, conf=(), plugins=(), clean=True, env=None, mgmt=True):
        self.name = name; self.d = qdir(name, clean)
        self.amqp, self.http, self.dist, self.stream = free_ports(4)
        self.nodename = f'{name}@localhost'
        self.conf = list(conf); self.plugins = list(plugins); self.extra_env = env or {}; self.mgmt = mgmt
        self.p = None
        self.logf = self.d / 'log' / f'{self.nodename}.log'

    def _write(self):
        d = self.d; (d / 'mnesia').mkdir(exist_ok=True); (d / 'log').mkdir(exist_ok=True)
        lines = [f'listeners.tcp.default = 127.0.0.1:{self.amqp}', 'loopback_users = none', 'log.console = false', 'log.file.level = info']
        if self.mgmt: lines += [f'management.tcp.port = {self.http}', 'management.tcp.ip = 127.0.0.1']
        if 'rabbitmq_stream' in self.plugins: lines += [f'stream.listeners.tcp.1 = 127.0.0.1:{self.stream}']
        (d / 'rabbitmq.conf').write_text('\n'.join(lines + self.conf) + '\n')
        pl = (['rabbitmq_management'] if self.mgmt else []) + self.plugins
        (d / 'enabled_plugins').write_text('[' + ','.join(pl) + '].\n')

    def env(self):
        d = self.d
        return _env(dict({'RABBITMQ_NODENAME': self.nodename, 'RABBITMQ_NODE_IP_ADDRESS': '127.0.0.1', 'RABBITMQ_NODE_PORT': str(self.amqp),
                          'RABBITMQ_DIST_PORT': str(self.dist), 'RABBITMQ_MNESIA_BASE': str(d / 'mnesia'), 'RABBITMQ_LOG_BASE': str(d / 'log'),
                          'RABBITMQ_CONFIG_FILE': str(d / 'rabbitmq.conf'), 'RABBITMQ_ENABLED_PLUGINS_FILE': str(d / 'enabled_plugins'),
                          'RABBITMQ_PID_FILE': str(d / 'pid')}, **self.extra_env))

    def start(self, wait=True, timeout=120):
        self._write()
        self.p = subprocess.Popen([f'{SBIN}/rabbitmq-server'], cwd=self.d, env=self.env(), stdout=open(self.d / 'out.log', 'w'), stderr=subprocess.STDOUT, start_new_session=True)
        _procs.append(self.p)
        if wait: self.wait(timeout)
        return self

    def wait(self, timeout=120):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.p.poll() is not None: raise RuntimeError(f'{self.name} 退出码 {self.p.returncode}\n' + self.out_tail(15))
            try:
                with socket.create_connection(('127.0.0.1', self.amqp), timeout=0.3): pass
                r = self.ctl_raw('await_startup', timeout=60)
                if r.returncode == 0: return
            except Exception: pass
            time.sleep(0.3)
        raise TimeoutError(self.name)

    def ctl_raw(self, *args, timeout=120, tool='rabbitmqctl'):
        a = [f'{SBIN}/{tool}', '-n', self.nodename] if tool != 'rabbitmq-plugins' or True else []
        return subprocess.run(a + list(args), env=self.env(), capture_output=True, text=True, errors='replace', timeout=timeout, cwd=self.d)

    def ctl(self, *args, timeout=120, tool='rabbitmqctl'):
        """返回整理过的 rabbitmqctl 输出(stdout+stderr)。"""
        try:
            r = self.ctl_raw(*args, timeout=timeout, tool=tool); return tidy(r.stdout + r.stderr)
        except subprocess.TimeoutExpired: return '(超时)'

    def sh(self, line, timeout=120, tool='rabbitmqctl', n=None, w=170):
        """打印 `$ rabbitmqctl <line>` 和真实输出。line 里不要有 shell 引号以外的特殊字符(用 shlex 拆分)。"""
        import shlex
        out = self.ctl(*shlex.split(line), timeout=timeout, tool=tool)
        print(f'  $ {tool} {line}')
        L = out.split('\n')
        if n and len(L) > n: L = L[:n] + [f'…(共 {len(out.splitlines())} 行)']
        for l in L:
            if l.strip(): print('    ' + l[:w])
        return out

    def stop(self, kill=False, timeout=60):
        if self.p and self.p.poll() is None:
            if kill:
                try: os.killpg(self.p.pid, signal.SIGKILL)
                except Exception: pass
                # 子进程里的 beam 也要杀
                subprocess.run(['pkill', '-9', '-f', f'-sname {self.nodename}|{self.d}/'], capture_output=True)
            else:
                try: self.ctl_raw('shutdown', timeout=timeout)
                except Exception: pass
            try: self.p.wait(timeout)
            except subprocess.TimeoutExpired: os.killpg(self.p.pid, signal.SIGKILL); self.p.wait()
        return self

    def restart(self, kill=False, conf=None, wait=True):
        self.stop(kill)
        if conf is not None: self.conf = list(conf)
        return self.start(wait)

    def params(self, **kw):
        kw.setdefault('heartbeat', 60)
        return pika.ConnectionParameters('127.0.0.1', self.amqp, **kw)

    def conn(self, **kw): return pika.BlockingConnection(self.params(**kw))

    def api(self, path, method='GET', body=None, timeout=15):
        r = urllib.request.Request(f'http://127.0.0.1:{self.http}/api{path}', method=method, data=json.dumps(body).encode() if body is not None else None)
        r.add_header('Authorization', 'Basic ' + base64.b64encode(b'guest:guest').decode()); r.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(r, timeout=timeout) as f:
                t = f.read().decode(); return json.loads(t) if t else None
        except urllib.error.HTTPError as e:
            return {'_error': e.code, 'body': e.read().decode(errors='replace')[:300]}

    def out_tail(self, n=20):
        try: return '\n'.join((self.d / 'out.log').read_text(errors='replace').splitlines()[-n:])
        except Exception: return ''

    def logs(self, pat=None):
        try: L = self.logf.read_text(errors='replace').splitlines()
        except Exception: return []
        return [l for l in L if not pat or re.search(pat, l)]

    def du(self):
        return int(subprocess.run(f'du -sk {self.d / "mnesia"} | cut -f1', shell=True, capture_output=True, text=True).stdout.split()[0])


def join(node, other):
    """把 node 加入 other 所在的集群(node 必须是刚起的空节点)。"""
    node.ctl('stop_app'); out = node.ctl('join_cluster', other.nodename); node.ctl('start_app'); return out


def mgmt_queue(node, q, vhost='%2F'):
    return node.api(f'/queues/{vhost}/{q}')


def wait_for(fn, timeout=30, step=0.2):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = fn()
        if v: return v
        time.sleep(step)
    return None


def fmt_props(p):
    return {k: v for k, v in p.__dict__.items() if v is not None} if p is not None else {}


# ---------- AMQP 0-9-1 帧解析 + TCP 代理(看线上真实的字节) ----------
METHODS = {(10, 10): 'Connection.Start', (10, 11): 'Connection.StartOk', (10, 30): 'Connection.Tune', (10, 31): 'Connection.TuneOk', (10, 40): 'Connection.Open', (10, 41): 'Connection.OpenOk',
           (10, 50): 'Connection.Close', (10, 51): 'Connection.CloseOk', (10, 60): 'Connection.Blocked', (10, 61): 'Connection.Unblocked', (10, 70): 'Connection.UpdateSecret', (10, 71): 'Connection.UpdateSecretOk',
           (20, 10): 'Channel.Open', (20, 11): 'Channel.OpenOk', (20, 20): 'Channel.Flow', (20, 21): 'Channel.FlowOk', (20, 40): 'Channel.Close', (20, 41): 'Channel.CloseOk',
           (40, 10): 'Exchange.Declare', (40, 11): 'Exchange.DeclareOk', (40, 20): 'Exchange.Delete', (40, 21): 'Exchange.DeleteOk', (40, 30): 'Exchange.Bind', (40, 31): 'Exchange.BindOk',
           (50, 10): 'Queue.Declare', (50, 11): 'Queue.DeclareOk', (50, 20): 'Queue.Bind', (50, 21): 'Queue.BindOk', (50, 30): 'Queue.Purge', (50, 31): 'Queue.PurgeOk', (50, 40): 'Queue.Delete', (50, 41): 'Queue.DeleteOk', (50, 50): 'Queue.Unbind', (50, 51): 'Queue.UnbindOk',
           (60, 10): 'Basic.Qos', (60, 11): 'Basic.QosOk', (60, 20): 'Basic.Consume', (60, 21): 'Basic.ConsumeOk', (60, 30): 'Basic.Cancel', (60, 31): 'Basic.CancelOk', (60, 40): 'Basic.Publish', (60, 50): 'Basic.Return', (60, 60): 'Basic.Deliver',
           (60, 70): 'Basic.Get', (60, 71): 'Basic.GetOk', (60, 72): 'Basic.GetEmpty', (60, 80): 'Basic.Ack', (60, 90): 'Basic.Reject', (60, 100): 'Basic.RecoverAsync', (60, 110): 'Basic.Recover', (60, 111): 'Basic.RecoverOk', (60, 120): 'Basic.Nack',
           (85, 10): 'Confirm.Select', (85, 11): 'Confirm.SelectOk', (90, 10): 'Tx.Select', (90, 11): 'Tx.SelectOk', (90, 20): 'Tx.Commit', (90, 21): 'Tx.CommitOk', (90, 30): 'Tx.Rollback', (90, 31): 'Tx.RollbackOk'}


class Proxy:
    """客户端 → 代理 → broker 的 TCP 转发,按 AMQP 0-9-1 帧解析两个方向的字节,记到 events:
    (相对时间 s, 方向 'C→S' / 'S→C', 通道号, 名称, 帧字节数)。cut() 断开,hole=True 时停止转发(黑洞,模拟网络不通但连接不断)。"""
    def __init__(self, target_port):
        self.target = target_port; self.events = []; self.t0 = time.perf_counter(); self.hole = False; self.conns = []; self.dd = {}; self.delay = 0.0   # delay: 每个方向单向延迟(秒),保持流水线(不是逐块 sleep)
        self.srv = socket.socket(); self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); self.srv.bind(('127.0.0.1', 0)); self.srv.listen(16)
        self.port = self.srv.getsockname()[1]; self.alive = True; self.lock = threading.Lock()
        self.bytes = {'C→S': 0, 'S→C': 0}
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while self.alive:
            try: c, _ = self.srv.accept()
            except Exception: return
            s = socket.create_connection(('127.0.0.1', self.target)); self.conns += [c, s]
            for a, b, d in ((c, s, 'C→S'), (s, c, 'S→C')): threading.Thread(target=self._pump, args=(a, b, d), daemon=True).start()

    def _pump(self, a, b, d):
        buf = b''; first = d == 'C→S'
        import queue as _q
        dq = _q.Queue()
        def sender():
            while True:
                t, x = dq.get()
                if x is None: return
                w = t - time.perf_counter()
                if w > 0: time.sleep(w)
                try: b.sendall(x)
                except Exception: return
        threading.Thread(target=sender, daemon=True).start()
        while True:
            try: x = a.recv(65536)
            except Exception: break
            if not x: break
            if self.hole:
                continue
            self.bytes[d] += len(x)
            buf += x
            if first and buf[:4] == b'AMQP':
                with self.lock: self.events.append((time.perf_counter() - self.t0, d, 0, 'ProtocolHeader', 8))
                buf = buf[8:]; first = False
            while len(buf) >= 7:
                ft, ch, sz = buf[0], int.from_bytes(buf[1:3], 'big'), int.from_bytes(buf[3:7], 'big')
                if len(buf) < 7 + sz + 1: break
                pl = buf[7:7 + sz]
                if ft == 1: name = METHODS.get((int.from_bytes(pl[0:2], 'big'), int.from_bytes(pl[2:4], 'big')), f'method{int.from_bytes(pl[0:2], "big")}.{int.from_bytes(pl[2:4], "big")}')
                elif ft == 2: name = 'ContentHeader'
                elif ft == 3: name = 'ContentBody'
                elif ft == 8: name = 'Heartbeat'
                else: name = f'frame{ft}'
                if ft == 1 and name in ('Basic.Ack', 'Basic.Nack') and len(pl) >= 13:
                    tag = int.from_bytes(pl[4:12], 'big'); bits = pl[12]
                    name += f' tag={tag} multiple={bool(bits & 1)}' + (f' requeue={bool(bits & 2)}' if name == 'Basic.Nack' else '')
                with self.lock: self.events.append((time.perf_counter() - self.t0, d, ch, name, 8 + sz))
                buf = buf[8 + sz:]
            dly = self.delay or self.dd.get(d, 0)
            if dly:
                dq.put((time.perf_counter() + dly, x)); continue
            try: b.sendall(x)
            except Exception: break
        try: b.shutdown(socket.SHUT_WR)
        except Exception: pass

    def cut(self):
        for c in self.conns:
            try: c.close()
            except Exception: pass

    def close(self):
        self.alive = False; self.cut()
        try: self.srv.close()
        except Exception: pass

    def mark(self): return len(self.events)

    def names(self, since=0, d=None):
        return [(e[1], e[2], e[3], e[4]) for e in self.events[since:] if d is None or e[1] == d]


def drain(ch, q, limit=100000):
    """用 basic_get 把队列里的消息全取出来(自动 ack),返回 body 的字符串列表"""
    r = []
    while len(r) < limit:
        mt, props, body = ch.basic_get(q, auto_ack=True)
        if mt is None: break
        r.append(body.decode())
    return r


def qdecl(ch, name, **kw):
    """声明持久队列(4.x 默认不允许非持久的非独占队列);kw 里的 arguments 等原样传"""
    kw.setdefault('durable', True)
    return ch.queue_declare(name, **kw)


def _qinfo(self, q=None, cols=('messages_ready', 'messages_unacknowledged'), vhost='/'):
    """用 rabbitmqctl 实时读队列字段(管理 API 的统计有 5 秒延迟):返回 {队列名: [值…]},只给 q 时直接返回该队列的值元组。"""
    r = self.ctl_raw('--quiet', 'list_queues', '-p', vhost, '--no-table-headers', 'name', *cols)
    res = {}
    for l in r.stdout.splitlines():
        p = l.split('\t')
        if len(p) == len(cols) + 1:
            res[p[0]] = tuple(int(x) if x.lstrip('-').isdigit() else x for x in p[1:])
    return res if q is None else res.get(q)
Node.qinfo = _qinfo


def cluster(name, k=3, conf=(), plugins=(), clean=True):
    """起 k 个节点并组成集群:名字 {name}1..{name}k;第 1 个是种子,其余 join。返回节点列表。"""
    nodes = [Node(f'{name}{i + 1}', conf=conf, plugins=plugins, clean=clean) for i in range(k)]
    for nd in nodes: nd.start()
    for nd in nodes[1:]:
        r = nd.ctl_raw('stop_app'); r = nd.ctl_raw('join_cluster', nodes[0].nodename)
        if r.returncode != 0: raise RuntimeError(r.stdout + r.stderr)
        nd.ctl_raw('start_app')
    return nodes


def queues_cmd(self, *args, timeout=60):
    """rabbitmq-queues 子命令(quorum_status、check_if_node_is_quorum_critical 等),返回整理过的输出"""
    r = subprocess.run([f'{SBIN}/rabbitmq-queues', '-n', self.nodename, *args], env=self.env(), capture_output=True, text=True, errors='replace', timeout=timeout)
    return tidy(r.stdout + r.stderr)
Node.queues_cmd = queues_cmd


def async_publish(port, queue, n_msgs, window=1000, body=b'x' * 100, persistent=True, exchange='', timeout=120):
    """用 pika SelectConnection 带 publisher confirm 异步发布 n_msgs 条(在途上限 window),返回 (耗时 ms, 收到的 Ack 个数, Nack 个数)"""
    res = {'sent': 0, 'conf': 0, 'acks': 0, 'nacks': 0, 'last': 0, 'ch': None}
    done = threading.Event(); t = {}
    props = pika.BasicProperties(delivery_mode=2 if persistent else 1)
    def go():
        chn = res['ch']
        while res['sent'] < n_msgs and res['sent'] - res['conf'] < window:
            chn.basic_publish(exchange, queue, body, props); res['sent'] += 1
    def on_confirm(frame):
        m = frame.method
        cnt = (m.delivery_tag - res['last']) if m.multiple else 1
        if m.multiple: res['last'] = m.delivery_tag
        else: res['last'] = max(res['last'], m.delivery_tag)
        if isinstance(m, pika.spec.Basic.Ack): res['acks'] += 1
        else: res['nacks'] += 1
        res['conf'] += cnt
        if res['conf'] >= n_msgs: t['end'] = time.perf_counter(); done.set()
        else: go()
    def on_ch(chn):
        res['ch'] = chn; chn.confirm_delivery(on_confirm, callback=lambda f: go())
    conn = pika.SelectConnection(pika.ConnectionParameters('127.0.0.1', port), on_open_callback=lambda c: c.channel(on_open_callback=on_ch))
    t['start'] = time.perf_counter()
    th = threading.Thread(target=conn.ioloop.start, daemon=True); th.start()
    ok = done.wait(timeout)
    try: conn.ioloop.add_callback_threadsafe(conn.close)
    except Exception: pass
    time.sleep(0.2)
    try: conn.ioloop.stop()
    except Exception: pass
    return (((t.get('end') or time.perf_counter()) - t['start']) * 1000, res['acks'], res['nacks'], ok)


KAFKA_BIN = '/opt/homebrew/opt/kafka/bin'
class KafkaNode:
    """单节点 KRaft Kafka(Homebrew 4.3.1,broker+controller 合一),端口 9580/9581,数据在 qtmp/<name>/data。仅用于与 RabbitMQ 对比的实验。"""
    def __init__(self, name, port=9580, props=None):
        self.name = name; self.d = qdir(name); self.port = port; self.p = None
        self.props = {'process.roles': 'broker,controller', 'node.id': '1', 'controller.quorum.voters': f'1@127.0.0.1:{port + 1}',
                      'listeners': f'PLAINTEXT://127.0.0.1:{port},CONTROLLER://127.0.0.1:{port + 1}', 'advertised.listeners': f'PLAINTEXT://127.0.0.1:{port}',
                      'controller.listener.names': 'CONTROLLER', 'inter.broker.listener.name': 'PLAINTEXT',
                      'listener.security.protocol.map': 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT', 'log.dirs': str(self.d / 'data'),
                      'offsets.topic.replication.factor': '1', 'transaction.state.log.replication.factor': '1', 'transaction.state.log.min.isr': '1',
                      'group.initial.rebalance.delay.ms': '0', 'num.partitions': '1', 'share.coordinator.state.topic.replication.factor': '1', 'share.coordinator.state.topic.min.isr': '1'}
        self.props.update(props or {})
    def _env(self): return dict(os.environ, KAFKA_HEAP_OPTS='-Xmx512m -Xms128m', LOG_DIR=str(self.d / 'logs'), PATH=f'/opt/homebrew/opt/openjdk@17/bin:{os.environ.get("PATH", "")}')
    def start(self, timeout=90):
        (self.d / 'server.properties').write_text('\n'.join(f'{k}={v}' for k, v in self.props.items()) + '\n')
        cid = subprocess.run([f'{KAFKA_BIN}/kafka-storage', 'random-uuid'], capture_output=True, text=True, env=self._env()).stdout.strip().splitlines()[-1]
        r = subprocess.run([f'{KAFKA_BIN}/kafka-storage', 'format', '-t', cid, '-c', str(self.d / 'server.properties')], capture_output=True, text=True, env=self._env())
        if r.returncode != 0: raise RuntimeError(r.stdout + r.stderr)
        self.p = subprocess.Popen([f'{KAFKA_BIN}/kafka-server-start', str(self.d / 'server.properties')], stdout=open(self.d / 'kafka.out', 'w'), stderr=subprocess.STDOUT, env=self._env(), start_new_session=True)
        _procs.append(self.p)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.p.poll() is not None: raise RuntimeError((self.d / 'kafka.out').read_text()[-1500:])
            try:
                with socket.create_connection(('127.0.0.1', self.port), timeout=0.3): return self
            except Exception: time.sleep(0.3)
        raise TimeoutError('kafka')
    def stop(self):
        if self.p and self.p.poll() is None:
            try: os.killpg(self.p.pid, signal.SIGTERM)
            except Exception: pass
            try: self.p.wait(30)
            except Exception: os.killpg(self.p.pid, signal.SIGKILL)
    def du(self): return int(subprocess.run(f'du -sk {self.d / "data"} | cut -f1', shell=True, capture_output=True, text=True).stdout.split()[0])
    def topics(self, *args):
        return subprocess.run([f'{KAFKA_BIN}/kafka-topics', '--bootstrap-server', f'127.0.0.1:{self.port}', *args], capture_output=True, text=True, env=self._env())
