from lib import *
R = J('z33')
def S(k): return [l for l in out('z33').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("五节点检查表:对每个节点各发 srvr 和 mntr,汇总角色、zxid、连接数、outstanding 请求数、synced_followers、平均延迟。健康时:1 个 leader(synced_followers = 4)、4 个 follower,五个节点的 zxid 相同(0x100000065)。一张表就能看出集群是否「一个 leader + 四个同步的 follower + zxid 一致」。", t=tl(S(1)[:7]), done=[0, 1, 2, 3, 4, 5, 6], kv=KV([['健康的标志', '1 个 leader,synced_followers = N−1,zxid 一致']], ['健康的标志'])),
    step("杀掉 1 个 follower:表里该节点显示「已停止」,leader 的 synced_followers 从 4 变成 3,其它节点正常——这是最先应该监控的指标。", t=tl(S(2)[1:8]), mark=[0], kv=KV([['synced_followers', 'leader 少一个就是有 follower 掉线']], ['synced_followers'])),
    step("再杀掉 leader:刚被杀的瞬间,存活的 3 个节点全部显示「不服务」(正在选举),表里没有 leader;选举完成后:新 leader 的 zxid 变成 0x200000000(epoch 从 1 到 2,counter 从 0 开始,见第 37 篇),synced_followers = 2(剩下 3 个节点里的 2 个 follower)。", t=tl(S(3)), mark=[1, 2], done=[10, 11], kv=KV([['选举期间', '全部「不服务」'], ['新 leader', 'zxid epoch +1']], ['选举期间'])),
    step("健康检查不能只用 ruok:只起 3 个节点中的 1 个,ruok 仍回「imok」,但 srvr 首行是「This ZooKeeper instance is not currently serving requests」。要判断「能否服务」,看 srvr 的 Mode 或 mntr 的 zk_server_state,不要只看 ruok。", t=tl(S(4)), mark=[0], kv=KV([['ruok', '只表示进程活着'], ['srvr / mntr', '才表示能否服务']], ['srvr / mntr'])),
]
A = dict(
    n=33, series='zookeeper', tags='ZooKeeper,监控,Quorum,健康检查,真实验证,动画演示',
    desc='五节点 Quorum 检查表:对每个节点发 srvr / mntr 汇总角色、zxid、连接数、synced_followers;杀 follower 时 leader 的 synced_followers 4 → 3;杀 leader 后选举期间所有存活节点「不服务」,新 leader 的 zxid epoch +1;ruok 不能代表能否服务。',
    lead='一个 5 节点的 ZooKeeper 集群「看起来是否健康」,最少要看哪几项?这篇写一个只用四字命令的检查表,在健康、一个 follower 掉线、leader 被杀三种状态下各打印一次。',
    facts=[('synced_followers', 'leader 上这一项少于 N−1,说明有 follower 掉线'), ('zxid 一致', '健康时各节点 zxid 相同'), ('ruok 不够', '只起 1/3 时 ruok 回 imok,srvr 却是不服务')],
    body=[
        sec('健康时', '', term('', blk('z33', 1))),
        sec('一个 follower 掉线', '', term('', blk('z33', 2))),
        sec('leader 被杀', '', term('', blk('z33', 3))),
        sec('为什么不能只看 ruok', '', term('', blk('z33', 4))),
        sec('分步演示', '', demo('五节点检查表', [('t', 'term', '检查表'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。5 节点伪集群;检查表用 srvr 与 mntr(白名单设为 *);「已停止」是脚本里进程已退出,不是四字命令的返回', '没有验证:Prometheus 指标(第 63 篇)、JMX(第 64 篇)、更多运维指标的阈值、四字命令的访问控制(第 67 篇)'],
)
