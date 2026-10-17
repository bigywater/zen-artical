import sys, os, time, json, re, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z41'); R = {}
e = Ensemble('z41', 3, base=7300).start(); fo = e.followers()[0]
z = client(f'127.0.0.1:{fo.cport}'); z.create('/t', b''); z.create('/t/a', b'hello')
for i in range(20): z.create(f'/t/n{i}', b'x' * 10)
z.set('/t/a', b'world'); z.delete('/t/n0'); t = z.transaction(); t.create('/t/m1', b'1'); t.create('/t/m2', b'2'); t.commit(); z.stop(); time.sleep(1)
def dump(nd):
    logs = sorted(p for p in (nd.dir / 'data' / 'version-2').iterdir() if p.name.startswith('log.'))
    out = []
    for p in logs:
        r = subprocess.run([JAVA, '-Xmx64m', '-cp', CP, 'org.apache.zookeeper.server.persistence.TxnLogToolkit', str(p)], capture_output=True, text=True)
        out += [l for l in (r.stdout + r.stderr).splitlines() if re.search(r'session 0x\w+ cxid 0x\w+ zxid 0x\w+', l)]
    return out
D = {nd.name: dump(nd) for nd in e.nodes}
print('== 一:三个节点各自事务日志里的事务(TxnLogToolkit 读出;只看带 zxid 的行)')
for k, v in D.items(): print(f'  {k}({[n.mode() for n in e.nodes if n.name == k][0]}):共 {len(v)} 条事务,最后一条:', re.sub(r'^\S+ \S+ \S+ \S+ ', '', v[-1])[:90])
a = list(D.values()); same = all(x == a[0] for x in a[1:]); print('  三个节点的事务日志内容逐行完全相同(含时间戳、会话 id、cxid、zxid):', same); R['same'] = same
print()
print('== 二:一条事务的结构:请求有 cxid(客户端自己的序号),事务有 zxid(集群的序号);同一个客户端的 cxid 递增,zxid 全局递增')
sample = [l for l in a[0] if '/t/a' in l or 'multi' in l or 'delete' in l][:4]
for l in sample: print('  ', re.sub(r'^\S+ \S+ \S+ \S+ ', '', l)[:130])
R['sample'] = [re.sub(r'^\S+ \S+ \S+ \S+ ', '', l)[:130] for l in sample]
print()
print('== 三:multi 在日志里是一条 multi 事务(含多个子操作),只占一个 zxid')
mt = [l for l in a[0] if 'multi' in l]; print('  multi 事务:', re.sub(r'^\S+ \S+ \S+ \S+ ', '', mt[0])[:160] if mt else '(没找到)'); R['multi'] = re.sub(r'^\S+ \S+ \S+ \S+ ', '', mt[0])[:160] if mt else None
e.stop(); save('z41', R)
