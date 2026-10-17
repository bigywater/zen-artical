import sys, os, time, json, re, http.client; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z68'); R = {}
n = Node('z68', 7300, conf={'admin.enableServer': 'true', 'admin.serverPort': 7392, 'admin.serverAddress': '127.0.0.1'}, jvm=[]).start()
n.stop(); cfg = (n.dir / 'zoo.cfg').read_text(); n.p = None
import subprocess
cmd = [JAVA, '-Xmx128m', f'-Dlogback.configurationFile={n.dir / "logback.xml"}', '-cp', CP, 'org.apache.zookeeper.server.quorum.QuorumPeerMain', str(n.dir / 'zoo.cfg')]
n.p = subprocess.Popen(cmd, cwd=n.dir, stdout=open(n.dir / 'stdout.log', 'a'), stderr=subprocess.STDOUT); n.wait_ready(30)
def get(path):
    c = http.client.HTTPConnection('127.0.0.1', 7392, timeout=5); c.request('GET', path); r = c.getresponse(); b = r.read().decode(); return r.status, r.getheader('Content-Type'), b
z = client('127.0.0.1:7300'); [z.create(f'/n{i}', b'x') for i in range(20)]
print('== 一:AdminServer(zoo.cfg:admin.enableServer=true、admin.serverPort=7392、admin.serverAddress=127.0.0.1;默认端口 8080 我没有用,它是你机器上别的服务的)')
st, ct, b = get('/commands'); cmds = re.findall(r'href="/commands/(\w+)"', b)
print(f'  GET /commands → {st},Content-Type: {ct};返回的是一个 HTML 链接列表,可用命令 {len(cmds)} 个:{cmds}'); R['commands'] = cmds
print()
print('== 二:几个命令的返回(JSON)')
R['samples'] = {}
for c in ('ruok', 'stats', 'monitor', 'configuration', 'connections'):
    st, ct, b = get(f'/commands/{c}')
    try: j = json.loads(b); keys = list(j.keys())[:6]; summary = {k: (v if not isinstance(v, (dict, list)) else f'<{type(v).__name__} {len(v)}>') for k, v in list(j.items())[:6]}
    except Exception: summary = b[:100]
    print(f'  /commands/{c} → {st} {summary}'[:230]); R['samples'][c] = str(summary)[:200]
print()
print('== 三:与四字命令 mntr 的关系:同一个指标两边的值')
st, ct, b = get('/commands/monitor'); j = json.loads(b); m = kv(four(7300, 'mntr'))
print('  monitor 里的 znode_count =', j.get('znode_count'), '| mntr 里的 zk_znode_count =', m.get('zk_znode_count'), '| monitor 里 outstanding_requests =', j.get('outstanding_requests')); R['cmp'] = (j.get('znode_count'), m.get('zk_znode_count'))
print('  monitor 的字段数:', len(j), '| mntr 的指标数:', len(m)); R['counts'] = (len(j), len(m))
print()
print('== 四:不存在的命令与方法')
st, ct, b = get('/commands/nope'); print('  GET /commands/nope →', st, b[:80]); R['nope'] = (st, b[:80])
z.stop(); n.stop(); save('z68', R)
