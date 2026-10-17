import json
from lib import *
R = J('r89'); B = J('r88')
ev = R['events']
def first(ch, i=None):
    return next((r for r in ev if r[0] == ch and (i is None or r[1] == i)), None)
tf = {i: first('+try-failover', i)[2] for i in (0, 2)}
vote = [r for r in ev if r[0] == '+vote-for-leader']
elected = first('+elected-leader')
ba = B['rows']; abort = next(r for r in ba if r[0] == '-failover-abort-not-elected'); retry = [r for r in ba if r[0] == '+try-failover'][1]
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step(f"o_down 之后,想执行故障转移的 sentinel 要先当「领导者」。quorum 2 的集群里,sentinel0({tf[0]:.0f} ms)和 sentinel2({tf[2]:.0f} ms)几乎同时 +try-failover,都进入 epoch 1——两个候选人。", n=fl([['sentinel0', '+try-failover epoch 1'], ['sentinel2', '+try-failover epoch 1'], ['sentinel1', '未参选']], cur=[0, 1]), kv=KV([['候选人', 'sentinel0、sentinel2']], ['候选人'])),
    step("每个 sentinel 在一个 epoch 里只能投一票(+vote-for-leader)。sentinel0 给自己(4570effe…),sentinel2 给自己(59ffdbdd…),sentinel1 收到 sentinel0 先到的请求,把票投给 sentinel0。结果 sentinel0 得 2 票,sentinel2 得 1 票。", n=fl([['sentinel0', '得 2 票(自己 + sentinel1)'], ['sentinel2', '得 1 票(自己)'], ['sentinel1', '投给 sentinel0']], done=[0], mark=[1]), kv=KV([['票数', 'sentinel0:2,sentinel2:1']], ['票数'])),
    step(f"sentinel0 拿到多数(3 个 sentinel 里的 2 个)→ +elected-leader({elected[2]:.0f} ms),随后由它执行故障转移。sentinel2 落选,只跟随。", n=fl([['sentinel0', '+elected-leader'], ['sentinel2', '落选,等待']], done=[0]), b=bars([['+elected-leader', elected[2], f'{elected[2]:.0f} ms']], 4500, done=[0]), kv=KV([['领导者', 'sentinel0']], ['领导者'])),
    step(f"对照:quorum 设成 1,但另外两个 sentinel 被冻结。sentinel0 一个人就 +odown(#quorum 1/1)并 +try-failover,给自己投一票(epoch 1)——但 3 个 sentinel 里它只有 1 票,没有多数。", n=fl([['sentinel0', 'o_down,1 票'], ['sentinel1、2', '冻结']], mark=[0]), kv=KV([['票数', '1 / 3(需要 2)']], ['票数'])),
    step(f"故障转移超时:failover-timeout 设成 8000 ms,{abort[1]/1000:.1f} s 时 -failover-abort-not-elected(选举失败,放弃)。再过一段冷却,{retry[1]/1000:.1f} s 时用 epoch 2 重新 +try-failover,仍然只有自己一票。25 秒里主库地址始终是旧的 7780。", n=fl([['sentinel0', '-failover-abort-not-elected'], ['再试 epoch 2', '仍然只有 1 票']], mark=[0, 1]), b=bars([['放弃', abort[1], f'{abort[1]/1000:.1f} s'], ['再次尝试(epoch 2)', retry[1], f'{retry[1]/1000:.1f} s']], 21000, mark=[0, 1]), kv=KV([['结果', '25 s 无新主库']], ['结果'])),
]
A = dict(
    n=88, series='redis', tags='Redis,Sentinel,选举,真实验证,动画演示',
    desc=f'从 Sentinel 事件流看故障转移投票:quorum 2、3 个 sentinel 时两个 sentinel 同时 +try-failover(epoch 1),各投自己一票,第三个 sentinel 投给先到的 sentinel0,sentinel0 以 2/3 当选(+elected-leader);quorum 1 但只剩 1 个 sentinel 可用时,o_down 立刻成立却拿不到多数票,{abort[1]/1000:.1f} s 后 -failover-abort-not-elected,25 秒都没有新主库。',
    lead='上一篇里 quorum 决定「客观下线」。但真正执行故障转移,要在 sentinel 里选出一个领导者,这需要「多数 sentinel」投票——不是 quorum。两件事经常被混为一谈。这篇订阅 sentinel 的事件流,把两个 sentinel 抢着当领导者的过程和「凑不够多数」的失败都抓下来。',
    facts=[('2 / 3', 'sentinel0 当选所需与得到的票数(每个 sentinel 每个 epoch 只投一票)'), ('quorum 1 也不行', 'o_down 成立,但只有 1 个 sentinel 可用时拿不到多数,故障转移放弃'), (f'{abort[1]/1000:.1f} s', 'failover-timeout 8000 ms 下,选举失败后 -failover-abort-not-elected 的时间')],
    body=[
        sec('两个候选人', '订阅 sentinel 的 PSUBSCRIBE * 事件流(时间相对 kill -9 主库)', term('', '\n'.join(f'+{r[2]:6.0f} ms  s{r[1]}  {r[0]:<20} {r[3][:70]}' for r in ev if r[0] in ('+odown', '+new-epoch', '+try-failover', '+vote-for-leader', '+elected-leader'))),
            '<p>quorum 2 时,sentinel0 和 sentinel2 几乎同时(相差 2 ms)达成 o_down 并 <code>+try-failover</code>,都在 epoch 1。<code>+vote-for-leader</code> 的参数是被投票 sentinel 的 ID 和 epoch:sentinel0(4570effe…)得 2 票(自己和 sentinel1),sentinel2(59ffdbdd…)只有自己 1 票。得到多数(3 个里的 2 个)的 sentinel0 <code>+elected-leader</code>,然后由它选新主库、发 <code>SLAVEOF NO ONE</code>(第 89 篇)。</p>'),
        sec('凑不够多数', 'quorum 1,另两个 sentinel 冻结', term('', blk('r88', 1)),
            '<p>即使 quorum 设成 1,让单个 sentinel 就能宣布客观下线,<b>执行故障转移仍需要多数 sentinel 授权</b>:只有 1 个可用时,它给自己投了一票,但 3 个里需要 2 票。超时后放弃(<code>-failover-abort-not-elected</code>),冷却一段时间后用更大的 epoch 再试,仍然失败。日志里的 <code>Next failover delay: I will not start a failover before …</code> 就是这个冷却时间。</p>'),
        sec('实践含义', '', '<p>部署 sentinel 至少要 3 个且放在不同的故障域里:主库挂掉的同时如果有 sentinel 一起不可用,剩下的 sentinel 数必须仍然超过一半,否则即使检测到了故障也切不了。</p>'),
        sec('分步演示:选举', '', demo('Sentinel 故障转移投票', [('n', 'flow', 'sentinel 状态'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。3 个 sentinel,quorum 2(第一组)与 quorum 1 + 两个 sentinel 冻结(第二组,failover-timeout 8000);事件来自 PSUBSCRIBE *', '没有验证:sentinel 数量为 5 时的多数(3)、选举 epoch 冲突时的多轮结果、跨机器时钟差的影响'],
)
