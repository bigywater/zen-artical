import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z24'); R = {}
MIB = 1048576
print('== 一:默认配置(没有设置 jute.maxbuffer)的服务端:写入大小的临界点')
n = Node('z24a', 7300).start(); z = client('127.0.0.1:7300')
R['default'] = []
for sz in (1048000, 1048500, 1048560, 1048576, 2 * MIB):
    try: z.create(f'/d{sz}', b'x' * sz); r = 'OK'
    except Exception as e: r = type(e).__name__
    if not z.connected: z.stop(); z = client('127.0.0.1:7300')
    R['default'].append((sz, r)); print(f'  create 数据 {sz:>8} 字节 → {r}')
lg = [re.sub(r'^\S+ \[.*?\] \w+\s+\S+ - ', '', l) for l in n.log().splitlines() if 'Len error' in l or 'out of range' in l]; print('  服务端日志:', lg[:2]); R['server_log'] = lg[:2]
z.stop(); n.stop()
print()
print('== 二:服务端设 -Djute.maxbuffer=4194304(4 MiB):写 3 MiB 成功;不同客户端读它')
n = Node('z24b', 7301, jvm=['-Djute.maxbuffer=4194304'], xmx=256).start(); z = client('127.0.0.1:7301')
z.create('/b3', b'y' * 3 * MIB); print('  kazoo 写 3 MiB 到 4 MiB 上限的服务端 → 成功'); print('  kazoo 读回长度:', len(z.get('/b3')[0]), '(kazoo 没有按 jute.maxbuffer 检查响应大小)')
o1 = cli(7301, 'stat /b3')[0].splitlines(); print('  官方 Java 客户端(默认 jute.maxbuffer)执行 stat /b3(不读数据)→', [l for l in o1 if 'dataLength' in l])
o2 = cli(7301, 'get /b3', timeout=60)[0]; print('  官方 Java 客户端(默认 jute.maxbuffer)执行 get /b3 → 输出', len(o2), '字符:', repr(o2[:140]))
o3 = cli(7301, 'get /b3', timeout=60, jvm=['-Djute.maxbuffer=4194304'])[0]; print('  同样命令,客户端也设 -Djute.maxbuffer=4194304 → 输出', len(o3), '字符(数据 3145728 字节)')
R['java_default'] = o2[:200]; R['java_ok'] = len(o3)
print()
print('== 三:服务端上限是「收到的请求」大小,客户端上限是「收到的响应」大小;分别用 5 MiB 写入测服务端 4 MiB 的上限')
try: z.create('/b5', b'z' * 5 * MIB); r = 'OK'
except Exception as e: r = type(e).__name__
print('  写 5 MiB 到 4 MiB 上限的服务端 →', r); R['over'] = r
z.stop(); n.stop(); save('z24', R)
