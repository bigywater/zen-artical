import sys, os, re, struct, threading, statistics, errno, logging, logging.handlers, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path = [q for q in sys.path if os.path.abspath(q) != os.path.dirname(os.path.abspath(__file__))]
from netl import *
import dpkt
tee('w103'); reset()
FAC = ['kern', 'user', 'mail', 'daemon', 'auth', 'syslog', 'lpr', 'news', 'uucp', 'cron', 'authpriv', 'ftp', 'ntp', 'audit', 'alert', 'clock', 'local0', 'local1', 'local2', 'local3', 'local4', 'local5', 'local6', 'local7']
SEV = ['emerg', 'alert', 'crit', 'err', 'warning', 'notice', 'info', 'debug']
def udp_rx(port, stop, store, rcvbuf=None, delay=0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if rcvbuf: s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
    s.bind(('127.0.0.1', port)); s.settimeout(0.3)
    def run():
        while not stop[0]:
            try: d, a = s.recvfrom(65535)
            except socket.timeout: continue
            store.append(d)
            if delay: time.sleep(delay)
        s.close()
    threading.Thread(target=run, daemon=True).start(); return s
def tcp_rx(port, stop, store):
    ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind(('127.0.0.1', port)); ls.listen(8); ls.settimeout(0.3)
    def h(c):
        c.settimeout(3); buf = b''
        try:
            while True:
                d = c.recv(65536)
                if not d: break
                buf += d
        except Exception: pass
        store.extend(x for x in buf.split(b'\0') if x) if b'\0' in buf else store.extend(x for x in buf.split(b'\n') if x)
    def acc():
        while not stop[0]:
            try: c, _ = ls.accept()
            except socket.timeout: continue
            threading.Thread(target=h, args=(c,), daemon=True).start()
        ls.close()
    threading.Thread(target=acc, daemon=True).start()

print('== 一:RFC 3164(传统 BSD syslog)的报文长什么样:<PRI>时间 主机名 标签[进程号]: 消息。用 Python 的 SysLogHandler 发几条不同设施 / 级别的日志,接收端是本机一个 UDP 套接字,逐条解码')
port = lab_port(); stop = [False]; got = []; udp_rx(port, stop, got)
lg = logging.getLogger('w103a'); lg.setLevel(logging.DEBUG); lg.handlers.clear()
for fac, lvl, fn in ((logging.handlers.SysLogHandler.LOG_AUTH, logging.WARNING, 'warning'), (logging.handlers.SysLogHandler.LOG_DAEMON, logging.INFO, 'info'), (logging.handlers.SysLogHandler.LOG_LOCAL0, logging.ERROR, 'error'), (logging.handlers.SysLogHandler.LOG_MAIL, logging.DEBUG, 'debug')):
    h = logging.handlers.SysLogHandler(address=('127.0.0.1', port), facility=fac); h.setFormatter(logging.Formatter('w103app[%(process)d]: %(message)s')); lg.addHandler(h); getattr(lg, fn)(f'sample {fn} message'); lg.removeHandler(h); h.close(); time.sleep(0.05)
time.sleep(0.3)
print('    原始报文(线上字节)                                           PRI  设施(PRI÷8)       级别(PRI mod 8)')
for d in got:
    m = re.match(rb'<(\d+)>', d); pri = int(m.group(1)); print(f'    {d!r:<60} {pri:>3}  {FAC[pri // 8]:<10}({pri // 8:>2})   {SEV[pri % 8]:<8}({pri % 8})')
print('  PRI = 设施 × 8 + 级别:例如 auth(4)+ warning(4)→ 4 × 8 + 4 = 36。注意这个传统格式里**没有时间戳和主机名**(Python 的 SysLogHandler 不写,由接收端补)——接收端只能用“收到的时间”和“发送方 IP”,发送方的时间与身份无法验证')

print('== 二:RFC 5424(现代 syslog)的格式:<PRI>版本 时间戳 主机名 应用名 进程号 消息ID [结构化数据] 消息。手工拼一条,发出,再解析')
msg = '<165>1 2026-10-15T12:34:56.789Z host1.example.net w103app 4321 ID47 [exampleSDID@32473 iut="3" eventSource="Application" eventID="1011"] An application event log entry'
p5 = re.match(r'<(\d+)>(\d+) (\S+) (\S+) (\S+) (\S+) (\S+) (\[.*?\]|-) ?(.*)', msg); pri = int(p5.group(1))
print(f'  原文:{msg}')
print(f'  解析:PRI {pri} = 设施 {FAC[pri // 8]}({pri // 8})× 8 + 级别 {SEV[pri % 8]}({pri % 8});版本 {p5.group(2)};时间戳 {p5.group(3)}(ISO 8601,带时区和毫秒);主机名 {p5.group(4)};应用名 {p5.group(5)};进程号 {p5.group(6)};消息 ID {p5.group(7)};结构化数据 {p5.group(8)[:40]}…;消息 {p5.group(9)!r}')
print('  5424 把时间戳、主机名、应用名放进了格式本身,并增加了结构化数据([ID k="v" …]),比 3164 更容易被机器解析')

print('== 三:UDP syslog 没有任何送达保证。lo0 上 netlab 加丢包(每方向),发送端发 500 条,接收端数收到多少;对比 TCP syslog(SysLogHandler 的 socktype = SOCK_STREAM,字节流不丢)')
def run_udp(loss, n=500):
    port = lab_port(); stop = [False]; store = []; udp_rx(port, stop, store)
    with lossy(loss=loss, delay=5, bw=0):
        lg = logging.getLogger(f'w103u{loss}'); lg.setLevel(logging.INFO); lg.handlers.clear(); h = logging.handlers.SysLogHandler(address=('127.0.0.1', port)); lg.addHandler(h)
        for i in range(n): lg.info(f'event {i:04d}'); time.sleep(0.002)
        time.sleep(0.5); h.close()
    stop[0] = True; time.sleep(0.4); return len(store), n
def run_tcp(loss, n=500):
    port = lab_port(); stop = [False]; store = []; tcp_rx(port, stop, store)
    with lossy(loss=loss, delay=5, bw=0):
        lg = logging.getLogger(f'w103t{loss}'); lg.setLevel(logging.INFO); lg.handlers.clear(); h = logging.handlers.SysLogHandler(address=('127.0.0.1', port), socktype=socket.SOCK_STREAM); lg.addHandler(h)
        for i in range(n): lg.info(f'event {i:04d}'); time.sleep(0.002)
        time.sleep(1.0); h.close()
    stop[0] = True; time.sleep(3.5); return len(store), n
for loss in (0, 10, 30):
    ru = run_udp(loss); rt = run_tcp(loss)
    print(f'  丢包 {loss:>2}%:UDP 发 {ru[1]} 条,接收端收到 {ru[0]} 条(丢了 {ru[1] - ru[0]} 条,{(ru[1] - ru[0]) / ru[1]:.1%});TCP 发 {rt[1]} 条,接收端收到 {rt[0]} 条(丢了 {rt[1] - rt[0]} 条)')
print('  UDP 丢的包发送端完全不知道:syslog 没有确认机制,出问题时恰恰是网络不稳、日志最重要的时候')

print('== 四:接收端来不及处理也会丢:发送端一口气发 20000 条(每条约 60 字节),接收端的 UDP 缓冲区(SO_RCVBUF)设得很小,且每条处理 1 ms')
for rb, nm in ((None, '默认缓冲区'), (8192, 'SO_RCVBUF = 8 KiB')):
    port = lab_port(); stop = [False]; store = []; udp_rx(port, stop, store, rcvbuf=rb, delay=0.0005); snd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    t0 = time.time()
    for i in range(20000): snd.sendto(f'<14>w103app: burst message number {i:05d} with some padding to look real'.encode(), ('127.0.0.1', port))
    dt = time.time() - t0; time.sleep(3); stop[0] = True; time.sleep(0.4)
    print(f'  {nm}:发送端 {dt:.2f} 秒发完 20000 条;接收端处理完收到 {len(store)} 条,丢了 {20000 - len(store)} 条({(20000 - len(store)) / 20000:.1%});发送端不知道丢了')
print('== 五:没有认证:任何能把 UDP 包送到 514 端口的人都能伪造日志,接收端无法区分。伪造一条“来自 sshd 的登录成功”日志')
port = lab_port(); stop = [False]; store = []; udp_rx(port, stop, store); f = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
forged = b'<38>Oct 15 12:00:00 victim-host sshd[999]: Accepted password for root from 203.0.113.9 port 51234 ssh2'; f.sendto(forged, ('127.0.0.1', port)); time.sleep(0.4)
print(f'  接收端收到:{store[0]!r}——这条日志完全是我伪造的(没有任何 sshd,主机名 victim-host 也是我写的)。收到后只能看到来源 IP(UDP 也能伪造源地址),内容的真实性无法验证;这就是为什么审计日志需要 TLS 传输 + 签名,或者放在可信的本机再转发')
stop[0] = True
