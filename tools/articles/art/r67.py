import json
from lib import *
R = J('r67'); T = R['t']; S = R['size']; I = R['incr']
sizes = ['100000', '500000', '1000000', '2000000']
rdb = {int(k): v for k, v in T['RDB'].items()}; aofr = {int(k): v for k, v in T['AOF(RDB base)'].items()}; aofc = {int(k): v for k, v in T['AOF(纯命令)'].items()}
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
per_rdb = rdb[2000000] / 2.0; per_aofc = aofc[2000000] / 2.0
inc0 = I[0][2]; per_inc = [(w - inc0) / (x / 1e6) for x, _, w in I if x]
steps = [
    step("同样的 key(value 是 64 位随机十六进制)在四个数据集大小上:10 万、50 万、100 万、200 万。每种配置持久化后正常停止,再启动,量「进程启动 → INFO loading 变成 0」的耗时。", b=bars([['RDB', 1, ''], ['AOF(RDB base)', 1, ''], ['AOF(纯命令)', 1, '']], 1), kv=KV([['测量', '启动到 loading=0']], [])),
    step(f"100 万个 key:RDB {rdb[1000000]:.2f} s、AOF(RDB base){aofr[1000000]:.2f} s、AOF 纯命令 {aofc[1000000]:.2f} s。RDB 与 RDB base 的 AOF 几乎一样快——文件内容就是同样的 RDB。", b=bars([['RDB', rdb[1000000], f'{rdb[1000000]:.2f} s'], ['AOF(RDB base)', aofr[1000000], f'{aofr[1000000]:.2f} s'], ['AOF(纯命令)', aofc[1000000], f'{aofc[1000000]:.2f} s']], aofc[1000000], done=[0, 1], mark=[2]), kv=KV([['100 万 key', f'{rdb[1000000]:.2f} / {aofr[1000000]:.2f} / {aofc[1000000]:.2f} s']], ['100 万 key'])),
    step(f"加载时间随数据量近似线性:RDB 从 {rdb[100000]:.2f} s(10 万)到 {rdb[2000000]:.2f} s(200 万),约 {per_rdb:.2f} s/百万 key;纯命令 AOF 约 {per_aofc:.2f} s/百万 key,慢约 {(per_aofc/per_rdb-1)*100:.0f}%。", b=bars([[f'RDB {n}', rdb[n], f'{rdb[n]:.2f} s'] for n in (100000, 500000, 1000000, 2000000)], rdb[2000000], done=[0, 1, 2, 3]), kv=KV([['RDB 加载速度', f'约 {1/per_rdb:.1f} 百万 key/秒']], ['RDB 加载速度'])),
    step(f"磁盘大小:200 万个 key,RDB {S['RDB']['2000000']/1e6:.0f} MB、AOF base(RDB 格式)完全相同、纯命令 AOF {S['AOF(纯命令)']['2000000']/1e6:.0f} MB。", b=bars([['RDB', S['RDB']['2000000'], f"{S['RDB']['2000000']/1e6:.0f} MB"], ['AOF(RDB base)', S['AOF(RDB base)']['2000000'], f"{S['AOF(RDB base)']['2000000']/1e6:.0f} MB"], ['AOF(纯命令)', S['AOF(纯命令)']['2000000'], f"{S['AOF(纯命令)']['2000000']/1e6:.0f} MB"]], S['AOF(纯命令)']['2000000'], done=[0, 1], mark=[2]), kv=KV([['200 万 key', '159 / 159 / 205 MB']], ['200 万 key'])),
    step(f"如果 AOF 很久没重写:100 万 key 的 RDB base 之后又追加了 X 条 SET,重启要回放它们。追加 0 / 20 万 / 100 万 / 300 万条,重启总耗时 {I[0][2]:.2f} / {I[1][2]:.2f} / {I[2][2]:.2f} / {I[3][2]:.2f} s,每百万条命令约多 {sum(per_inc)/len(per_inc):.2f} s。", b=bars([[f'追加 {x//10000} 万条({inc/1e6:.0f} MB incr)', w, f'{w:.2f} s'] for x, inc, w in I], I[3][2], mark=[1, 2, 3], done=[0]), kv=KV([['每百万条命令', f'约 {sum(per_inc)/len(per_inc):.2f} s']], ['每百万条命令'])),
]
A = dict(
    n=67, series='redis', tags='Redis,持久化,重启,真实验证,动画演示',
    desc=f'量 Redis 重启恢复耗时:10 万到 200 万个 key,RDB 约 {per_rdb:.2f} s/百万 key,AOF(RDB base)相同,纯命令 AOF 约 {per_aofc:.2f} s/百万 key(慢 {(per_aofc/per_rdb-1)*100:.0f}%);AOF 未重写、base 之后追加的增量每百万条命令多约 {sum(per_inc)/len(per_inc):.2f} s(300 万条增量让 100 万 key 的重启从 {I[0][2]:.2f} s 变成 {I[3][2]:.2f} s)。',
    lead='Redis 重启之后多久能服务?答案取决于两件事:要加载多少数据,以及数据是以什么格式落在磁盘上。这篇在 10 万到 200 万个 key 上,实测三种持久化配置的重启耗时,再看 AOF 增量没重写时会拖多久。',
    facts=[(f'{per_rdb:.2f} s / 百万 key', f'RDB(及 RDB base 的 AOF)的重启加载速度;200 万个 key 需要 {rdb[2000000]:.2f} s'), (f'{per_aofc:.2f} s / 百万 key', f'纯命令 AOF 的加载速度,比 RDB 慢约 {(per_aofc/per_rdb-1)*100:.0f}%'), (f'{I[0][2]:.2f} → {I[3][2]:.2f} s', '100 万 key 的 base 之后追加 300 万条 SET 未重写时的重启耗时')],
    body=[
        sec('不同数据量:重启耗时', '每格一个新实例:写入 → 持久化 → 正常停止 → 重启,计时到 loading=0', term('', blk('r67', 1)),
            f'<p>加载耗时随 key 数近似线性:RDB 200 万个 key {rdb[2000000]:.2f} s,约每百万 {per_rdb:.2f} s。AOF 用 RDB 作 base 时和 RDB 几乎一样;纯命令的 AOF 每百万 key 约 {per_aofc:.2f} s,慢约 {(per_aofc/per_rdb-1)*100:.0f}%——它要解析并执行每一条命令。本机的 SSD、CPU 与 key/value 大小决定了这些绝对值,只有「线性」和「相对比例」可以迁移到别的机器。</p>'),
        sec('磁盘上的大小', '', term('', blk('r67', 2)), f'<p>RDB 与 AOF(RDB base)的文件大小完全一样(同一份 RDB);纯命令 AOF 大约多 {(S["AOF(纯命令)"]["2000000"]/S["RDB"]["2000000"]-1)*100:.0f}%。(value 是随机字符串,几乎不可压缩;value 重复度高时 RDB 会小得多。)</p>'),
        sec('AOF 没重写:增量要回放', '100 万个 key 的 base 之后又追加 X 条 SET', term('', blk('r67', 3)),
            f'<p>base 固定是 100 万个 key(重启 {I[0][2]:.2f} s),之后追加的命令不重写,重启时要逐条回放:20 万条(13 MB incr)多 {I[1][2]-I[0][2]:.2f} s,100 万条多 {I[2][2]-I[0][2]:.2f} s,300 万条(203 MB)多 {I[3][2]-I[0][2]:.2f} s,每百万条约 {sum(per_inc)/len(per_inc):.2f} s。这里的增量都是简单的 SET;对同一批 key 的反复修改,回放的条数远多于最终的 key 数。<b>所以自动重写(第 59 篇)不只是省磁盘,也是在控制重启时间。</b></p>'),
        sec('这个实验没有包含的部分', '', '<p>重启耗时只是「Redis 能服务」的一部分。真实的恢复时间还要加上:进程被外部拉起的延迟、从库场景下的复制追赶(第 54–58 篇)、客户端重连。同时,本机数据集最大只有 200 万个 key(约 160 MB),更大的数据集、更慢的磁盘、更大的 value 都会改变绝对值。</p>'),
        sec('分步演示:三种配置与增量', '', demo('Redis 重启恢复耗时', [('b', 'bars', '耗时 / 大小'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。正常停止(SIGTERM)后启动;耗时从启动进程到 INFO persistence 的 loading:0;value 是 random.Random 生成的 64 位十六进制字符串', '没有验证:崩溃后(而非正常停止)的启动、超过 200 万个 key 的数据集、RDB 压缩开启对加载耗时的影响(本文的 value 不易压缩)、从库启动后与主库追赶的时间'],
)
