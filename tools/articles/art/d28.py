from lib import *
R = J('d28')
import re
def parse(txt):
    out = {}
    for l in txt.splitlines():
        m = re.search(r'^(.*?)\s+查询\s+(\d+)\s+次\s+([\d.]+)\s+ms', l)
        if m: out[m.group(1).strip()] = (int(m.group(2)), float(m.group(3)))
    return out
fk = parse(R['fk']); mm = parse(R['m2m']); rv = parse(R['reverse'])
fkl = list(fk.values()); mml = list(mm.values()); rvl = list(rv.values())
steps = [
    step(f"2000 本书、100 个作者:不优化,每本书访问 b.author 就查一次——{fkl[0][0]} 次查询、{fkl[0][1]:.0f} ms。select_related('author'):{fkl[1][0]} 次(一条 INNER JOIN)、{fkl[1][1]:.0f} ms;prefetch_related('author'):{fkl[2][0]} 次、{fkl[2][1]:.0f} ms。", b=bars([['不优化(ms)', fkl[0][1], f"{fkl[0][1]:.0f}"], ['select_related(ms)', fkl[1][1], f"{fkl[1][1]:.0f}"], ['prefetch_related(ms)', fkl[2][1], f"{fkl[2][1]:.0f}"]], fkl[0][1] * 1.1, mark=[0], done=[1, 2]), kv=KV([['外键', f"{fkl[0][0]} 次 → {fkl[1][0]} 次"]], ['外键'])),
    step("两种方式发的 SQL 不同:select_related 是一条带 INNER JOIN 的 SELECT,作者的列跟书一起取回;prefetch_related 是先查主表,再用 WHERE … IN (id 列表) 查关联表,在 Python 里把它们接起来。", t=tl([l for l in R['sql'].splitlines() if l.strip()], cur=[1], mark=[3, 4]), kv=KV([['select_related', 'JOIN,1 条 SQL'], ['prefetch_related', '2 条 SQL,IN 列表']], ['prefetch_related'])),
    step(f"多对多:不优化 {mml[0][0]} 次查询、{mml[0][1]:.0f} ms;prefetch_related('tags') {mml[1][0]} 次、{mml[1][1]:.0f} ms。select_related 不能用于多对多:FieldError: Invalid field name(s) given in select_related: 'tags'. Choices are: author。", b=bars([['不优化(ms)', mml[0][1], f"{mml[0][1]:.0f}"], ['prefetch_related(ms)', mml[1][1], f"{mml[1][1]:.0f}"]], mml[0][1] * 1.1, mark=[0], done=[1]), kv=KV([['多对多', 'prefetch_related']], ['多对多'])),
    step(f"反向外键(一个作者的多本书):100 个作者各查一次 {rvl[0][0]} 次、{rvl[0][1]:.0f} ms;prefetch_related('books') {rvl[1][0]} 次、{rvl[1][1]:.0f} ms。Prefetch(queryset=…filter…, to_attr=…) 可以只预取满足条件的子集(仍是 2 次查询)。", b=bars([['不优化(ms)', rvl[0][1], f"{rvl[0][1]:.0f}"], ['prefetch_related(ms)', rvl[1][1], f"{rvl[1][1]:.0f}"]], rvl[0][1] * 1.1, mark=[0], done=[1]), kv=KV([['Prefetch 对象', '可带过滤和 to_attr']], ['Prefetch 对象'])),
    step("一个陷阱:在已经预取的属性上再写 a.books.filter(...) 会另外发查询——预取的缓存只服务 .all() 这种原样访问。实测 100 个作者各 filter().count() 一次,共 102 次查询(1 + 1 次预取 + 100 次)。", t=tl(R['reverse'].splitlines()[-1:], mark=[0]), kv=KV([['预取后再 filter', '不走缓存,又是 N 次']], ['预取后再 filter'])),
]
A = dict(
    n=28, series='django', tags='Django,ORM,select_related,prefetch_related,N+1,真实验证,动画演示',
    desc=f'在 2000 本书 / 100 个作者 / 20 个标签上实测:外键不优化 {fkl[0][0]} 次查询 {fkl[0][1]:.0f} ms,select_related {fkl[1][0]} 次 {fkl[1][1]:.0f} ms;多对多用 prefetch_related {mml[1][0]} 次;select_related 不能用于多对多;预取后再 filter 又会 N 次查询。',
    lead='select_related 和 prefetch_related 都能消灭 N+1,差别在哪?各自发出什么 SQL?什么时候只能用哪一个?这篇用同一份数据把两者的查询次数、耗时、SQL 都摆出来。',
    facts=[(f'{fkl[0][0]} → {fkl[1][0]}', '外键场景下的查询次数:不优化 → select_related'), (f'{mml[0][0]} → {mml[1][0]}', '多对多场景下的查询次数:不优化 → prefetch_related'), ('再 filter', '在已预取的属性上再 .filter() 会重新发查询,预取缓存只服务 .all()')],
    body=[
        sec('外键:两种方式', '', term('', blk('d28', 1)), '<p>耗时是 5 轮取最快的一次。两种方式都把 N+1 变成常数次查询,耗时接近;这里的数据量下差别很小,不代表在别的数据分布下也一样。</p>'),
        sec('多对多', '', term('', blk('d28', 2)), '<p>多对多(和反向外键)是「一对多」的关系,JOIN 会让主表的行重复,所以只能用 <code>prefetch_related</code>(分两步查再在 Python 里组装)。</p>'),
        sec('实际发出的 SQL', '', term('', blk('d28', 3)), '<p><code>select_related</code> 一条 JOIN;<code>prefetch_related</code> 一条 <code>IN (…)</code>。IN 列表的长度等于主表这一批的行数,行数很大时要分批(SQLite 有变量个数限制,本文没有测到边界)。</p>'),
        sec('反向外键与 Prefetch 对象', '', term('', blk('d28', 4)), '<p>用 <code>Prefetch(queryset=..., to_attr=...)</code> 预取带条件的子集;之后读 <code>to_attr</code> 指定的属性。在预取的关系上再写 <code>.filter()</code> 会重新查询,是 N+1 复发的常见原因。</p>'),
        sec('分步演示:两种预取', '', demo('select_related vs prefetch_related', [('b', 'bars', '耗时'), ('t', 'term', 'SQL'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;数据:2000 本书、100 个作者、20 个标签、每本书 3 个标签;耗时为 5 轮中最快的一轮', '没有验证:PostgreSQL / MySQL 上的耗时与计划、大结果集下 IN 列表的分批、嵌套预取(a__b__c)、select_related 多层 JOIN 的成本、prefetch_related_objects()'],
)
