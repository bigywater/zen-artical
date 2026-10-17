import json, re
from lib import *
R = J('r61'); rows = R['rows']; mix = R['mix']
a, b, r = rows
sec_ = lambda x: float(re.search(r'([\d.]+) seconds', x['log']).group(1))
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def fl(nodes, cur=(), done=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done)}
steps = [
    step("同样的 50 万个 key(value 是 64 位随机十六进制,不易压缩),三种持久化配置各做一次持久化,再重启,量文件大小和加载时间。", f=fl([['AOF + preamble', '默认'], ['AOF 无 preamble', '纯命令'], ['只有 RDB', 'dump.rdb']], cur=[0, 1, 2]), kv=KV([['数据集', '500000 个 key']], ['数据集'])),
    step(f"文件头:preamble 的 base 是 {a['head'][:12]}…(RDB),无 preamble 的 base 是 *2\\r\\n$6\\r\\nSELECT…(命令文本)。preamble=yes 的 AOF base 与 dump.rdb 的文件头一样。", f=fl([['base.rdb', 'REDIS0015…'], ['base.aof', '*2 $6 SELECT …'], ['dump.rdb', 'REDIS0015…']], cur=[0, 1, 2]), kv=KV([['preamble yes', 'RDB 格式'], ['preamble no', 'RESP 命令文本']], ['preamble no'])),
    step(f"大小:RDB 格式 {a['size']/1e6:.1f} MB(AOF base 与 dump.rdb 完全一样大:{r['size']/1e6:.1f} MB);命令文本格式 {b['size']/1e6:.1f} MB,大 {(b['size']/a['size']-1)*100:.0f}%。", b=bars([['AOF + preamble', a['size'], f"{a['size']/1e6:.1f} MB"], ['AOF 无 preamble', b['size'], f"{b['size']/1e6:.1f} MB"], ['只有 RDB', r['size'], f"{r['size']/1e6:.1f} MB"]], b['size'], mark=[1], done=[0, 2]), kv=KV([['命令文本比 RDB 大', f"{(b['size']/a['size']-1)*100:.0f}%"]], ['命令文本比 RDB 大'])),
    step(f"加载耗时(日志「DB loaded from … seconds」):AOF+preamble {sec_(a):.3f} s、AOF 无 preamble {sec_(b):.3f} s、只有 RDB {sec_(r):.3f} s。命令文本要一条条重放,比 RDB 慢 {(sec_(b)/sec_(a)-1)*100:.0f}%(单次测量)。", b=bars([['AOF + preamble', sec_(a), f'{sec_(a):.3f} s'], ['AOF 无 preamble', sec_(b), f'{sec_(b):.3f} s'], ['只有 RDB', sec_(r), f'{sec_(r):.3f} s']], sec_(b), mark=[1], done=[0, 2]), kv=KV([['结论', 'preamble 的加载速度 ≈ RDB']], ['结论'])),
    step(f"混合持久化 = RDB base + 之后的增量命令。重写后再写 20 万个 key,incr 是 {mix['incr']/1e6:.1f} MB 的 RESP 文本。重启时日志分两步:先「Reading RDB base file」(约 0.20 s),再回放 incr(约 0.17 s),最终 DBSIZE = {mix['db']}(50 万 + 20 万),总加载约 0.38 s。", f=fl([['base:RDB 快照', '50 万 key'], ['incr:命令回放', '20 万条 SET']], cur=[0, 1]), kv=KV([['DBSIZE', str(mix['db'])], ['incr', f"{mix['incr']/1e6:.1f} MB"]], ['DBSIZE'])),
]
A = dict(
    n=61, series='redis', tags='Redis,RDB,AOF,混合持久化,真实验证,动画演示',
    desc=f'50 万个 key 实测三种持久化格式:AOF 开 RDB preamble(默认)base {a["size"]/1e6:.1f} MB、加载 {sec_(a):.3f} s;关掉 preamble 的纯命令 base {b["size"]/1e6:.1f} MB、加载 {sec_(b):.3f} s;纯 RDB {r["size"]/1e6:.1f} MB、{sec_(r):.3f} s。混合持久化重启时先读 RDB base 再回放 incr 命令。',
    lead='「RDB 和 AOF 混合持久化」到底混合了什么?答案是:AOF 重写产出的 base 文件是 RDB 格式,之后追加的增量仍是命令文本。这篇用同一份 50 万个 key 的数据集,分别用 RDB、开 preamble 的 AOF、关 preamble 的 AOF 持久化,比较文件格式、大小和重启加载时间。',
    facts=[(f'{a["size"]/1e6:.1f} vs {b["size"]/1e6:.1f} MB', 'AOF base:RDB 格式(preamble yes)vs 命令文本(preamble no)'), (f'{sec_(a):.2f} vs {sec_(b):.2f} s', '重启加载耗时:preamble yes vs no'), (f'{mix["db"]}', '混合持久化重启后 DBSIZE(50 万 base + 20 万 incr)')],
    body=[
        sec('三种格式并排', '500000 个 key,每种配置一个新实例', term('', blk('r61', 1)),
            f'<p>文件头一眼就能分清:preamble 为 yes 时 AOF 的 base 文件以 <code>REDIS0015</code> 开头,是 RDB;为 no 时是 <code>*2\\r\\n$6\\r\\nSELECT</code> 开头的 RESP 命令文本。大小:RDB 格式 {a["size"]/1e6:.1f} MB(与纯 RDB 的 dump.rdb 一样大),命令文本 {b["size"]/1e6:.1f} MB,大约多 {(b["size"]/a["size"]-1)*100:.0f}%。加载耗时(日志里的秒数):{sec_(a):.3f} s / {sec_(b):.3f} s / {sec_(r):.3f} s(AOF+preamble / AOF 纯命令 / RDB)。<b>每种配置只做了一次重启测量</b>,毫秒级的差别不要当结论;命令文本更慢这个方向是清楚的(约 {(sec_(b)/sec_(a)-1)*100:.0f}%)。</p><p>这里的 value 是随机十六进制字符串,压缩率低,所以 RDB 只比命令文本小两成多;value 像上一个实验(第 54 篇)里那样重复度高时,RDB 会小得多。</p>'),
        sec('「混合」:RDB base + 增量命令', '', term('', blk('r61', 2)),
            f'<p>重写之后再写 20 万个 key,incr 文件是 {mix["incr"]/1e6:.1f} MB 的命令文本(开头能看到 <code>SELECT 0</code> 和 <code>SET new:0 …</code>)。重启日志分两段:<code>DB loaded from base file … 0.202 seconds</code>,然后 <code>DB loaded from incr file … 0.174 seconds</code>,合计 0.377 秒,DBSIZE = {mix["db"]}。增量越大,回放越久——这也是要定期重写的原因。</p>'),
        sec('分步演示:三种格式', '', demo('混合持久化', [('f', 'flow', '格式'), ('b', 'bars', '大小 / 耗时'), ('kv', 'kv', '观察')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。三种配置的对比来自同一份数据(random.Random(1) 生成);每种配置只测一次重启', '没有验证:更大的数据集下的差别、value 高度可压缩时的大小差异、AOF 混合持久化在 fork 时对主进程的影响(第 66 篇)、关闭 aof-use-rdb-preamble 后重写产出 base.aof 的其它细节'],
)
