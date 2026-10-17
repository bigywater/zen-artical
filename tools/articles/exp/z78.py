import sys, os, time, json, re, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
from cryptography.fernet import Fernet
tee('z78'); R = {}
SECRET = b'SUPER-SECRET-TOKEN-8842'
d = pki()
def scan(nd, label):
    v2 = nd.dir / 'data' / 'version-2'; hits = {}
    for p in sorted(v2.iterdir()):
        if p.name.startswith(('log.', 'snapshot.')): hits[p.name] = SECRET in p.read_bytes()
    return hits
print('== 一:静态数据(at rest):事务日志与快照里是明文——把一个「机密」写进 znode,直接在数据目录里搜它')
n = Node('z78a', 7300, conf={'snapCount': 100}).start(); z = client('127.0.0.1:7300'); z.create('/token', SECRET)
[z.create(f'/n{i}', b'x') for i in range(150)]; z.stop(); n.stop()
h = scan(n, ''); print('  数据目录里各文件是否含有明文机密:', h); R['at_rest'] = h
print('  (digest ACL 只控制「通过 ZooKeeper 访问」,能读数据目录文件的人不需要任何口令)')
print()
print('== 二:传输中(客户端 ↔ 服务端):明文端口 vs TLS 端口——让客户端经过一个会记录字节流的代理,看机密是否出现在抓到的字节里')
n = Node('z78b', 7300, conf=tls_conf(d, 7301)).start()
pp = Proxy(7390, 7300).start(); pt = Proxy(7391, 7301).start()
z = client('127.0.0.1:7390'); z.create('/tok2', SECRET); z.get('/tok2'); z.stop(); time.sleep(0.3)
print(f'  明文端口(代理 7390 → 7300)抓到 {len(pp.cap)} 字节,含机密:', SECRET in bytes(pp.cap)); R['plain_wire'] = SECRET in bytes(pp.cap)
from kazoo.client import KazooClient
import logging; logging.getLogger('kazoo').setLevel(logging.CRITICAL)
zt = KazooClient(hosts='127.0.0.1:7391', use_ssl=True, ca=str(d / 'ca.crt'), verify_certs=False, timeout=10); zt.start(timeout=10); zt.create('/tok3', SECRET); zt.get('/tok3'); zt.stop(); time.sleep(0.3)
print(f'  TLS 端口(代理 7391 → 7301)抓到 {len(pt.cap)} 字节,含机密:', SECRET in bytes(pt.cap)); R['tls_wire'] = SECRET in bytes(pt.cap)
pp.stop(); pt.stop(); n.stop()
print()
print('== 三:节点之间的复制流量(quorum 端口):默认明文;sslQuorum=true 之后加密')
def quorum(ssl_on, base):
    conf = {'tickTime': 1000}
    if ssl_on: conf.update({'sslQuorum': 'true', 'ssl.quorum.keyStore.location': str(d / 'server.p12'), 'ssl.quorum.keyStore.password': 'changeit', 'ssl.quorum.keyStore.type': 'PKCS12', 'ssl.quorum.trustStore.location': str(d / 'truststore.p12'), 'ssl.quorum.trustStore.password': 'changeit', 'ssl.quorum.trustStore.type': 'PKCS12'})
    e = NetEnsemble(f'z78q{int(ssl_on)}', 3, base=base, conf=conf).start(); z = client(e.hosts()); z.create('/tok', SECRET); [z.create(f'/n{i}', SECRET) for i in range(20)]; time.sleep(1)
    cap = b''.join(bytes(p.cap) for pq in e.proxies.values() for p in pq); ok = SECRET in cap; size = len(cap); modes = {nd.name: nd.mode() for nd in e.nodes}; z.stop(); e.stop(); return ok, size, modes
a = quorum(False, 7400); print(f'  明文 quorum:节点间抓到 {a[1]} 字节,含机密:', a[0], '| 集群角色', a[2]); R['quorum_plain'] = dict(visible=a[0], size=a[1])
try:
    b = quorum(True, 7500); print(f'  sslQuorum=true:节点间抓到 {b[1]} 字节,含机密:', b[0], '| 集群角色', b[2]); R['quorum_tls'] = dict(visible=b[0], size=b[1], modes=b[2])
except Exception as e: print('  sslQuorum=true 的集群没有起来:', type(e).__name__, str(e)[:100]); R['quorum_tls'] = dict(error=str(e)[:100])
print()
print('== 四:应用层加密:客户端先加密再写入,数据目录里就没有明文了(代价:服务端看不懂数据,密钥要自己管理)')
f = Fernet(Fernet.generate_key()); n = Node('z78d', 7300, conf={'snapCount': 100}).start(); z = client('127.0.0.1:7300'); z.create('/enc', f.encrypt(SECRET)); [z.create(f'/m{i}', b'x') for i in range(150)]
print('  从 ZooKeeper 读回、客户端解密 →', f.decrypt(z.get('/enc')[0])); z.stop(); n.stop(); h2 = scan(n, ''); print('  数据目录里各文件是否含有明文机密:', h2); R['app_enc'] = h2
save('z78', R)
