"""网络协议实验辅助(前缀 w)。实验脚本用 wtmp_venv/bin/python 运行。
- Cap(filter, iface='lo0', ...):后台 tcpdump(需要 /dev/bpf* 可读),with 结束后 .lines 是原始输出;norm() 把随机的客户端端口换成 C1/C2…,把时间戳换成相对毫秒
- lossy(loss, delay, bw):with 里在 lo0 的 9400-9499 端口上造丢包 / 单向延迟 / 限速(靠 /Library/netlab/netlab,dummynet;退出时一定关掉)
- tcp_info(sock):macOS 的 TCP_CONNECTION_INFO(RTT、cwnd、ssthresh、重传字节等)
- read_pcap(path):用 dpkt 读 tcpdump -w 写的 lo0 抓包(link-type NULL),返回 [(时间戳, dpkt.ip.IP)]
- lab_port():9400-9499 里挑一个空闲端口(这个范围才会受 netlab 影响)"""
import warnings; warnings.filterwarnings('ignore')
import os, sys, subprocess, shutil, pathlib, time, json, re, socket, signal, threading, statistics, random, atexit, struct, ctypes, contextlib
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'): os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'
from rl import tee, save
from fl import ms, median, pr
WT = HERE / 'wtmp'; WT.mkdir(exist_ok=True)
NETLAB = '/Library/netlab/netlab'
_port = [9399]
_procs = []


