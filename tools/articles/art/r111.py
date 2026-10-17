import json
from lib import *
R = J('r111'); m1, m2 = R['m1'], R['m2']
u1, u2, r1, r2 = int(m1['used_memory']) / 1e6, int(m2['used_memory']) / 1e6, int(m1['used_memory_rss']) / 1e6, int(m2['used_memory_rss']) / 1e6
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("先说一个前提:主动碎片整理(activedefrag)需要 Redis 使用特制的 jemalloc。这台机器上的 Redis(Homebrew 构建)的 mem_allocator 是 libc。", t=tm(['mem_allocator = libc']), kv=KV([['分配器', 'libc(不是 jemalloc)']], ['分配器'])),
    step("因此开启会失败:CONFIG SET activedefrag yes → ERR … Active defragmentation cannot be enabled: it requires a Redis server compiled with a modified Jemalloc like the one shipped by default with the Redis source distribution。所以我没法在这台机器上演示「整理」本身,只能演示「碎片是怎么来的」。", t=tm(['> CONFIG SET activedefrag yes', '(error) … Active defragmentation cannot be enabled: it requires a Redis server compiled with a modified Jemalloc …'], mark=[1]), kv=KV([['activedefrag', '本机不可用']], ['activedefrag'])),
    step(f"制造碎片:写入 100 万个 key(value 20–199 字节随机),used_memory {u1:.0f} MB、used_memory_rss {r1:.0f} MB,mem_fragmentation_ratio = {m1['mem_fragmentation_ratio']}(健康)。", b=bars([['used_memory', u1, f'{u1:.0f} MB'], ['used_memory_rss', r1, f'{r1:.0f} MB']], r2, done=[0, 1]), kv=KV([['mem_fragmentation_ratio', m1['mem_fragmentation_ratio']]], ['mem_fragmentation_ratio'])),
    step(f"随机删除其中 90% 的 key:used_memory 降到 {u2:.0f} MB(-{(1-u2/u1)*100:.0f}%),但 used_memory_rss 是 {r2:.0f} MB,一点没降。mem_fragmentation_ratio = {m2['mem_fragmentation_ratio']}——RSS 是 used_memory 的 {float(m2['mem_fragmentation_ratio']):.0f} 倍。释放出来的内存没有还给操作系统。", b=bars([['used_memory', u2, f'{u2:.0f} MB'], ['used_memory_rss', r2, f'{r2:.0f} MB']], r2, mark=[1], done=[0]), kv=KV([['mem_fragmentation_ratio', f"{m1['mem_fragmentation_ratio']} → {m2['mem_fragmentation_ratio']}"]], ['mem_fragmentation_ratio'])),
    step("MEMORY PURGE 返回 OK,但在 libc 分配器上它没有产生可见效果(RSS 没降);MEMORY DOCTOR 会给出「Peak memory: 曾经用过的内存超过当前的 150%,分配器通常无法在峰值后释放内存」这类诊断。这就是碎片比 10 的含义:内存在,但对系统来说仍被占着。", t=tm(['> MEMORY PURGE → OK(无可见效果)', 'MEMORY DOCTOR: Peak memory: … The allocator is normally not able to release memory after a peak …'], cur=[1]), kv=KV([['结论', '碎片 = 已释放但未归还系统的内存']], ['结论'])),
]
A = dict(
    n=111, series='redis', tags='Redis,内存碎片,Active Defrag,真实验证,动画演示',
    desc=f'在 libc 分配器的 Redis 上演示内存碎片的来历:写入 100 万个 key 后随机删除 90%,used_memory 从 {u1:.0f} MB 降到 {u2:.0f} MB,used_memory_rss 却仍是 {r2:.0f} MB,mem_fragmentation_ratio 从 {m1["mem_fragmentation_ratio"]} 涨到 {m2["mem_fragmentation_ratio"]};并如实记录:主动碎片整理(activedefrag)需要 jemalloc,本机构建不支持,CONFIG SET 直接报错。',
    lead='这篇有一个遗憾要先说:Active Defrag(主动碎片整理)只在特制的 jemalloc 构建上可用,我这台机器上的 Redis 用的是 libc,开启会直接失败——所以我没法演示「整理」本身。能演示、并且值得演示的是它要解决的问题:碎片是怎么产生的,有多严重。这部分是完整实测的。',
    facts=[('libc,不是 jemalloc', 'activedefrag 在本机构建上不能启用,CONFIG SET 报错'), (f'{u1:.0f} → {u2:.0f} MB', '随机删除 90% 的 key:used_memory 的变化'), (f'{r1:.0f} → {r2:.0f} MB', '同一过程 used_memory_rss(操作系统眼中的占用)几乎没变')],
    body=[
        sec('先看分配器', '', term('', blk('r111', 1)), '<p><code>INFO memory</code> 里的 <code>mem_allocator</code> 是 <code>libc</code>。Redis 官方源码自带并默认使用的是定制的 jemalloc;Homebrew 这个构建用了系统的 libc malloc。</p>'),
        sec('开启 activedefrag', '', term('', blk('r111', 2)), '<p>报错原文:<code>Active defragmentation cannot be enabled: it requires a Redis server compiled with a modified Jemalloc like the one shipped by default with the Redis source distribution</code>。所以「主动碎片整理有多有效」这个问题,本文没有答案;需要在 jemalloc 构建(比如官方 Docker 镜像)上测。我这台机器上 Docker 没有运行,没法补上。</p>'),
        sec('碎片是怎么来的', '100 万个 key,value 20–199 字节随机;然后随机删除 90%', term('', blk('r111', 3)), f'<p>写入完成时 <code>used_memory</code> {u1:.0f} MB、<code>used_memory_rss</code> {r1:.0f} MB,碎片率 {m1["mem_fragmentation_ratio"]}。随机删掉 90% 的 key 之后 <code>used_memory</code>(Redis 自己统计的已分配)降到 {u2:.0f} MB,但 <code>used_memory_rss</code> 仍是 {r2:.0f} MB——碎片率 {m2["mem_fragmentation_ratio"]}。原因:被删除的 key 散落在整个堆里,每个大块里都还夹着仍然存活的 key,分配器无法把整块还给系统。(这里是 libc 分配器 + macOS;jemalloc 上的表现会不同,我没有测。)</p>'),
        sec('MEMORY PURGE 与 MEMORY DOCTOR', '', term('', blk('r111', 4)), '<p><code>MEMORY PURGE</code> 让分配器尝试归还内存,在 libc 上返回 OK 但没有可见效果。<code>MEMORY DOCTOR</code> 给出的诊断对应「峰值之后分配器通常无法释放内存」——它没有说这是「碎片」,而是「峰值」;两者在这个实验里其实是同一件事的两种说法。</p>'),
        sec('这个指标怎么读', '', '<p><code>mem_fragmentation_ratio</code> = RSS ÷ <code>used_memory</code>。远大于 1 表示「进程占着系统的内存,但 Redis 自己已经没在用」;小于 1 则通常意味着发生了 swap。它不等于「可以回收」:回收要靠 active defrag(需要 jemalloc)、重启,或者让新数据重新利用这些空洞。本文只验证了「这个比值会变得很高」,没有验证「怎么降下来」。</p>'),
        sec('分步演示:碎片的来历', '', demo('Redis Active Defrag', [('t', 'term', '输出'), ('b', 'bars', '内存'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。Homebrew 构建,mem_allocator=libc;value 长度 20–199 字节随机(random.Random(4));删除是随机选 90% 的 key', '没有验证:activedefrag 本身的效果与开销(需要 jemalloc)、jemalloc 上的碎片形态、MEMORY PURGE 在 jemalloc 上的效果、Linux 上 RSS 的表现、overcommit 与 THP 对碎片的影响'],
)
