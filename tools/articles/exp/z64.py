import sys, os, time, json, re, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z64'); R = {}
def probe(port, *args):
    r = subprocess.run([JAVA, '-cp', str(HERE / 'jmxc'), 'JmxProbe', str(port), *args], capture_output=True, text=True, timeout=60); return [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
JMX = lambda port: [f'-Dcom.sun.management.jmxremote.port={port}', '-Dcom.sun.management.jmxremote.authenticate=false', '-Dcom.sun.management.jmxremote.ssl=false', '-Djava.rmi.server.hostname=127.0.0.1', '-Dcom.sun.management.jmxremote.local.only=true', '-Dzookeeper.jmx.log4j.disable=true']
print('== 一:单机节点开启 JMX(仅本机、无认证——只用于实验)后,ZooKeeper 注册的 MBean')
n = Node('z64a', 7300, jvm=JMX(7391)).start(); z = client('127.0.0.1:7300'); rs = [z.create_async(f'/n{i}', b'x') for i in range(500)]; [r.get() for r in rs]
names = probe(7391); [print('  ', x) for x in names]; R['standalone_names'] = names
sv = [x for x in names if 'StandaloneServer' in x][0]
print()
print('== 二:StandaloneServer MBean 的属性(读到的实际值)')
at = probe(7391, sv); keep = [l for l in at if l.startswith('ATTR') and any(k in l for k in ('Version', 'NumAliveConnections', 'AvgRequestLatency', 'MaxRequestLatency', 'PacketsReceived', 'OutstandingRequests', 'TickTime', 'ClientPort', 'MaxClientCnxnsPerHost', 'MinSessionTimeout', 'MaxSessionTimeout'))]
for l in keep: print('  ', l[:130])
print('  可调用的操作:', [l[3:] for l in at if l.startswith('OP')]); R['attrs'] = keep; R['ops'] = [l[3:] for l in at if l.startswith('OP')]
z.stop(); n.stop()
print()
print('== 三:集群节点的 MBean:leader 与 follower 的名字不同(只看名字里的角色)')
e = Ensemble('z64b', 3, base=7310); [setattr(nd, 'jvm', JMX(7392 + i)) for i, nd in enumerate(e.nodes)]; e.start(); ld = e.leader(); fo = e.followers()[0]
for who, nd in (('leader', ld), ('follower', fo)):
    nm = probe(7392 + e.nodes.index(nd)); print(f'  {who}({nd.name}):'); [print('    ', x.replace('org.apache.ZooKeeperService:', '')) for x in nm]; R[who] = [x.replace('org.apache.ZooKeeperService:', '') for x in nm]
e.stop(); save('z64', R)