def netlab(*args):
    r = subprocess.run(['sudo', '-n', NETLAB, *map(str, args)], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


@contextlib.contextmanager
def lossy(loss=0, delay=0, bw=0):
    """loss 单位 %,delay 单位 ms(每个方向各加一次,往返 = 2×),bw 单位 Kbit/s(0 不限)"""
    out = netlab('on', loss, delay, bw)
    try: yield out
    finally: netlab('off')
atexit.register(lambda: netlab('off'))


def lab_port():
    while True:
        _port[0] += 1
        if _port[0] > 9499: _port[0] = 9400
        p = _port[0]
        with socket.socket() as s:
            try: s.bind(('127.0.0.1', p)); s.close(); return p
            except OSError: continue


def reset():
    subprocess.run(['pkill', '-f', 'tcpdump -i'], capture_output=True)
    netlab('off'); time.sleep(0.3)


def tidy(t):
    t = re.sub(r'\x1b\[[0-9;]*m', '', t).replace(str(HERE.parent), '<scratch>').replace(str(HERE), '<实验目录>')
    t = re.sub(r'/private/tmp/claude-501/[^\s"\':]*?/scratchpad', '<scratch>', t)
    return '\n'.join(l.rstrip() for l in t.rstrip().split('\n')).lstrip('\n')


class Cap:
    """with Cap('tcp port 9401') as c: …;c.lines 是 tcpdump 的文本输出(-nn -tt),c.pcap 是 -w 写出的文件(如果给了 write=True)"""
    def __init__(self, flt='', iface='lo0', verbose=0, hexdump=False, write=False, snaplen=None, extra=()):
        self.flt = flt; self.iface = iface; self.verbose = verbose; self.hexdump = hexdump; self.write = write; self.snaplen = snaplen; self.extra = list(extra)
        self.lines = []; self.pcap = None
    def __enter__(self):
        a = ['tcpdump', '-i', self.iface, '-nn', '-l', '-tt', '-U', '--immediate-mode'] + ['-' + 'v' * self.verbose] * (1 if self.verbose else 0)
        if self.hexdump: a.append('-X')
        if self.snaplen: a += ['-s', str(self.snaplen)]
        a += self.extra
        if self.write:
            Cap._n = getattr(Cap, '_n', 0) + 1; self.pcap = WT / f'cap_{os.getpid()}_{Cap._n}_{int(time.time() * 1000) % 100000}.pcap'; a += ['-w', str(self.pcap)]
        a += self.flt.split() if self.flt else []
        self.p = subprocess.Popen(a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace')
        _procs.append(self.p)
        # 等到 "listening on" 出现在 stderr 才算就绪
        t0 = time.time(); self.err = ''
        import select
        while time.time() - t0 < 5:
            r, _, _ = select.select([self.p.stderr], [], [], 0.1)
            if r:
                l = self.p.stderr.readline(); self.err += l
                if 'listening on' in l: break
            if self.p.poll() is not None: raise RuntimeError('tcpdump 启动失败: ' + self.err + self.p.stderr.read())
        time.sleep(0.2)
        return self
    def __exit__(self, *a):
        time.sleep(0.4)
        self.p.send_signal(signal.SIGINT)
        try: out, err = self.p.communicate(timeout=5)
        except subprocess.TimeoutExpired: self.p.kill(); out, err = self.p.communicate()
        self.err += err; self.out = out
        if self.write:
            r = subprocess.run(['tcpdump', '-r', str(self.pcap), '-nn', '-tt'] + (['-' + 'v' * self.verbose] if self.verbose else []) + (['-X'] if self.hexdump else []), capture_output=True, text=True, errors='replace')
            out = r.stdout
        self.lines = [l for l in out.splitlines() if l.strip()]
        m = re.search(r'(\d+) packets captured', self.err); self.count = int(m.group(1)) if m else len(self.lines)


def norm(lines, base=None, ephemeral=40000, names=None, mask_mac=True):
    """把 -tt 的时间戳换成相对第一个包的毫秒(+0.000),随机的临时端口换成 C1、C2……(同一个端口始终同名);verbose 输出的续行也一起处理;MAC 地址只保留前 3 字节。返回行列表。"""
    names = {} if names is None else names; out = []; t0 = base
    def sub(mm):
        p = int(mm.group(2))
        if p >= ephemeral:
            names.setdefault(p, f'C{len(names) + 1}'); return mm.group(1) + '.' + names[p]
        return mm.group(0)
    for l in lines:
        m = re.match(r'^(\d+\.\d+) (.*)$', l)
        if m:
            t = float(m.group(1)); rest = m.group(2)
            if t0 is None: t0 = t
            head = f'+{(t - t0) * 1000:8.3f} ms  '
        else:
            rest = l.lstrip(); head = ' ' * 14 + '  ' if l.startswith(' ') else ''
        rest = re.sub(r'(\d+\.\d+\.\d+\.\d+)\.(\d+)', sub, rest)
        if mask_mac: rest = re.sub(r'\b([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}):[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}\b', r'\1:xx:xx:xx', rest)
        out.append(head + rest)
    return out


def show(lines, n=30, w=150, **kw):
    L = norm(lines, **kw)
    for l in L[:n]: print('  ' + l[:w])
    if len(L) > n: print(f'  …(共 {len(L)} 行)')


def read_pcap(path):
    import dpkt
    out = []
    with open(path, 'rb') as f:
        pc = dpkt.pcap.Reader(f); lt = pc.datalink()
        for ts, buf in pc:
            try:
                if lt == 0: ip = dpkt.ip.IP(buf[4:]); ip.raw = buf[4:]        # lo0: DLT_NULL,前 4 字节是地址族;ip.raw 是抓到的原始 IP 包字节(dpkt 重新打包会重算校验和,所以要用原始字节)
                elif lt == 1:
                    e = dpkt.ethernet.Ethernet(buf)
                    if e.type != 0x0800: continue          # 只要 IPv4(ARP / IPv6 帧的 data 不是 IP 包)
                    ip = e.data; ip.raw = buf[14:]
                else: continue
                out.append((ts, ip))
            except Exception: pass
    return out


# macOS 的 struct tcp_connection_info
class _TCI(ctypes.Structure):
    _fields_ = [('state', ctypes.c_uint8), ('snd_wscale', ctypes.c_uint8), ('rcv_wscale', ctypes.c_uint8), ('_pad1', ctypes.c_uint8),
                ('options', ctypes.c_uint32), ('flags', ctypes.c_uint32), ('rto', ctypes.c_uint32), ('maxseg', ctypes.c_uint32),
                ('snd_ssthresh', ctypes.c_uint32), ('snd_cwnd', ctypes.c_uint32), ('snd_wnd', ctypes.c_uint32), ('snd_sbbytes', ctypes.c_uint32),
                ('rcv_wnd', ctypes.c_uint32), ('rttcur', ctypes.c_uint32), ('srtt', ctypes.c_uint32), ('rttvar', ctypes.c_uint32),
                ('tfo', ctypes.c_uint32), ('txpackets', ctypes.c_uint64), ('txbytes', ctypes.c_uint64), ('txretransmitbytes', ctypes.c_uint64),
                ('rxpackets', ctypes.c_uint64), ('rxbytes', ctypes.c_uint64), ('rxoutoforderbytes', ctypes.c_uint64), ('txretransmitpackets', ctypes.c_uint64)]
TCP_CONNECTION_INFO = 0x106
def tcp_info(sock):
    buf = sock.getsockopt(socket.IPPROTO_TCP, TCP_CONNECTION_INFO, ctypes.sizeof(_TCI))
    t = _TCI.from_buffer_copy(buf.ljust(ctypes.sizeof(_TCI), b'\0'))
    d = {f[0]: getattr(t, f[0]) for f in _TCI._fields_ if not f[0].startswith('_')}
    d['srtt_ms'] = d['srtt'] / 1.0; return d


def sysrun(*argv, timeout=20, env=None, input=None):
    """通过 sysd.py(系统 python 常驻进程)执行系统命令,返回 (返回码, stdout, stderr)。arp / ndp / netstat 等必须走这里,直接 subprocess 会看不到邻居表(见 sysd.py 说明)。"""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(timeout + 5)
    s.connect('/tmp/netl_sysd.sock')
    s.sendall((json.dumps({'argv': list(argv), 'timeout': timeout, 'env': env, 'input': input}) + '\n').encode())
    buf = b''
    while not buf.endswith(b'\n'):
        d = s.recv(65536)
        if not d: break
        buf += d
    s.close(); r = json.loads(buf.decode()); return r['rc'], r['out'], r['err']
def sysout(*argv, **kw):
    rc, out, err = sysrun(*argv, **kw); return out + err


def priv(t):
    """隐私:链路本地 IPv6 地址只保留 fe80::…;192.168.a.b/前缀 里没写全四段的网络号(netstat 常见)也遮掉;MAC 只保留前 3 字节。"""
    t = re.sub(r'fe80:[0-9a-f:]*(%\w+)?', lambda m: 'fe80::…' + (m.group(1) or ''), t)
    t = re.sub(r'192\.168\.\d+(?:\.\d+)?(/\d+)?', lambda m: '<本机局域网IP>' + (m.group(1) or ''), t)
    t = re.sub(r'\b([0-9a-f]{1,2}:[0-9a-f]{1,2}:[0-9a-f]{1,2}):[0-9a-f]{1,2}:[0-9a-f]{1,2}:[0-9a-f]{1,2}\b', r'\1:xx:xx:xx', t)
    return t
