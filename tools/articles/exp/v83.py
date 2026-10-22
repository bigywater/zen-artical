import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from msl import *
import subprocess as sp
tee('v83'); reset()
print('Sidecar 的流量劫持:iptables 规则做了什么。在 Docker Desktop 的 Linux 容器里(python:3.12-alpine,加 NET_ADMIN,iptables v1.8.10 nf_tables,宿主机是 macOS 所以必须用容器)搭一个 Istio 风格的最小实验:出站规则把容器里所有发出的 TCP 连接 REDIRECT 到 sidecar 监听的 15001 端口,sidecar(我写的 50 行 Python,以 uid 1337 运行)用 SO_ORIGINAL_DST 取到原始目的地址再转发;入站规则把进入的连接 REDIRECT 到 15006。所有输出都来自容器里真实运行的脚本')
D = pathlib.Path(__file__).resolve().parent.parent / 'vtmp/v83'
def dk(*a, check=True, timeout=300):
    r = sp.run(['docker', *a], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0: raise RuntimeError(r.stderr[-800:])
    return r
sp.run(['docker', 'rm', '-f', 'v83a'], capture_output=True)
dk('run', '-d', '--name', 'v83a', '--cap-add', 'NET_ADMIN', '-v', f'{D}:/w', 'python:3.12-alpine', 'sh', '-c', 'apk add --no-cache iptables >/dev/null 2>&1 && python3 /w/lab.py')
t0 = time.time()
while time.time() - t0 < 120:
    if sp.run(['docker', 'exec', 'v83a', 'test', '-f', '/tmp/inbound_done'], capture_output=True).returncode == 0: break
    time.sleep(1.0)
else: raise RuntimeError('lab 没有走到入站这一步:' + dk('logs', 'v83a', check=False).stdout[-1500:])
logs = [json.loads(l) for l in dk('logs', 'v83a').stdout.splitlines() if l.startswith('{')]; R = {k: v for d in logs for k, v in d.items()}; ip = R['ip']
cli = lambda path: dk('run', '--rm', 'python:3.12-alpine', 'python3', '-c', f"import urllib.request;print(urllib.request.urlopen('http://{ip}:{path}', timeout=3).read().decode())", check=False)
r8080 = cli('8080/in'); r3306 = cli('3306/direct')
dk('exec', 'v83a', 'touch', '/tmp/stop'); time.sleep(2.0)
logs = [json.loads(l) for l in dk('logs', 'v83a').stdout.splitlines() if l.startswith('{')]; R = {k: v for d in logs for k, v in d.items()}
sp.run(['docker', 'rm', '-f', 'v83a'], capture_output=True)

# ============ 一 ============
print('== 一:没有规则与有规则。应用(uid 0)去连一个“服务地址” 10.99.0.5:8080(这个地址在容器的网络里不存在,代表 Kubernetes 的 ClusterIP)。(a)没有任何 iptables 规则;(b)装上下面的出站规则并启动 sidecar(映射:10.99.0.5:8080 → 后端 127.0.0.1:9000)后,应用代码一行不改,再请求同一个地址')
print(f'  (a)没有规则:{R["baseline_no_rules"]}')
print('  (b)装上的 nat 表规则(iptables -t nat -S):')
for l in R['rules']: print(f'      {l}')
print(f'  应用请求同一个地址:{R["redirected"]}')
print('  sidecar 的日志:')
for l in R['sidecar_log']: print(f'      {l}')
print('  MESH_OUT 链的计数器(pkts bytes target … 一行一条规则,iptables -v -n -x):')
for l in R['counters']: print(f'      {l}')
print('  OUTPUT 链上所有 TCP 先跳进 MESH_OUT;以 uid 1337(sidecar 自己)发出的和目的地是 127.0.0.1 的先放行(RETURN),其余的 REDIRECT 到 15001;应用连的明明是 10.99.0.5:8080,sidecar 看到的连接来自应用,靠 SO_ORIGINAL_DST 取回应用想连的地址。每条规则的计数都只有 1 个包、60 字节(正好是一个 TCP SYN 包),而不是整个请求的包数:nat 表只处理一条连接的第一个包,同一条连接后面的包按已经建立的转换记录走(这一点是我对 netfilter 的了解,计数器的数字与它一致,没有另外验证)')

# ============ 二 ============
L = R['loop']
print('== 二:没有 “放行自己” 的规则会怎样。去掉 uid 1337 和 127.0.0.1 这两条 RETURN 规则,只留下 REDIRECT。sidecar 限制最多处理 30 个连接以免无限循环。应用请求同一个地址')
print(f'  应用的结果:{L["app"]}')
print(f'  sidecar 在 3 s 内接受的连接数:{L["accepted"]}(上限 30);它们的原始目的地址:{L["dsts"]}')
print('  日志开头:')
for l in L['first_lines']: print(f'      {l}')
print('  sidecar 转发时自己发出的连接也被 REDIRECT 回了 15001,变成新的一条连接又交给自己,循环往复;所以出站规则里必须让 sidecar 的流量(按 uid 或 gid 识别)绕过自己')

# ============ 三 ============
E_, X = R['exclude_with'], R['exclude_without']
print('== 三:排除端口。容器里有一个 3306 端口的服务(代表数据库),监听在容器自己的地址上。(a)出站规则里先有 “--dport 3306 -j RETURN”,应用访问它;(b)去掉这条规则,应用再访问同一个地址')
print(f'  (a)有排除规则:应用的结果 {E_["direct_3306"]},sidecar 接受的连接数 {E_["sidecar_accepts"]}')
print(f'  (b)去掉排除规则:应用的结果 {X["via_3306"]},sidecar 接受的连接数 {X["sidecar_accepts"]};日志 {X["log"]}')
print('  被排除的端口的连接不经过 sidecar(sidecar 的计数不变);数据库、监控等不想经过代理的流量用这个办法绕开')

# ============ 四 ============
print('== 四:入站。容器里的应用监听 0.0.0.0:8080,PREROUTING 链把进入的 8080 端口的 TCP 连接 REDIRECT 到入站 sidecar 的 15006。另一个容器去访问第一个容器的 8080 和 3306(3306 没有入站规则)')
print(f'  访问 {ip}:8080 的结果:{r8080.stdout.strip() or r8080.stderr.strip()[-200:]!r};访问 {ip}:3306 的结果:{r3306.stdout.strip() or r3306.stderr.strip()[-200:]!r}')
print('  入站 sidecar 的日志:')
for l in R['inbound_log']: print(f'      {l}')
print('  MESH_IN 链的计数器:')
for l in R['inbound_counters']: print(f'      {l}')
print('  8080 的请求先到入站 sidecar,sidecar 用 SO_ORIGINAL_DST 知道它本来要去哪个地址,再转发给应用(这里转发到 127.0.0.1:8080);3306 没有入站规则,直接到应用')
print('ERRORS', dict(ERRORS))
