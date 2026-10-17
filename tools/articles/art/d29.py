from lib import *
import re
R = J('d29')
def parse(txt):
    out = []
    for l in txt.splitlines():
        m = re.search(r'^(.*?)\s+查询\s+(\d+)\s+次\s+([\d.]+)\s+ms', l)
        if m: out.append((m.group(1).strip(), int(m.group(2)), float(m.group(3))))
    return out
n1 = parse(R['n1']); pf = parse(R['perf'])
steps = [
    step("only('title') 只查 id 和 title;defer('body') 查除了 body 之外的所有列;only('title', 'author__name') 配合 select_related 时连表取作者名。被推迟的字段可以用 get_deferred_fields() 看到:only('title') 的实例推迟了 author_id 和 body,defer('body') 的实例只推迟 body。", t=tl([l for l in R['sql'].splitlines() if l.strip()], cur=[1, 2, 3]), kv=KV([['only', '白名单(主键始终会取)'], ['defer', '黑名单']], ['only'])),
    step(f"访问被推迟的字段会为每个实例再发一次查询:200 行 only('title') 只读 title 只要 {n1[1][1]} 次;又读了 body,变成 {n1[2][1]} 次(1 + 200),耗时 {n1[1][2]:.1f} → {n1[2][2]:.1f} ms。N+1 的另一种形态。", b=bars([[n[0][:22], n[1], str(n[1])] for n in n1], n1[2][1] * 1.1, mark=[2], done=[0, 1]), kv=KV([['读了推迟字段', f'{n1[1][1]} 次 → {n1[2][1]} 次查询']], ['读了推迟字段'])),
    step(f"2000 行、body 约 10 KB:取全部字段 {pf[0][2]:.1f} ms;defer('body') {pf[1][2]:.1f} ms;only('title') {pf[2][2]:.1f} ms;values_list('title', flat=True) {pf[3][2]:.1f} ms(不构造模型实例)。", b=bars([[p[0][:34], p[2], f"{p[2]:.1f}"] for p in pf], pf[0][2] * 1.1, done=[3]), kv=KV([['结论', '不要的大字段推迟掉;只要值用 values_list']], ['结论'])),
    step("对带推迟字段的实例 save():UPDATE 只写已加载并改过的列——UPDATE \"lab_article\" SET \"title\" = 'changed' WHERE id = 1,不会把没加载的 body 写成空。refresh_from_db(fields=['body']) 只取回这一个字段(SELECT id, body …),之后 deferred 只剩 author_id。", t=tl(R['save'].splitlines(), cur=[0, 1]), kv=KV([['save()', '只更新已加载的字段']], ['save()'])),
]
A = dict(
    n=29, series='django', tags='Django,ORM,only,defer,N+1,真实验证,动画演示',
    desc=f'实测 only() / defer():生成的 SQL 与被推迟字段;读了被推迟的字段会每行多一次查询(200 行 {n1[1][1]} → {n1[2][1]} 次);2000 行 × 10 KB 的 body 不同取法耗时 {pf[0][2]:.1f} / {pf[2][2]:.1f} / {pf[3][2]:.1f} ms;带推迟字段的实例 save() 只更新已加载的列。',
    lead='大字段不想每次都查,用 only() 或 defer() 就完事了吗?一旦你后面又读到了它,会发生什么?这篇数出额外的查询次数,并量不同取法的耗时。',
    facts=[(f'{n1[1][1]} → {n1[2][1]}', '200 行 only("title") 只读 title 与又读了 body 的查询次数'), (f'{pf[0][2]:.0f} → {pf[3][2]:.1f} ms', '2000 行 × 10 KB:取全部字段 → values_list 单列的耗时'), ('save()', '带推迟字段的实例 save() 只更新已加载的列')],
    body=[
        sec('生成的 SQL 与被推迟的字段', '', term('', blk('d29', 1)), '<p><code>only()</code> 是白名单(主键总是会取),<code>defer()</code> 是黑名单。<code>only(\'title\')</code> 连外键 <code>author_id</code> 也推迟了,访问 <code>a.author_id</code> 或 <code>a.author</code> 都会额外查询。</p>'),
        sec('读到推迟的字段', '', term('', blk('d29', 2)), '<p>模板里循环访问一个被 <code>defer</code> 的字段,是这个坑的高发场景。发现时用 <code>only()</code> 列全要用的字段,或直接 <code>values()</code> / <code>values_list()</code>。</p>'),
        sec('耗时', '', term('', blk('d29', 3)), '<p>SQLite 在本机,没有网络往返,所以字段体积带来的差别主要是读取和构造对象的代价;换成远程数据库,大字段的传输代价会更明显(本文没有测)。</p>'),
        sec('save() 与 refresh_from_db()', '', term('', blk('d29', 4)), '<p>对推迟了字段的实例调用 <code>save()</code>,Django 只更新已加载的字段,不会误把推迟的字段写掉。</p>'),
        sec('分步演示:only / defer', '', demo('only() 与 defer()', [('t', 'term', 'SQL / 输出'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;耗时取 5 轮最快', '没有验证:PostgreSQL / MySQL 下大字段的实际传输代价、only() 与多态继承 / 代理模型的交互、defer 用在 select_related 的关联字段上、被推迟字段在 pickle / 序列化中的行为'],
)
