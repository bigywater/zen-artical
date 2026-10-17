from lib import *
import re
R = J('d34')
rows = []
for l in R['perf'].splitlines():
    m = re.search(r'^(.*?)\s+([\d.]+) ms\s+峰值内存\s+([\d.]+) MiB', l)
    if m: rows.append((m.group(1).strip(), float(m.group(2)), float(m.group(3))))
steps = [
    step(f"20 万行、条件 a >= 100(约 19.99 万行满足)。qs.exists() {rows[0][1]:.2f} ms、qs.count() {rows[2][1]:.2f} ms,而 bool(qs) {rows[1][1]:.0f} ms、len(qs) {rows[3][1]:.0f} ms——后两者把所有行都取回来并构造成模型对象。", b=bars([[r[0][:34], r[1], f"{r[1]:.2f} ms"] for r in rows], rows[1][1] * 1.1, done=[0, 2], mark=[1, 3]), kv=KV([['exists / count', '在数据库里做'], ['bool / len', '取回全部行']], ['bool / len'])),
    step(f"内存:exists()、count() 几乎不占(<0.1 MiB);bool()、len() 各占约 {rows[1][2]:.0f} MiB;只想拿个数的替代写法 len(list(qs.values_list('a', flat=True))) 是 {rows[4][1]:.0f} ms / {rows[4][2]:.0f} MiB——仍然比 count() 重得多。", b=bars([[r[0][:34], r[2], f"{r[2]:.2f} MiB"] for r in rows], rows[1][2] * 1.1, done=[0, 2], mark=[1, 3]), kv=KV([['结论', '要「有没有」用 exists(),要「几个」用 count()']], ['结论'])),
    step("SQL:exists() → SELECT 1 … LIMIT 1;count() → SELECT COUNT(*);len() 与 bool() 都是完整的 SELECT 全部列(没有 LIMIT)。", t=tl(R['sql'].splitlines(), cur=[0, 1], mark=[2, 3]), kv=KV([['exists()', 'LIMIT 1'], ['count()', 'COUNT(*)']], ['exists()'])),
    step("如果 QuerySet 反正要迭代,缓存改变了答案:全新的 qs 先 count() 查 1 次,再 len(qs) 又查 1 次(填充缓存),之后 count / exists / len 都是 0 次。所以「先判断再遍历」在还没缓存时是两次查询;已经遍历过的 QuerySet 上,len / bool / count 免费。", t=tl(R['cache'].splitlines()), kv=KV([['缓存之后', 'count / exists / len 都是 0 次']], ['缓存之后'])),
]
A = dict(
    n=34, series='django', tags='Django,ORM,exists,count,真实验证,动画演示',
    desc=f'20 万行上量 exists() / count() / len() / bool():exists {rows[0][1]:.2f} ms,count {rows[2][1]:.2f} ms,len 与 bool 各 {rows[3][1]:.0f} ms 且占约 {rows[3][2]:.0f} MiB;len(list(values_list)) 也要 {rows[4][1]:.0f} ms;以及缓存对答案的影响。',
    lead='判断「有没有」和「有几个」有四种写法,差距有多大?这篇在 20 万行的表上把 exists、count、len、bool 的耗时、内存和 SQL 都量出来。',
    facts=[(f'{rows[0][1]:.2f} ms vs {rows[3][1]:.0f} ms', '20 万行:qs.exists() vs len(qs)'), (f'{rows[2][1]:.2f} ms', 'qs.count() 的耗时(SELECT COUNT(*))'), (f'{rows[3][2]:.0f} MiB', 'len(qs) / bool(qs) 构造模型对象的峰值内存')],
    body=[
        sec('量一量', '', term('', blk('d34', 1)), '<p>耗时取 3 次里最快的,内存另开一次用 tracemalloc 量峰值。</p>'),
        sec('为什么', '', term('', blk('d34', 2)), '<p><code>exists()</code> 让数据库找到第一行就停;<code>count()</code> 让数据库数;<code>len()</code> / <code>bool()</code> 是先把整个 QuerySet 求值。这里的差别是「数据库做」还是「Python 做」。</p>'),
        sec('缓存的影响', '', term('', blk('d34', 3)), '<p>已经求值过的 QuerySet,<code>len()</code> 是免费的;所以「后面反正要遍历,顺便判断」时可以直接用 <code>len()</code> / <code>bool()</code>,不要多写一次 <code>exists()</code>(第 27 篇)。</p>'),
        sec('分步演示:四种写法', '', demo('exists / count / len', [('b', 'bars', '耗时 / 内存'), ('t', 'term', 'SQL / 查询数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite,20 万行,a 列有索引;条件 a >= 100', '没有验证:PostgreSQL 上 COUNT(*) 对大表的代价(全表扫描)与近似计数、MySQL InnoDB 的 COUNT、分页里的 count(第 49 篇)'],
)
