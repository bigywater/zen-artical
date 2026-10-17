import json, re
from lib import *
R = J('r117'); bk = R['bigkeys']; mk = R['memkeys']; s1 = R['bk_s']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
sm = lambda L: [l.strip() for l in L if l.strip().startswith('Biggest') and 'found so far' not in l]
steps = [
    step("redis-cli --bigkeys 用 SCAN 扫全库,按类型报告最大的 key。同一份数据(30 万个小 key + 5 个大 key),-i 0.01 表示每 100 次 SCAN 睡 0.01 秒,降低对服务器的冲击。", t=tm(['redis-cli --bigkeys -i 0.01', f'耗时 {s1:.1f} s(含睡眠)']), kv=KV([['-i', '扫描时的休眠间隔']], ['-i'])),
    step("--bigkeys 的判据是「元素个数」(字符串是字节数):list 最大是 big:list(200000 items)、hash 是 big:hash(100000 fields)、字符串是 big:string(5242880 bytes)、set 是 big:set(150000 members)、zset 是 big:zset(50000 members)。", t=tm(sm(bk)), kv=KV([['判据', '元素个数(字符串:字节)']], ['判据'])),
    step("--memkeys 的判据是内存字节数(内部用 MEMORY USAGE):list 1700350、hash 5450727、字符串 5259293、set 6784700、zset 4256515 字节。这一次字节数最大的类型是 set,不是元素最多的 string。", t=tm(sm(mk)), kv=KV([['判据', 'MEMORY USAGE 字节数']], ['判据'])),
    step("同一批 key 在两种口径下排序不同:按元素数 string 5242880 最大,其次 list 200000、set 150000、hash 100000、zset 50000;按字节数 set 6.78 MB 最大,其次 hash 5.45 MB、string 5.26 MB、zset 4.26 MB、list 1.70 MB。元素多(list)不等于占内存多。", t=tm(['按元素数:string > list > set > hash > zset', '按字节数:set > hash > string > zset > list'], cur=[0, 1]), kv=KV([['结论', '找大 key 应该用 --memkeys 或 MEMORY USAGE']], ['结论'])),
    step("扫描过程中会打印进度行 [xx.xx%] Biggest … found so far:每发现一个更大的 key 就更新。最后是 summary。它们都只报告「每种类型最大的一个」,不会列出所有超过阈值的 key——要列出全部,得自己写扫描器(第 116 篇)。", t=tm(['[29.44%] Biggest set found so far "big:set" with 150000 members', '[38.21%] Biggest string found so far "big:string" with 5242880 bytes', '-------- summary -------'], cur=[0, 1, 2]), kv=KV([['输出', '每类型只报告最大的一个']], ['输出'])),
]
A = dict(
    n=117, series='redis', tags='Redis,大Key,redis-cli,真实验证,动画演示',
    desc=f'在有 5 个大 key 的实例上运行 redis-cli --bigkeys 与 --memkeys(-i 0.01,各约 {s1:.0f} s):--bigkeys 按元素个数报告(list 20 万 items、set 15 万 members……),--memkeys 按 MEMORY USAGE 字节数报告(set 6784700 字节最大);两种口径下的排序不同;两者都只报告每种类型最大的一个 key。',
    lead='redis-cli 自带两个找大 key 的开关:--bigkeys 与 --memkeys。名字很像,判据不同。这篇在同一份数据上各跑一次,把两者的输出并排,看它们各自给出什么、忽略什么。',
    facts=[('元素数 vs 字节数', '--bigkeys 按元素个数;--memkeys 按 MEMORY USAGE 的字节数'), ('6784700 字节', '--memkeys 找到的最大 key(big:set,15 万成员)'), (f'约 {s1:.0f} s', '扫描 30 万个 key 的耗时(-i 0.01,含休眠)')],
    body=[
        sec('--bigkeys', '', term('', blk('r117', 1)), '<p>每种类型最大的 key,「大」指元素个数(字符串是字节数)。进度行 <code>[xx.xx%] Biggest … found so far</code> 随扫描更新,最后是 summary。<code>-i 0.01</code> 让它每扫一批就睡一会儿。注意:它只给「每种类型最大的一个」,不列出全部超标的 key。</p>'),
        sec('--memkeys', '', term('', blk('r117', 2)), '<p>同样的框架,但每个 key 用 <code>MEMORY USAGE</code> 的字节数比较。这个版本上得到的最大的 set 是 big:set(6784700 字节),最大的 hash 是 big:hash(5450727 字节),最大的 list 只有 1700350 字节。</p>'),
        sec('两种口径并排', '', term('', blk('r117', 3)), '<p>元素最多的是 5 MB 的字符串(以字节计)与 20 万元素的 list,但字节数最大的是 15 万成员的 set。<b>找「占内存大」的 key 应该用 <code>--memkeys</code>;<code>--bigkeys</code> 适合找「元素多、可能造成遍历/删除慢」的集合。</b></p>'),
        sec('分步演示:两个开关', '', demo('redis-cli --bigkeys', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。同第 116 篇的数据集;redis-cli 8.10.2 -i 0.01;输出为去掉终端控制符后的文本', '没有验证:不带 -i 时对服务器的冲击、--memkeys 的 --memkeys-samples 选项、--bigkeys 的每类型统计(本版本的输出里没有出现)、集群模式下的行为'],
)
