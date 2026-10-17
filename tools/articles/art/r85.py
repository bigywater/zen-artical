import json
from lib import *
R = J('r85'); pr = R['probe']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("配置里每个 sentinel 只写了一行:sentinel monitor mymaster 127.0.0.1 7600 2(主库地址 + quorum 2)。它们不知道从库,也不知道彼此。", n=fl([['sentinel ×3', '只知道主库'], ['从库 ×2', '未知'], ['其它 sentinel', '未知']], mark=[1, 2]), kv=KV([['配置', 'monitor mymaster 127.0.0.1 7600 2']], ['配置'])),
    step("启动后 185 ms:三个 sentinel 都通过向主库发 INFO 发现了 2 个从库。", n=fl([['sentinel ×3', '已知从库 2 个']], done=[0]), b=bars([['发现 2 个从库', 185, '185 ms']], 2500, done=[0]), kv=KV([['从库发现', '185 ms(INFO 主库)']], ['从库发现'])),
    step(f"约 2.1 s 时开始互相发现:sentinel 之间没有配置彼此地址,靠往主库的 __sentinel__:hello 频道发布自己的信息(主库上 publish 12 秒 {pr['publish']} 次,约每 2 秒每个 sentinel 一次)。{R['ready']:.1f} s 时三个 sentinel 都知道另外两个。", n=fl([['sentinel ×3', '互相发现,通过主库的 hello 频道']], cur=[0]), b=bars([['互相发现完成', R['ready'] * 1000, f"{R['ready']:.1f} s"]], 2500, done=[0]), kv=KV([['互相发现', f"{R['ready']:.1f} s"]], ['互相发现'])),
    step(f"探测频率(3 个 sentinel,12 秒,主库 INFO commandstats):ping {pr['ping']} 次(每个 sentinel 每秒 1 次)、publish {pr['publish']} 次(每 2 秒 1 次)、info {pr['info']} 次(每 10 秒 1 次)、replconf {pr['replconf']} 次(来自 2 个从库的心跳,与 sentinel 无关)。主库上有 {R['nconn']} 个 sentinel 连接(每个 sentinel 一条命令连接、一条订阅连接)。", b=bars([[k, pr[k], str(pr[k])] for k in ('ping', 'publish', 'info')], max(pr['ping'], 40), done=[0, 1, 2]), kv=KV([['ping / publish / info', f"{pr['ping']} / {pr['publish']} / {pr['info']}"]], ['ping / publish / info'])),
    step("发现的拓扑会被写回 sentinel 自己的配置文件:sentinel known-replica × 2、known-sentinel × 2、myid、current-epoch。重启 sentinel 后不需要重新发现。SENTINEL CKQUORUM 返回 OK 3 usable Sentinels。", n=fl([['sentinel.conf', 'known-replica ×2,known-sentinel ×2']], done=[0]), kv=KV([['CKQUORUM', 'OK 3 usable Sentinels']], ['CKQUORUM'])),
]
A = dict(
    n=85, series='redis', tags='Redis,Sentinel,监控,真实验证,动画演示',
    desc=f'启动 3 个只配置了主库地址的 Sentinel:185 ms 通过 INFO 发现 2 个从库,{R["ready"]:.1f} s 内经主库的 __sentinel__:hello 频道互相发现;12 秒里主库上 sentinel 的探测是 ping {pr["ping"]} 次、publish {pr["publish"]} 次、info {pr["info"]} 次;拓扑被写回 sentinel.conf。',
    lead='Sentinel 只需要知道主库的地址。它怎么知道有几个从库、有哪些别的 sentinel?探测多频繁?这篇从零启动三个 sentinel,把发现过程按毫秒量出来,再看它对主库的探测流量和写回配置文件的内容。',
    facts=[('185 ms', '3 个 sentinel 发现 2 个从库(向主库发 INFO)'), (f'{R["ready"]:.1f} s', '3 个 sentinel 互相发现完成(通过主库的 hello 频道)'), (f'{pr["ping"]} / {pr["publish"]} / {pr["info"]}', '12 秒内主库上 ping / publish / info 的调用次数(3 个 sentinel)')],
    body=[
        sec('发现过程', '', term('', blk('r85', 1)), '<p>从库靠向主库发 <code>INFO</code>(里面列出了 slave0、slave1)发现;其它 sentinel 靠主库上的发布订阅频道 <code>__sentinel__:hello</code>:每个 sentinel 定期发布自己的地址、ID 与当前对主库的看法,其它 sentinel 订阅了这个频道就能看到。所以 sentinel 之间不需要互相配置地址。</p>'),
        sec('SENTINEL MASTER / REPLICAS / SENTINELS', '', term('', blk('r85', 2)), '', term('', blk('r85', 3)), '<p><code>quorum 2</code> 是判定客观下线所需的 sentinel 数(第 87 篇)。<code>SENTINEL CKQUORUM</code> 检查当前可用的 sentinel 数够不够达到 quorum 并有权限发起故障转移。(输出里 7622 那一行的 <code>disconnected</code> 是那一刻到该 sentinel 的连接还没建好的瞬时状态。)</p>'),
        sec('探测流量', '', term('', blk('r85', 4)), f'<p>3 个 sentinel 在 12 秒里对主库发了 ping {pr["ping"]} 次(约每个 sentinel 每秒一次)、publish {pr["publish"]} 次(约每 2 秒一次)、info {pr["info"]} 次(约每 10 秒一次)。<code>replconf</code> 是两个从库自己的心跳。流量很小;ping 的间隔也决定了主观下线判断的粒度(第 86 篇)。</p>'),
        sec('写回配置文件', '', term('', blk('r85', 5)), '<p>Sentinel 会改写自己的配置文件,保存 <code>known-replica</code>、<code>known-sentinel</code>、<code>myid</code>、<code>current-epoch</code>。所以 sentinel 的配置文件必须可写;重启后靠这些内容直接恢复拓扑。</p>'),
        sec('分步演示:从「只知道主库」到完整拓扑', '', demo('Sentinel 监控', [('n', 'flow', '发现'), ('b', 'bars', '耗时 / 次数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。1 主 2 从 + 3 个 sentinel,quorum 2,down-after-milliseconds 3000', '没有验证:sentinel 数量更多时的发现时间、跨机器网络、sentinel 密码/ACL 配置、announce-ip 设置、sentinel 重启后的重新发现细节'],
)
