import json
from lib import *
R = J('r92'); c = R['c']; fx, sq, sb = c['固定地址'], c['失败后问 sentinel'], c['订阅 +switch-master']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("三个客户端同时每 10 ms 写一次:A 把主库地址写死;B 每次连接失败就问 sentinel(SENTINEL GET-MASTER-ADDR-BY-NAME mymaster)重新取地址;C 订阅 sentinel 的 +switch-master 事件,收到后换地址。", n=fl([['A', '固定地址'], ['B', '失败后问 sentinel'], ['C', '订阅 +switch-master']], cur=[0, 1, 2]), kv=KV([['策略', '固定 / 失败后问 / 订阅']], ['策略'])),
    step(f"kill -9 主库。三者立刻开始收到 ConnectionRefusedError(旧主库进程没了);sentinel 在 {R['tsw']:.1f} s 后完成切换。", n=fl([['旧主库', '已死'], ['三个客户端', '都失败']], mark=[0, 1]), b=bars([['sentinel 切换完成', R['tsw'] * 1000, f"{R['tsw']:.1f} s"]], 6000, mark=[0]), kv=KV([['切换', f"{R['tsw']:.1f} s"]], ['切换'])),
    step(f"A(固定地址):kill 后失败 {fx['fails']} 次并一直失败,始终没有恢复——写死的地址永远指向已经不存在的旧主库。", n=fl([['A', '永远失败']], mark=[0]), kv=KV([['A 失败次数', str(fx['fails'])], ['恢复', '从未']], ['恢复'])),
    step(f"B(失败后问 sentinel):每次连接失败就重新取地址,在切换完成后的第一次询问就拿到新主库,{sq['recovered']*1000:.0f} ms 恢复;失败 {sq['fails']} 次(每 ~50 ms 一次的重试)。", n=fl([['B', '每次失败都重新询问']], done=[0]), b=bars([['B 恢复', sq['recovered'] * 1000, f"{sq['recovered']*1000:.0f} ms"]], 6000, done=[0]), kv=KV([['B 恢复', f"{sq['recovered']*1000:.0f} ms"], ['失败次数', str(sq['fails'])]], ['B 恢复'])),
    step(f"C(订阅 +switch-master):{sb['recovered']*1000:.0f} ms 才恢复,比 B 晚 {(sb['recovered']-sq['recovered'])*1000:.0f} ms;失败 {sb['fails']} 次。我的解释:事件从它订阅的那一个 sentinel 发出,如果这个 sentinel 恰好是故障转移的领导者,它的 +switch-master 要到整个流程结束时才发布(第 89 篇里领导者 5280 ms、其它 sentinel 4254 ms);这个解释没有专门验证。", b=bars([['B 恢复', sq['recovered'] * 1000, f"{sq['recovered']*1000:.0f} ms"], ['C 恢复', sb['recovered'] * 1000, f"{sb['recovered']*1000:.0f} ms"]], 6000, done=[0], mark=[1]), kv=KV([['C 恢复', f"{sb['recovered']*1000:.0f} ms"]], ['C 恢复'])),
]
A = dict(
    n=92, series='redis', tags='Redis,Sentinel,客户端,真实验证,动画演示',
    desc=f'对比三种客户端主库发现策略(kill -9 主库,sentinel {R["tsw"]:.1f} s 完成切换):固定地址 {fx["fails"]} 次失败、永不恢复;失败后重新问 sentinel {sq["recovered"]*1000:.0f} ms 恢复;订阅 +switch-master {sb["recovered"]*1000:.0f} ms 恢复。',
    lead='Sentinel 把主库换了,客户端怎么知道?答案是:客户端自己要去问 sentinel。这篇把三种常见做法放在同一次故障里比较:写死地址、连接失败后重新问 sentinel、订阅 +switch-master 事件。',
    facts=[('永不恢复', '写死主库地址的客户端:切换之后一直连旧地址'), (f'{sq["recovered"]*1000:.0f} ms', '连接失败后重新向 sentinel 询问的客户端恢复时间'), (f'{sb["recovered"]*1000:.0f} ms', '仅订阅 +switch-master 事件的客户端恢复时间')],
    body=[
        sec('三个客户端,一次故障', '', term('', blk('r92', 1)), '<p>三个线程每 10 ms 写一次。故障之后,写死地址的客户端始终失败;「失败后问 sentinel」的客户端在切换完成后的第一次询问就拿到新地址;「订阅事件」的客户端要等它订阅的那个 sentinel 发出 <code>+switch-master</code>。</p>'),
        sec('实现建议(从数据得出的)', '', '<p>1) 不要把主库地址写死,启动时和每次连接失败(或收到 READONLY)时都向 sentinel 询问;2) 事件订阅可以作为「更快通知」的补充,但不要只靠它——事件可能晚到,也可能因为订阅的 sentinel 自己不可用而收不到;3) 询问要在多个 sentinel 之间轮换。第 3 条来自常识,这里没有实验。</p>'),
        sec('分步演示:三种发现策略', '', demo('客户端发现 Sentinel 新主库', [('n', 'flow', '客户端'), ('b', 'bars', '恢复时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。三个客户端各自一个线程;kill -9 只杀主库进程;没有使用真正的客户端库', '没有验证:真实客户端库(redis-py Sentinel、Lettuce、Jedis)的具体策略、READONLY 错误触发重新发现的路径(本实验里旧主库进程已死,没有产生 READONLY)、订阅多个 sentinel 的组合策略'],
)
