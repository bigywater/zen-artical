import json, statistics
from lib import *
R = J('r51'); idle = R['idle']; pool = R['pool']; tp = R['tp']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
P = {p['N']: p for p in pool}
imin, imed, imax = min(idle), statistics.median(idle), max(idle)
steps = [
    step("默认 notify-keyspace-events 是空字符串:通知关闭。订阅 __key*__:* 之后 SET k v,什么都收不到。", e=cells(['SET k v', '(没有任何通知)'], mark=[1]), kv=KV([['notify-keyspace-events', '""(关闭)']], ['notify-keyspace-events'])),
    step("CONFIG SET notify-keyspace-events KEA 之后,一条命令产生两条通知:__keyspace@0__:<key> 频道里推事件名,__keyevent@0__:<事件> 频道里推 key 名。RENAME 一次产生 rename_from 和 rename_to 两个事件。", e=cells(['SET k → set', 'LPUSH l → lpush', 'EXPIRE k → expire', 'RENAME k k2 → rename_from + rename_to', 'DEL k2 → del'], done=[0, 1, 2, 3, 4]), kv=KV([['每条命令', '2 条通知(keyspace + keyevent)'], ['RENAME', '2 个事件']], ['每条命令'])),
    step(f"expired 事件不是准点的。空闲实例上设 30 个 PX 300 的 key,事件比 300 ms 晚 {imin:.1f}–{imax:.0f} ms,中位 {imed:.1f} ms。", b=bars([['最小', imin, f'{imin:.1f} ms'], ['中位', imed, f'{imed:.1f} ms'], ['最大', imax, f'{imax:.0f} ms']], imax, mark=[2]), kv=KV([['空闲实例的延迟', f'{imin:.1f} / {imed:.1f} / {imax:.0f} ms']], ['空闲实例的延迟'])),
    step(f"但池子里有大量「长 TTL」的 key 时,少量短 TTL key 的事件会严重变慢:0 个长 TTL key 时 {P[0]['got']}/30 都在 {P[0]['med']:.0f} ms;1000 个时 20 秒内只收到 {P[1000]['got']}/30(中位 {P[1000]['med']/1000:.1f} s);10000 个时 {P[10000]['got']}/30;10 万个时 {P[100000]['got']}/30;30 万个时 {P[300000]['got']}/30。", b=bars([[f'{N} 个长 TTL key', P[N]['got'], f'{P[N]["got"]}/30 在 20 s 内'] for N in (0, 1000, 10000, 100000, 300000)], 30, mark=[1, 2, 3, 4], done=[0]), kv=KV([['20 秒内收到', ' / '.join(f'{P[N]["got"]}' for N in (0, 1000, 10000, 100000, 300000)) + '(共 30)']], ['20 秒内收到'])),
    step(f"key 已过期但还没被后台清到时,谁访问它,expired 事件就在那一刻发出:GET 一个过期的 key 返回 nil,事件在 GET 之后 {R['lazy']:.2f} ms 内到达。不访问的 key(池子 30 万个,hz=1)8 秒内没有收到事件。", e=cells(['过期后 GET → 事件立刻到', '不访问 → 8 秒内没有事件'], done=[0], mark=[1]), kv=KV([['GET 之后事件到达', f'{R["lazy"]:.2f} ms'], ['不访问', '8 秒内无事件']], ['不访问'])),
    step("订阅者不在时事件就没了(发后即忘):key 在订阅者离线期间过期,重新订阅后什么都收不到。", e=cells(['订阅者离线', 'key 过期', '重新订阅 → 什么都没有'], mark=[2]), kv=KV([['重新订阅后', '什么都没有']], ['重新订阅后'])),
    step(f"开销:管道 SET 20 万条,关闭通知 {tp[0]/1000:.0f}k/s;开启 KEA 但没有订阅者 {tp[1]/1000:.0f}k/s;开启且有 1 个订阅 set 事件的订阅者 {tp[2]/1000:.0f}k/s。", b=bars([['关闭', tp[0]/1000, f'{tp[0]/1000:.0f}k/s'], ['KEA 无订阅者', tp[1]/1000, f'{tp[1]/1000:.0f}k/s'], ['KEA + 1 订阅者', tp[2]/1000, f'{tp[2]/1000:.0f}k/s']], tp[0]/1000, mark=[1, 2]), kv=KV([['开启通知的代价', f'{(1-tp[1]/tp[0])*100:.0f}%(无订阅者)/ {(1-tp[2]/tp[0])*100:.0f}%(有订阅者)']], ['开启通知的代价'])),
]
A = dict(
    n=51, series='redis', tags='Redis,Keyspace Notification,过期,真实验证,动画演示',
    desc=f'实测 Keyspace Notification:默认关闭;KEA 下一条命令产生 keyspace 与 keyevent 两条通知;expired 事件在空闲实例上比 TTL 晚 {imed:.1f} ms(中位),但池子里有 1000 个以上长 TTL key 时,30 个短 TTL key 的事件 20 秒内只到 {P[1000]["got"]}/30 以下(30 万个时 {P[300000]["got"]}/30);发后即忘;开启 KEA 使管道 SET 吞吐下降约 {(1-tp[1]/tp[0])*100:.0f}%。',
    lead='Keyspace Notification 让你订阅「某个 key 被改了」「某个 key 过期了」这类事件。最常见的用法是用 expired 事件做「到期触发」,比如订单超时关闭。但 expired 事件到底有多准时?这篇量了一个多数人没量过的场景:数据库里有大量 TTL 很长的 key 时,短 TTL key 的过期事件要等多久。',
    facts=[('默认关闭', 'notify-keyspace-events 默认是空字符串'), (f'{imed:.1f} ms', f'空闲实例上 expired 事件比 TTL 晚的中位数(最大 {imax:.0f} ms)'), (f'{P[300000]["got"]}/30', '池子里有 30 万个长 TTL key 时,30 个 PX 300 的 key 在 20 秒内收到 expired 事件的个数(1000 个时是 %d/30)' % P[1000]['got'])],
    body=[
        sec('默认关闭,KEA 打开之后', '', term('', blk('r51', 1)), '', term('', blk('r51', 2)), '<p><code>K</code> 是 keyspace 频道(<code>__keyspace@0__:&lt;key&gt;</code>,内容是事件名),<code>E</code> 是 keyevent 频道(<code>__keyevent@0__:&lt;事件&gt;</code>,内容是 key 名),<code>A</code> 表示所有事件类型。所以一条命令会推两条消息。RENAME 会产生 <code>rename_from</code> 和 <code>rename_to</code> 两个事件。</p>'),
        sec('expired 事件:空闲实例上的延迟', '', term('', blk('r51', 3)), f'<p>每次 <code>SET key v PX 300</code>,然后等 expired 事件,量它比 300 ms 晚多少。30 次:最小 {imin:.1f} ms、中位 {imed:.1f} ms、最大 {imax:.0f} ms。空闲时事件几乎准点,但最大值说明它不是一个有保证的上限。</p>'),
        sec('大量长 TTL key 时:事件可能很久不来', '每组同时设 30 个 PX 300 的 key,最多等 20 秒', term('', blk('r51', 4)),
            f'<p>先往库里灌不同数量、TTL 为 1 小时的 key,再同时设 30 个 300 ms 的 key,看 20 秒内能收到几个 expired 事件。库里没有长 TTL key 时 30/30 都在 {P[0]["med"]:.0f} ms 到;<b>1000 个长 TTL key 时只有 {P[1000]["got"]}/30,中位延迟约 {P[1000]["med"]/1000:.1f} 秒;10 万个以上时,20 秒内一个到不了或只到寥寥几个。</b>我把这个实验跑了三次:三次里 1000 个长 TTL key 都是 22–24/30,10000 个是 12–15/30,10 万个是 0–3/30,30 万个是 0–1/30——具体个数每次不同,但趋势一致。上面打印的是最后一次。</p><p>这意味着:<b>expired 事件不能当作准点的定时器</b>。库里有大量长 TTL key 时,一个刚过期的 key 可能很久之后才被后台清理发现。为什么?我推测是后台过期清理采用随机抽样(每次只看一小批带 TTL 的 key),池子越大越难抽中那几个过期的——这是我对这个现象的解释,没有读源码验证。</p>'),
        sec('惰性删除:访问会立刻触发', '', term('', blk('r51', 5)), f'<p>把 <code>hz</code> 调到 1 让后台清理变慢。一个已过期的 key,被 <code>GET</code> 访问时,返回 nil、同时 expired 事件在 {R["lazy"]:.2f} ms 内到达;而另一个同样过期、但没人访问的 key,在 30 万 key 的库里 8 秒内一直没有事件。所以「读一下」比「等通知」更可靠——但你得知道要读哪个 key。</p>'),
        sec('发后即忘,以及开销', '', term('', blk('r51', 6)), '<p>Keyspace Notification 基于 Pub/Sub(见第 49 篇),订阅者不在时事件就丢了,没有补发。</p>', term('', blk('r51', 7)), f'<p>开启 KEA 之后管道写入吞吐从 {tp[0]/1000:.0f}k/s 降到 {tp[1]/1000:.0f}k/s(无订阅者),有一个订阅者时 {tp[2]/1000:.0f}k/s。<b>只开需要的事件类型</b>(比如只开 <code>Ex</code>)可以少产生通知——这一点我没有另外测量。</p>'),
        sec('分步演示:通知与过期', '', demo('Keyspace Notification', [('e', 'cells', '事件'), ('b', 'bars', '数据'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。第 4 节的 expired 事件实验用一个订阅者连接接收 __keyevent@0__:expired;每组 30 个 key;20 秒的观察窗口是固定值', '没有验证:hz 与 active-expire-effort 调大后事件延迟能否改善、只开 Ex 时的开销、集群下的事件、Redis 8 的哈希字段过期事件(hexpired)'],
)
