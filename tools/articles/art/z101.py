import re, pathlib
from lib import *
R = J('z101'); kd = R['kill_default']; k3 = R['kill_s3']; fz = R['freeze']; tm = R['term']; lb = R['lb']
def S(k): return [x for x in out('z101').split('== ')[k].splitlines()[1:] if x.strip()]
SB = pathlib.Path(__file__).resolve().parents[2] / 'dubbo' / 'src' / 'org/apache/dubbo/registry/zookeeper'
ZR = (SB / 'ZookeeperRegistry.java').read_text().splitlines(); CU = (SB / 'util/CuratorFrameworkUtils.java').read_text().splitlines()
def find(L, pat):
    for i, l in enumerate(L):
        if pat in l: return i
a = find(ZR, 'public void doRegister(URL url)'); reg = '\n'.join(ZR[a:a + 4]) + '\n        ...\n    }'
b = find(ZR, 'private String toUrlPath(URL url)'); up = '\n'.join(ZR[b:b + 3])
c = find(CU, 'int sessionTimeoutMs = connectionURL.getParameter(SESSION_KEY'); se = CU[find(CU, 'DEFAULT_SESSION_TIMEOUT_MS = ')].strip() + '\n...\n' + CU[c].strip()
steps = [
    step("启动一个 Dubbo 3.3.6 提供者后,ZooKeeper 里出现的东西比你想的多:/dubbo/Greeter/providers/<URL 编码后的完整服务 URL>(临时节点,接口级注册,Dubbo 2 的老方式)、/services/prov-app/<ip:port>(临时节点,应用级注册,数据是 JSON 实例信息,Dubbo 3 新增)、/dubbo/mapping/Greeter(内容 prov-app,接口 → 应用的映射)、/dubbo/metadata/Greeter/1.0/provider/prov-app(元数据),以及 /dubbo/config 下的迁移规则。接口级节点名解码后就是服务 URL:协议、地址、接口、方法、版本、时间戳。", t=tl(S(1)), done=[0], kv=KV([['接口级', '/dubbo/<接口>/providers/<URL>(临时)'], ['应用级', '/services/<应用>/<ip:port>(临时)']], ['接口级'])),
    step("消费者启动后新增:/dubbo/Greeter/consumers/<消费者 URL>(临时节点,供监控与治理使用)、/dubbo/Greeter/routers 下的路由规则目录。消费者调用提供者成功。", t=tl(S(2)), done=[0], kv=KV([['消费者注册', '/dubbo/Greeter/consumers/…(临时)']], ['消费者注册'])),
    step(f"再起一个提供者 P2:消费者 20 秒内的调用分布是 {', '.join(f'{k} {v}' for k, v in sorted(lb.items()))}(Dubbo 默认随机负载均衡,按权重随机,不是严格轮询);/dubbo/Greeter/providers 下有 2 个子节点。", t=tl(S(3)), done=[0], b=bars([[k, v, str(v)] for k, v in sorted(lb.items())], max(lb.values()) + 10, done=[0, 1]), kv=KV([['负载均衡', '随机(权重)']], ['负载均衡'])),
    step(f"kill -9 一个提供者(默认注册中心 session):P1 的节点在 {kd['removed']:.1f} s 后才从 ZooKeeper 消失 —— Dubbo 默认请求 60 s 的 session,但服务端的 maxSessionTimeout 是 20 × tickTime = 20 s(实测 cons 的 to=20000)。可是消费者在这 {kd['removed']:.0f} s 里 {kd['calls']} 次调用失败 {kd['err']} 次。我的推断(没有进一步验证):进程被 kill 时操作系统关闭了 TCP 连接,Dubbo 消费者据此不再选这个提供者,没有等 ZooKeeper 通知。", t=tl(S(4)), mark=[0], kv=KV([['节点消失', f"{kd['removed']:.1f} s"], ['消费者失败调用', f"{kd['err']} / {kd['calls']}"]], ['节点消失'])),
    step(f"注册中心 URL 加 ?session=3000(提供者与消费者都配):重复 3 次 kill -9,节点消失用时 {', '.join(f'{x} s' for x in k3['removed'])}(第 1 次更慢,原因没有查出来);失败调用均为 {k3['err']}。", t=tl(S(5)), b=bars([[f'第 {i+1} 次', x, f'{x} s'] for i, x in enumerate(k3['removed'])], 8, done=[1, 2], mark=[0]), kv=KV([['session=3000', '节点 2.9–3.0 s 消失(第 1 次 6.8 s)']], ['session=3000'])),
    step(f"冻结提供者进程(SIGSTOP:TCP 连接保持但不响应、也不发心跳):节点在 {fz['removed']:.1f} s 后消失,消费者 {fz['calls']} 次调用里失败 {fz['err']} 次(RpcException,冻结后 {fz['last_err']:.1f} s 内),之后没有再失败。只测了 1 次,没有查出 Dubbo 为什么没有继续向冻结的提供者发请求。", t=tl(S(6) if len(out('z101').split('== ')) > 6 else S(5)), mark=[0], kv=KV([['冻结', f"失败 {fz['err']} 次,节点 {fz['removed']:.1f} s 消失"]], ['冻结'])),
    step(f"SIGTERM:Dubbo 的 shutdown hook 先注销再退出,P2 的节点 {tm['removed']:.2f} s 就消失了,消费者 4 秒内 {tm['calls']} 次调用失败 {tm['err']} 次。正常发布(先注销)比被动等 session 过期好得多。", t=tl(S(len(out('z101').split('== ')) - 1)), done=[0], kv=KV([['SIGTERM 注销', f"{tm['removed']:.2f} s"]], ['SIGTERM 注销'])),
]
A = dict(
    n=101, series='zookeeper', tags='ZooKeeper,Dubbo,注册中心,源码,真实验证,动画演示',
    desc=f'真实运行 Dubbo 3.3.6 的 ZooKeeper 注册中心并读 ZookeeperRegistry 源码:接口级与应用级两套注册节点、mapping 与 metadata;默认 session 60 s 被服务端截到 20 s({kd["removed"]:.0f} s 后节点消失,但 kill -9 时消费者 0 次失败);session=3000 约 3 s;SIGTERM 注销 {tm["removed"]:.2f} s。',
    lead='Dubbo 是 ZooKeeper 最有名的使用者之一。这篇不凭印象写,真起一个 Dubbo 3.3.6 的提供者和消费者,看它在 ZooKeeper 里到底建了哪些节点,再读 ZookeeperRegistry 里注册那几行代码,最后杀进程、冻结进程、正常退出,量节点什么时候消失、调用是否失败。',
    facts=[('2 套', 'Dubbo 3 同时做接口级(/dubbo)与应用级(/services)注册'), (f'{kd["removed"]:.0f} s', '默认 session 下 kill -9 后节点消失(60 s 被服务端截到 20 s),消费者失败 %d 次' % kd['err']), (f'{tm["removed"]:.2f} s', 'SIGTERM 正常退出时节点消失(shutdown hook 先注销)')],
    body=[
        sec('Dubbo 在 ZooKeeper 里建了什么', '', term('', blk('z101', 1)), '<p>注册的代码很短:</p>', src('org/apache/dubbo/registry/zookeeper/ZookeeperRegistry.java(dubbo-registry-zookeeper 3.3.6)', reg + '\n\n' + up), '<p><code>URL.encode</code> 把完整服务 URL 编码成节点名,所以节点名里没有 / 号(见<a href="zookeeper-registry-data-model.html">注册中心数据模型</a>)。<code>create(path, dynamic, true)</code> 里的第二个参数是 dynamic(默认 true),决定是临时节点;我没有测 <code>dynamic=false</code>(应该是持久节点,只读了代码)。</p>'),
        sec('消费者的节点', '', term('', blk('z101', 2)), '<p>消费者自己也注册,仅用于监控与治理,提供者不依赖它。</p>'),
        sec('负载均衡', '', term('', blk('z101', 3))),
        sec('杀进程 vs session', '', src('同一模块 util/CuratorFrameworkUtils.java', se), term('', blk('z101', 4)), '<p>这里 Dubbo 默认请求 60 s,服务端按 <a href="zookeeper-session-expire.html">会话超时的协商规则</a>截断。实测 <code>cons</code> 里这两个会话的 to=20000(session=3000 时是 3000)。</p>'),
        sec('缩短 session', '', term('', blk('z101', 5))),
        sec('冻结与正常退出', '', term('', blk('z101', 6)), term('', blk('z101', 7)), '<p>三种「下线」方式对消费者的影响:正常退出(先注销)几乎无感;进程被杀(TCP 断开)时我观察到没有失败(推断是 Dubbo 自己发现了连接断开);进程冻结或网络断开(TCP 没断)才真正依赖 ZooKeeper 的会话过期。对照<a href="zookeeper-service-discovery.html">服务发现</a>那篇自己写的消费者(没有这层保护,kill -9 时有请求失败)。</p>'),
        sec('分步演示', '', demo('Dubbo 注册中心', [('t', 'term', '输出'), ('b', 'bars', '数量 / 时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Dubbo 3.3.6(dubbo-registry-zookeeper 3.3.6 源码来自 Maven Central 的 sources jar)+ Curator 5.1.0(Dubbo 依赖自带)+ ZooKeeper 3.9.6,tickTime=1000;提供者与消费者是独立 JVM 进程,消费者设 retries=0、timeout=1000 ms;输出里的本机局域网 IP 已替换为 <本机局域网IP>', '没有验证:dynamic=false 的持久注册、Dubbo 的服务端配置中心(/dubbo/config)与动态配置、元数据中心的内容含义、Dubbo 2.7 的行为、消费者为什么在冻结提供者时只失败 1 次(只测了 1 次)、多个注册中心、权重调整'],
)
