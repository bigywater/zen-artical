from lib import *
import re
R = J('d49')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
tm = {l.split(':')[0].strip(): float(re.search(r'([\d.]+) ms', l).group(1)) for l in L('time')}
ks = list(tm)
steps = [
    step("Paginator.page(3) 发两条 SQL:先 SELECT COUNT(*) FROM lab_item(算总页数),再 SELECT … ORDER BY id LIMIT 25 OFFSET 50。同一个 Paginator 上再取第 4 页,COUNT 不再重复(p.count 是缓存的);100 万行、每页 25 条共 40000 页。", t=tl(L('sql')), kv=KV([['COUNT', '每个 Paginator 一次'], ['总页数', '40000']], ['COUNT'])),
    step(f"100 万行的耗时(PostgreSQL,取最快的一次):SELECT COUNT(*) {tm[ks[0]]:.1f} ms;第 1 页 {tm[ks[1]]:.2f} ms;第 20000 页(OFFSET 499975){tm[ks[2]]:.1f} ms;第 40000 页(OFFSET 999975){tm[ks[3]]:.1f} ms。Paginator.page(1) 整体 {tm[ks[4]]:.1f} ms——几乎全是 COUNT(*) 的时间。", b=bars([[k[:28], v, f"{v:.1f} ms"] for k, v in list(tm.items())[:5]], max(tm.values()) * 1.1, mark=[0, 3]), kv=KV([['第 1 页', f"整体 {tm[ks[4]]:.1f} ms,其中 COUNT 占 {tm[ks[0]]:.1f} ms"]], ['第 1 页'])),
    step(f"OFFSET 越大越慢:第 40000 页 Paginator 整体 {tm[ks[5]]:.1f} ms(数据库要先跳过前 100 万行)。用 keyset(WHERE created > 上一页最后一个值 ORDER BY created LIMIT 25)只要 {tm[ks[6]]:.2f} ms,与页码无关(代价:只能上一页/下一页,不能跳页)。带过滤条件的 COUNT 也要 {tm[ks[7]]:.1f} ms。", b=bars([['Paginator 第 40000 页(ms)', tm[ks[5]], f"{tm[ks[5]]:.1f}"], ['keyset(ms)', tm[ks[6]], f"{tm[ks[6]]:.2f}"]], tm[ks[5]] * 1.1, mark=[0], done=[1]), kv=KV([['OFFSET', '越深越慢'], ['keyset', '与深度无关']], ['keyset'])),
    step("三个细节:未排序的 QuerySet 分页会触发 UnorderedObjectListWarning(Pagination may yield inconsistent results with an unordered object_list);请求越界页 → EmptyPage: That page contains no results;子类里把 count 写死(比如从缓存读近似值)后,COUNT 查询数为 0。", t=tl(L('misc')), kv=KV([['排序', '分页必须有确定的排序'], ['自己提供 count', '可以省掉 COUNT']], ['自己提供 count'])),
]
A = dict(
    n=49, series='django', tags='Django,分页,Paginator,COUNT,PostgreSQL,真实验证,动画演示',
    desc=f'在 100 万行的 PostgreSQL 表上量 Django 分页:Paginator 先发 COUNT(*)({tm[ks[0]]:.1f} ms)再发 LIMIT/OFFSET;第 1 页 {tm[ks[1]]:.2f} ms,最后一页 {tm[ks[3]]:.1f} ms(OFFSET 越深越慢);keyset 只要 {tm[ks[6]]:.2f} ms;未排序会警告。',
    lead='Django 分页为什么每次都多一条 COUNT(*)?大表上翻到最后一页会慢多少?有什么替代?这篇在 100 万行的表上量每一部分。',
    facts=[(f'{tm[ks[0]]:.1f} ms', '100 万行 COUNT(*) 的耗时;第 1 页整体 %.1f ms 几乎都是它' % tm[ks[4]]), (f'{tm[ks[1]]:.2f} → {tm[ks[3]]:.1f} ms', '取第 1 页 → 第 40000 页的 SQL 耗时(OFFSET 越深越慢)'), (f'{tm[ks[6]]:.2f} ms', 'keyset 分页(WHERE created > … LIMIT 25)的耗时,与深度无关')],
    body=[
        sec('Paginator 发出的 SQL', '', term('', blk('d49', 1)), '<p><code>Paginator.count</code> 是 <code>cached_property</code>,每个 Paginator 对象只查一次。但每个请求通常新建一个 Paginator,所以每个请求都会 <code>COUNT(*)</code>。</p>'),
        sec('耗时', '', term('', blk('d49', 2)), '<p>PostgreSQL 的 <code>COUNT(*)</code> 需要扫描(索引或表)满足条件的所有行,行数越多越慢。<code>OFFSET</code> 需要先取出并丢弃前面的行。都是本机单次测量,数字只反映这台机器上这份数据的量级。</p>'),
        sec('替代与细节', '', term('', blk('d49', 3)), '<p>要「上一页 / 下一页」的场景用 keyset;需要页码时可以缓存 count、或提供近似值(子类化 <code>Paginator</code> 重写 <code>count</code>)。分页永远要 <code>order_by</code>,并且排序键要唯一(否则页与页之间可能重复或遗漏)。</p>'),
        sec('分步演示:分页的代价', '', demo('分页与 COUNT', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。PostgreSQL 16.15(本机临时实例,端口 9424),100 万行(id 主键、created 有索引),ANALYZE 之后;每项取 5 次最快', '没有验证:MySQL 的 COUNT 与 OFFSET 代价、近似计数(pg_class.reltuples)、并发写入下 keyset 与 OFFSET 的一致性差异、无限滚动的 cursor 实现细节'],
)
