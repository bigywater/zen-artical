import json, statistics
from lib import *
R = J('r86'); da = R['da']; sg = R['single']; sl = R['sleep']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
m = {k: statistics.mean(v) * 1000 for k, v in da.items()}
sd1 = sg['s_down,master'] * 1000
steps = [
    step(f"主观下线(sdown)是单个 sentinel 自己的判断:它对主库的 PING 在 down-after-milliseconds 内没有有效回复,就给主库打上 s_down。冻结主库后,sentinel0 眼中的 flags 从 master 变成 s_down,master,用了 {sd1:.0f} ms(down-after = 3000 ms)。", n=fl([['sentinel0', 's_down(我觉得它挂了)']], mark=[0]), b=bars([['s_down 出现', sd1, f'{sd1:.0f} ms']], 4500, mark=[0]), kv=KV([['sdown', f'{sd1:.0f} ms']], ['sdown'])),
    step("但一个 sentinel 觉得挂了不够:我把主库和另外两个 sentinel 都冻结,只有 sentinel0 活着。9 秒后主库地址仍是 7660,没有故障转移——sdown 只是「我认为」,需要 quorum 个 sentinel 同意(客观下线,第 87 篇)才会行动。", n=fl([['sentinel0', 's_down,但孤立'], ['sentinel1、2', '冻结']], mark=[0]), kv=KV([['9 秒后主库', '仍是 7660,无故障转移']], ['9 秒后主库'])),
    step(f"判定时间由 down-after-milliseconds 决定:设 1000 / 3000 / 6000 ms,s_down 平均出现在 {m['1000']:.0f} / {m['3000']:.0f} / {m['6000']:.0f} ms(每种 2 次:{da['1000']}、{da['3000']}、{da['6000']} 秒)——都比设置值多约 0.9–1 s。", b=bars([[f'down-after {k} ms', m[k], f'{m[k]:.0f} ms'] for k in ('1000', '3000', '6000')], m['6000'], done=[0, 1, 2]), kv=KV([['实测 / 设置', f"{m['1000']:.0f}/1000、{m['3000']:.0f}/3000、{m['6000']:.0f}/6000 ms"]], ['实测 / 设置'])),
    step(f"「不响应」就算数,不管进程是否活着:DEBUG SLEEP 6 让主库进程活着但 6 秒不回应,sentinel0 在 {sl['s_down,master']*1000:.0f} ms 标 s_down,{sl['s_down,o_down,master']*1000:.0f} ms 达成客观下线,随后故障转移把主库换成了 7661。原主库其实没有死。", n=fl([['主库(阻塞 6 s)', '被判 s_down → o_down'], ['故障转移', '主库换成 7661']], mark=[0], done=[1]), b=bars([['s_down', sl['s_down,master'] * 1000, f"{sl['s_down,master']*1000:.0f} ms"], ['o_down', sl['s_down,o_down,master'] * 1000, f"{sl['s_down,o_down,master']*1000:.0f} ms"]], 6000, mark=[0, 1]), kv=KV([['结果', '存活但阻塞的主库也会被换掉']], ['结果'])),
]
A = dict(
    n=86, series='redis', tags='Redis,Sentinel,主观下线,真实验证,动画演示',
    desc=f'实测 Sentinel 主观下线:冻结主库后 sentinel 在 down-after-milliseconds 之后(3000 ms 时约 {m["3000"]:.0f} ms)标 s_down;单个 sentinel 的 s_down 不会触发故障转移;down-after 设 1000/3000/6000 ms 时实测约 {m["1000"]:.0f}/{m["3000"]:.0f}/{m["6000"]:.0f} ms;主库进程活着但阻塞 6 秒同样被判下线并被替换。',
    lead='Sentinel 判断主库挂了分两步:先是每个 sentinel 自己的「主观下线」(sdown),再是多个 sentinel 达成一致的「客观下线」。这一篇量第一步:多久判定、一个 sentinel 说了算不算、什么样的「挂」会被判定。',
    facts=[(f'{m["3000"]:.0f} ms', 'down-after-milliseconds = 3000 时 s_down 实际出现的时间(平均)'), ('不触发', '单个 sentinel 的 s_down 不会引发故障转移'), (f'{sl["s_down,master"]*1000:.0f} → {sl["s_down,o_down,master"]*1000:.0f} ms', '主库阻塞 6 秒(进程活着)时 s_down → o_down')],
    body=[
        sec('一个 sentinel 说了不算', '', term('', blk('r86', 1)), '<p>冻结主库,同时冻结另外两个 sentinel,只让 sentinel0 活着:它在约 3.9 s 后标出 <code>s_down</code>,但 9 秒后主库地址仍是原来的——<b>主观下线只是本地判断</b>。</p>'),
        sec('判定时间 = down-after + 探测间隔', '每种设置 2 次', term('', blk('r86', 2)), '<p>实际出现的时间比设置值多约 0.9–1 秒。我没有单独验证原因;和第 85 篇里观察到的「每秒一次 PING」吻合(要等到下一次探测才发现超时),但这是推测。</p>'),
        sec('进程活着也会被判', '', term('', blk('r86', 3)), '<p>sentinel 只看「有没有回复」。<code>DEBUG SLEEP 6</code> 让主库进程 6 秒不响应,sentinel 同样标 <code>s_down</code>,随后客观下线、故障转移;原主库没有死,但被换掉了。所以 <code>down-after-milliseconds</code> 太小会把 GC 停顿、大 key 阻塞一类的短暂卡顿误判成故障。</p>'),
        sec('分步演示:主观下线', '', demo('Sentinel 主观下线', [('n', 'flow', '状态'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。1 主 2 从 + 3 个 sentinel;主库用 SIGSTOP 冻结或 DEBUG SLEEP 阻塞', '没有验证:PING 回复错误(-LOADING、-BUSY 等)的判定、网络延迟高时的表现、down-after 的最优取值、多个 sentinel 各自 down-after 不同时的行为'],
)
