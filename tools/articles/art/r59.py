import json
from lib import *
R = J('r59'); sz = R['sizes']; au = R['auto']
incr_b = [s for f, s in sz['before'] if 'incr' in f][0]; base_a = [s for f, s in sz['after'] if 'base' in f][0]
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def fl(nodes, cur=(), done=()): return {'nodes': nodes, 'cur': list(cur), 'done': list(done)}
steps = [
    step("appendonly yes 的新实例:appendonlydir 里有三个文件——base(基础 RDB,89 字节,几乎是空的)、incr(增量 AOF,0 字节)、manifest(清单,列出前两者及序号)。", f=fl([['appendonly.aof.1.base.rdb', '89 B'], ['appendonly.aof.1.incr.aof', '0 B'], ['manifest', '102 B']], cur=[0, 1, 2]), kv=KV([['结构', 'base + incr + manifest']], ['结构'])),
    step(f"写入 30 万次 INCR counter 和 5 万个 SET:所有写命令追加到当前 incr 文件,涨到 {incr_b/1e6:.1f} MB;base 还是 89 字节。", f=fl([['base', '89 B'], ['incr', f'{incr_b/1e6:.1f} MB'], ['manifest', '102 B']], cur=[1]), b=bars([['incr 文件', incr_b, f'{incr_b/1e6:.1f} MB']], incr_b, mark=[0]), kv=KV([['写入', '350000 条命令']], ['写入'])),
    step("BGREWRITEAOF:主进程立刻新开一个 incr 文件(日志「Creating AOF incr file appendonly.aof.2.incr.aof on background rewrite」),之后的新写入进新文件;fork 出的子进程把「此刻的数据集」写成新的 base。", f=fl([['新 incr .2', '接收新写入'], ['fork 子进程', '写 temp base'], ['旧 base .1 + 旧 incr .1', '暂不动']], cur=[0, 1], done=[2]), kv=KV([['日志', 'Creating AOF incr file … on background rewrite']], ['日志'])),
    step(f"子进程完成后 rename 成 appendonly.aof.2.base.rdb,manifest 改为指向新的 base 和新的 incr;旧的 base、incr 被清掉。{incr_b/1e6:.1f} MB 的增量折叠成了 {base_a/1e6:.2f} MB 的 base(30 万次 INCR 只剩 counter = 300000 一条数据)。", f=fl([['base .2', f'{base_a/1e6:.2f} MB'], ['incr .2', '0 B'], ['manifest → .2', '']], done=[0, 1, 2]), b=bars([['重写前 incr', incr_b, f'{incr_b/1e6:.1f} MB'], ['重写后 base', base_a, f'{base_a/1e6:.2f} MB']], incr_b, done=[1]), kv=KV([['DBSIZE', '50001'], ['counter', '300000']], ['counter'])),
    step("新 base 的前 9 字节是 REDIS0015:base 是 RDB 格式(aof-use-rdb-preamble 默认 yes),不是命令文本。这样重启时加载 base 快得多。", f=fl([['base .2', 'REDIS0015…'], ['incr .2', 'RESP 命令']], cur=[0]), kv=KV([['base 格式', 'RDB']], ['base 格式'])),
    step(f"自动触发:auto-aof-rewrite-percentage 100、min-size 1 MB。持续写入直到日志出现 Starting automatic rewriting of AOF on 192% growth:当时 base = {au['base']} B,current = {au['cur']} B(约 {au['cur']/au['base']:.1f} 倍)。", b=bars([['aof_base_size', au['base'], f"{au['base']} B"], ['aof_current_size', au['cur'], f"{au['cur']} B"]], au['cur'], mark=[1]), kv=KV([['触发时增长', '192%']], ['触发时增长'])),
]
A = dict(
    n=59, series='redis', tags='Redis,AOF,持久化,真实验证,动画演示',
    desc=f'观察 Redis 8 的 AOF Rewrite:appendonlydir 里是 base(RDB 格式)+ incr(命令)+ manifest 三种文件;BGREWRITEAOF 会先新开一个 incr 再由子进程写新 base,{incr_b/1e6:.1f} MB 的 incr(30 万次 INCR + 5 万个 SET)折叠成 {base_a/1e6:.2f} MB 的 base;auto-aof-rewrite-percentage 100 时在增长 192% 处自动触发。',
    lead='AOF 只追加、从不修改,文件会越长越大。AOF Rewrite 就是把「重放后得到当前数据集所需的最少命令」重新写一遍,替换掉旧的。Redis 7 之后 AOF 的文件结构也变了(不再是单个 appendonly.aof)。这篇直接看 appendonlydir 里的文件、manifest 的变化和日志,把一次重写从头到尾走一遍。',
    facts=[(f'{incr_b/1e6:.1f} → {base_a/1e6:.2f} MB', '30 万次 INCR + 5 万个 SET 的 incr 文件,重写后变成的 base'), ('3 种文件', 'appendonlydir:base(RDB 格式)、incr(命令)、manifest(清单)'), ('192%', '自动触发重写时,AOF 相对 base 的增长(配置 percentage = 100)')],
    body=[
        sec('AOF 现在长什么样', '', term('', blk('r59', 1)), '<p>启动一个新的 appendonly 实例:<code>appendonlydir</code> 里有 base(<code>appendonly.aof.1.base.rdb</code>)、incr(<code>appendonly.aof.1.incr.aof</code>)和 <code>appendonly.aof.manifest</code>。manifest 列出当前有效的文件、序号和类型(<code>b</code> = base,<code>i</code> = incr)。</p>'),
        sec('一次重写前后', '为了看清过程,先把自动重写关掉(auto-aof-rewrite-percentage 0)', term('', blk('r59', 2)),
            f'<p>写入 30 万次 <code>INCR counter</code> 和 5 万个 SET 之后,incr 文件有 {incr_b/1e6:.1f} MB。<code>BGREWRITEAOF</code> 完成(约 0.15 s)后,文件变成 <code>appendonly.aof.2.base.rdb</code>({base_a/1e6:.2f} MB)加一个空的新 incr;manifest 指向新的一对,旧文件被删除。30 万次 INCR 折叠成一条 counter = 300000。manifest 里的 <code>startoffset 350000</code> 我没有追究它的精确定义(与写入的命令数 350000 相同)。</p>'),
        sec('base 是 RDB 格式', '', term('', blk('r59', 3)), '<p>新 base 的文件头是 <code>REDIS0015</code>——RDB。默认 <code>aof-use-rdb-preamble yes</code>,重写产出的 base 是 RDB 快照,之后的增量才是命令文本。混合持久化的详细对比见第 61 篇。</p>'),
        sec('日志里的时间线', '', term('', blk('r59', 4)), '<p>关键顺序:先 <code>Creating AOF incr file … on background rewrite</code>(新写入从这一刻起进新 incr),再 <code>Background append only file rewriting started by pid …</code>(fork),子进程写 <code>temp-rewriteaof-bg-….aof</code>,成功后 rename 为新的 base,最后 <code>Background AOF rewrite finished successfully</code>。重写期间的写入不需要在内存里缓冲、再补写——它们直接进新的 incr 文件(见第 60 篇)。</p>'),
        sec('自动触发', '', term('', blk('r59', 5)), f'<p>自动重写关掉之后,把 <code>auto-aof-rewrite-percentage</code> 设回 100(<code>auto-aof-rewrite-min-size</code> 设 1 MB)并继续写入,日志出现 <code>Starting automatic rewriting of AOF on 192% growth</code>:当时 <code>aof_base_size</code> = {au["base"]}、<code>aof_current_size</code> = {au["cur"]}。触发点是 AOF 相对 base 的增长(百分比)超过阈值且大小超过 min-size;实际触发时的 192% 大于 100%,因为我的写入是每批 2000 个 key,检查有间隔,没有精确停在 100%。</p>'),
        sec('分步演示:一次 AOF 重写', '', demo('AOF Rewrite', [('f', 'flow', 'appendonlydir 里的文件'), ('b', 'bars', '大小'), ('kv', 'kv', '观察')], steps, '本步涉及的文件')),
    ],
    refs=[ENV_R + '。appendonly yes、appendfsync everysec;重写演示时自动重写被关闭', '没有验证:数据集很大时重写对主进程的影响(见第 66 篇)、重写失败与重试、aof-use-rdb-preamble no 时的 base 格式(第 61 篇)、manifest 各字段的完整含义'],
)
