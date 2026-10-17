import json
from lib import *
R = J('r124'); t = R['t']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def fl(nodes, cur=(), done=(), mark=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done), 'mark': list(mark)}
def tl(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
ok = lambda k: '允许' if t[k] == 'OK' else '拒绝'
steps = [
    step(f"默认值 acl-pubsub-default = {R['default'][1]}:新用户没有任何频道权限。u1 有 +@all ~*,但 PUBLISH news:1 和 SUBSCRIBE news:1 都报 NOPERM No permissions to access a channel。", n=fl([['u1 (+@all ~*)', '无频道权限'], ['PUBLISH news:1', 'NOPERM'], ['SUBSCRIBE news:1', 'NOPERM']], mark=[1, 2]), kv=KV([['acl-pubsub-default', R['default'][1]]], ['acl-pubsub-default'])),
    step("给 u2 &news:*。判定:" + ';'.join(f"{k} {ok(k)}" for k in ('PUBLISH news:1 hi', 'PUBLISH other hi', 'SUBSCRIBE news:1', 'SUBSCRIBE other')) + "。", t=tl([f"{k:<26} {ok(k)}" for k in t], cur=[0, 2], mark=[1, 4]), kv=KV([['规则', '&news:*']], ['规则'])),
    step(f"模式订阅要「字面相同」:PSUBSCRIBE news:* → {ok('PSUBSCRIBE news:*')};PSUBSCRIBE news:a*(范围比 news:* 小)→ {ok('PSUBSCRIBE news:a*')};PSUBSCRIBE * → {ok('PSUBSCRIBE *')}。SUBSCRIBE news:*(把它当普通频道名)→ {ok('SUBSCRIBE news:*')}。SSUBSCRIBE news:1 → {ok('SSUBSCRIBE news:1')}。", kv=KV([['PSUBSCRIBE news:*', ok('PSUBSCRIBE news:*')], ['PSUBSCRIBE news:a*', ok('PSUBSCRIBE news:a*')], ['PSUBSCRIBE *', ok('PSUBSCRIBE *')]], ['PSUBSCRIBE news:a*'])),
    step("u2 订阅了 news:1,管理员发布一条,u2 收到。然后管理员执行 ACL SETUSER u2 resetchannels——", n=fl([['u2 SUBSCRIBE news:1', '已订阅'], ['PUBLISH news:1 before', 'u2 收到']], done=[0, 1]), kv=KV([['撤销前', '收到消息']], ['撤销前'])),
    step(f"撤销后订阅连接读到的结果:{R['revoke']}——服务端主动断开了这条订阅连接;之后 PUBLISH news:1 返回 0 个订阅者,PUBSUB CHANNELS 为空。撤销频道权限会立刻踢掉正在订阅的连接。", n=fl([['ACL SETUSER u2 resetchannels', ''], ['u2 订阅连接', 'EOF(被断开)'], ['PUBLISH news:1', '0 个订阅者']], mark=[1]), kv=KV([['撤销后', R['revoke']], ['订阅者数', 0]], ['撤销后'])),
    step(f"allchannels(即 &*)给了全部频道;把 acl-pubsub-default 改成 allchannels 后新建的 u4 自动带 &*({R['u4'].split('~*')[1].strip().split()[0]})。键空间通知的频道也要授权:u5 只有 &news:*,PSUBSCRIBE __keyspace@0__:* → 拒绝。", kv=KV([['allchannels', '&*'], ['u5 订阅 keyspace', '拒绝']], ['u5 订阅 keyspace'])),
]
A = dict(
    n=124, series='redis', tags='Redis,ACL,Pub/Sub,安全,真实验证,动画演示',
    desc='ACL Channel 实测:acl-pubsub-default 默认 resetchannels,新用户不能 PUBLISH / SUBSCRIBE;PSUBSCRIBE 的模式必须与授权模式字面相同;撤销频道权限会立即断开正在订阅的连接;键空间通知频道同样要授权。',
    lead='ACL 除了限制命令和 key,还限制频道(&pattern)。发布订阅出了名的没有认证之外的隔离,所以这一层要看清:哪些命令受它管、模式订阅怎么匹配、撤销权限时已经订阅的连接怎么办。全部在本机实例上实测。',
    facts=[('resetchannels', 'acl-pubsub-default 的默认值:新用户没有任何频道权限,连 PUBLISH 也不行'), ('字面相同', 'PSUBSCRIBE news:a* 在只有 &news:* 时被拒;模式必须与授权的模式字面一致'), ('EOF', '撤销频道权限后,正在订阅的连接被服务端断开')],
    body=[
        sec('默认值:没有频道权限', '', term('', blk('r124', 1)), term('', blk('r124', 2)), '<p>命令权限(<code>+@all</code>)和频道权限(<code>&amp;…</code>)是两套独立的东西。只给命令,不给频道,<code>PUBLISH</code> 和 <code>SUBSCRIBE</code> 都会被拒。<code>ACL LIST</code> 里看得见 <code>resetchannels</code>(即没有任何频道)。</p>'),
        sec('频道模式如何匹配', '', term('', blk('r124', 3)), '<p>DRYRUN 的判定见上表。要点:授权的是一个 glob 模式 <code>news:*</code>,普通订阅 <code>news:1</code> 命中它;而 <code>PSUBSCRIBE</code> 本身带模式,必须与已授权的模式<b>完全相同</b>——<code>news:a*</code> 虽然范围更小也被拒。<code>SUBSCRIBE news:*</code> 是把 <code>news:*</code> 当作一个普通频道名,能被 <code>&amp;news:*</code> 匹配,所以放行。(实测得到的行为;背后的匹配实现本文没有翻源码。)</p>'),
        sec('撤销权限时,已订阅的连接怎么办', '', term('', blk('r124', 4)), '<p>管理员 <code>resetchannels</code> 之后,服务端直接把这条订阅连接断开(客户端读到 EOF),不会留一个「还在订阅但没权限」的连接。所以客户端库要做好订阅连接被踢后重连(并重新鉴权,会被拒)的处理。</p>'),
        sec('allchannels 与键空间通知', '', term('', blk('r124', 5)), term('', blk('r124', 6)), '<p>想让新用户默认能用发布订阅,可以把 <code>acl-pubsub-default</code> 改成 <code>allchannels</code>——影响之后新建的用户。键空间通知的频道(<code>__keyspace@0__:*</code>)也归 ACL 管:没有授权的用户订阅不了,这是个天然的「谁能看到 key 变化」的开关。</p>'),
        sec('分步演示:频道权限', '', demo('ACL Channel', [('n', 'flow', '请求与结果'), ('t', 'term', '判定'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。判定用 ACL DRYRUN,撤销实验用真实订阅连接', '没有验证:Cluster 下 SSUBSCRIBE 的槽位与 ACL 的交互、模块命令、ACL 频道权限对 Lua 内 redis.call(PUBLISH) 的作用、版本差异(acl-pubsub-default 的默认值在 Redis 7 之前不同,未测)'],
)
