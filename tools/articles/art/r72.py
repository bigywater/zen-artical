import json
from lib import *
R = J('r72'); hot = R['hot']; sp = R['spread']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
hp = sorted(hot); sq = sorted(sp)
steps = [
    step("没有 hash tag:同一个用户的 user1:profile、user1:orders、user1:cart 分别落在槽 12715、1543、9467——三个不同的槽,很可能在不同的节点上,没法一起用多 key 命令。", t=tm(['user1:profile → 槽 12715', 'user1:orders  → 槽 1543', 'user1:cart    → 槽 9467'], mark=[0, 1, 2]), kv=KV([['槽位', '三个不同']], ['槽位'])),
    step("加上 hash tag:{user1}:profile、{user1}:orders、{user1}:cart 只用花括号里的 user1 计算 CRC16,三个 key 都在槽 8106,必在同一个节点。", t=tm(['{user1}:profile → 槽 8106', '{user1}:orders  → 槽 8106', '{user1}:cart    → 槽 8106'], cur=[0, 1, 2]), kv=KV([['槽位', '全部 8106']], ['槽位'])),
    step("解析规则(服务器与我的推断逐条对照,全部一致):取第一个 { 和它之后的第一个 } 之间的内容,内容非空才生效。a{b}c → 用 b;{}a → 花括号里是空的,整个 key 参与;{a → 没有右括号,整个 key;{{a}} → 用 {a(第一个 { 到第一个 })的内容;{a}{b}、{a}}、{a}b}c → 都用 a。", t=tm(["'a{b}c'  → 用 'b'", "'{}a'    → 用整个 key", "'{a'     → 用整个 key", "'{{a}}'  → 用 '{a'", "'{a}{b}' → 用 'a'"], cur=[0, 3, 4], mark=[1, 2]), kv=KV([['规则一致', '12 / 12']], ['规则一致'])),
    step(f"代价:一个 tag 只对应一个槽,一个槽只在一个节点上。10 万个 key 都用 {{user1}} 写入,三个主库的 DBSIZE 是 {hot[str(hp[0])]} / {hot[str(hp[1])]} / {hot[str(hp[2])]}——全在一个节点上,CLUSTER COUNTKEYSINSLOT 8106 = 100000。", b=bars([[f'主库 {p}', hot[str(p)], str(hot[str(p)])] for p in hp], 100000, mark=[1]), kv=KV([['数据分布', '100% 在一个节点']], ['数据分布'])),
    step(f"折中:把 tag 拆成 64 份({{user1:0}}…{{user1:63}}):10 万个 key 均匀分散到 64 个槽(每个 tag 内仍可多 key 操作),三个主库 {sp[str(sq[0])]} / {sp[str(sq[1])]} / {sp[str(sq[2])]}。不是完全均等——64 个 tag 掉进三个节点的槽段是随机的。", b=bars([[f'主库 {p}', sp[str(p)], str(sp[str(p)])] for p in sq], 100000 / 2, done=[0, 1, 2]), kv=KV([['分成 64 个 tag', f'{sp[str(sq[0])]} / {sp[str(sq[1])]} / {sp[str(sq[2])]}']], ['分成 64 个 tag'])),
]
A = dict(
    n=72, series='redis', tags='Redis,Cluster,Hash Tag,真实验证,动画演示',
    desc=f'验证 Redis Cluster hash tag:{{user1}}:profile / :orders / :cart 都在槽 8106;12 种边界写法(空花括号、缺右括号、嵌套、多组)的槽位与「第一个 {{ 到第一个 }}、内容非空才生效」的规则完全一致;10 万个 key 都用 {{user1}} 时全部落在一个主库({hot[str(hp[1])]} / 0 / 0),拆成 64 个 tag 后分散为 {sp[str(sq[0])]} / {sp[str(sq[1])]} / {sp[str(sq[2])]}。',
    lead='Redis Cluster 里多 key 命令(MSET、事务、Lua)的前提是所有 key 在同一个槽里。Hash tag 是让它们「被迫」同槽的办法:只对 key 里花括号中的部分算 CRC16。这篇把 tag 的解析规则逐条对照服务器验证,再看它最典型的代价——热点:一个 tag 就是一个槽,一个槽只能在一个节点上。',
    facts=[('槽 8106', '{user1}:profile / :orders / :cart 三个 key 的共同槽位'), ('12 / 12', 'hash tag 解析规则的推断与服务器 CLUSTER KEYSLOT 一致的用例数'), (f'{hot[str(hp[1])]} / 0 / 0', '10 万个 key 全用同一个 tag 时,三个主库的 DBSIZE')],
    body=[
        sec('没有 tag vs 有 tag', '', term('', blk('r72', 1)), '<p>没有 tag 时同一个用户的三个 key 落在三个不同的槽(12715、1543、9467);加上 <code>{user1}</code> 之后,三个 key 都只用 <code>user1</code> 计算,槽位一致(8106)。</p>'),
        sec('解析规则', '', term('', blk('r72', 2)), '<p>我把「取第一个 <code>{</code> 和它之后第一个 <code>}</code> 之间的内容,内容为空则整个 key 参与计算」这条规则实现出来,对 12 个边界写法逐条与 <code>CLUSTER KEYSLOT</code> 对照,全部一致。几个容易搞错的:<code>{}a</code>(空花括号)整个 key 参与;<code>{{a}}</code> 取的是 <code>{a</code>;<code>{a}{b}</code> 只看第一组;缺右括号的 <code>{a</code> 整个 key 参与。空字符串的槽位是 0。</p>'),
        sec('代价:热点', '', term('', blk('r72', 3)), f'<p>10 万个 key 都用 <code>{{user1}}</code>,它们全在槽 8106,也就全在同一个主库(三个主库 DBSIZE 为 0 / {hot[str(hp[1])]} / 0)。槽是迁移的最小单位,这个热点槽<b>没法被拆分到别的节点</b>——只能把整个槽搬走。</p>'),
        sec('折中:把 tag 拆细', '', term('', blk('r72', 4)), f'<p>把 tag 拆成 64 份(<code>{{user1:0}}</code>…<code>{{user1:63}}</code>):10 万个 key 分散到 64 个不同的槽,三个主库 {sp[str(sq[0])]} / {sp[str(sq[1])]} / {sp[str(sq[2])]},不是严格均等(64 个 tag 掉进三个槽段是随机的)。代价是:只有落在同一个 tag 里的 key 才能一起做多 key 操作。所以 tag 的粒度就是「你需要多 key 原子性的最大范围」。</p>'),
        sec('分步演示:tag 的规则与代价', '', demo('Redis Cluster Hash Tag', [('t', 'term', '槽位'), ('b', 'bars', '数据分布'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。3 主 3 从;规则验证用 12 个用例,分布实验用 10 万个 key', '没有验证:非 ASCII / 二进制 key 的 tag 行为、tag 与 Pub/Sub 的关系、hash tag 对 MEMORY 或 SCAN 行为的影响'],
)
