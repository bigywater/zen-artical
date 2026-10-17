from lib import *
R = J('d27')
steps = [
    step("构造 QuerySet 并链式调用 filter / order_by / exclude:0 次查询——它们只是在拼装查询条件。第一次迭代(list(qs))才发 1 次查询;之后 list(qs)、len(qs)、qs[0]、qs.count()、qs.exists() 全是 0 次(直接用已缓存的结果)。", t=tl(R['basic'].splitlines(), cur=[0, 2, 3, 4, 5, 6], mark=[1]), kv=KV([['构造', '0 次查询'], ['第一次迭代', '1 次,并缓存']], ['第一次迭代'])),
    step("没有缓存时各操作发出的 SQL:[0] → LIMIT 1;[5:10] → LIMIT 5 OFFSET 5;count() → SELECT COUNT(*);exists() → SELECT 1 … LIMIT 1;而 bool(qs)、len(qs) 会把所有行都取回来(没有 LIMIT);repr(qs) 会 LIMIT 21(所以在 shell 里回车 = 一次查询)。", t=tl([l for l in R['sql'].splitlines() if l.strip() and not l.startswith('==')], cur=[0, 1, 2, 3], mark=[4, 5]), kv=KV([['bool / len', '取回全部行'], ['repr', 'LIMIT 21']], ['bool / len'])),
    step("exists() 不填充缓存:先 qs.exists()(1 次)再 list(qs)(又 1 次);之后 exists() 用缓存(0 次)。bool(qs) 会填充缓存,之后 count() 不再查询。iterator() 遍历一遍(1 次)后再 list(qs) 还要再查一次——iterator() 不填充缓存。", t=tl(R['mix'].splitlines(), cur=[0, 1, 2, 3], mark=[6]), kv=KV([['exists()', '不填充缓存'], ['iterator()', '不填充缓存']], ['iterator()'])),
    step("缓存的代价:同一个 QuerySet 对象迭代过之后,数据库又变了(新建了一条),再迭代同一个对象仍是旧结果 [];要看到新数据,用 qs.all() 或再链一次 .filter() 生成新的 QuerySet。", t=tl(R['stale'].splitlines(), cur=[0], mark=[1], done=[2, 3]), kv=KV([['同一个 QuerySet', '结果被缓存,看不到新数据']], ['同一个 QuerySet'])),
]
A = dict(
    n=27, series='django', tags='Django,QuerySet,惰性,缓存,真实验证,动画演示',
    desc='用查询捕获数出 QuerySet 每种操作发了几次查询:链式调用 0 次、第一次迭代 1 次并缓存;count / exists / [0] / bool / len / repr 各自的 SQL(repr 是 LIMIT 21);exists() 与 iterator() 不填充缓存;缓存会让同一个 QuerySet 看不到之后的新数据。',
    lead='QuerySet 到底什么时候查库?第二次迭代还查吗?count() 和 len() 有什么区别?这篇用 CaptureQueriesContext 把每个操作发了几次查询、发的是什么 SQL 都数出来。',
    facts=[('0 次', '构造与链式调用 filter / order_by / exclude 不发任何查询'), ('LIMIT 21', 'repr(qs)(比如在 shell 里回车)会发一次 LIMIT 21 的查询'), ('缓存', '迭代后结果缓存在 QuerySet 里;exists() 与 iterator() 不填充它')],
    body=[
        sec('什么时候真的查库', '', term('', blk('d27', 1)), '<p>惰性:只有「求值」才查询(迭代、切片带步长、<code>list()</code>、<code>len()</code>、<code>bool()</code> 等)。求值一次后结果缓存在 <code>_result_cache</code>,同一个对象的后续访问不再查库。</p>'),
        sec('没缓存时每个操作的 SQL', '', term('', blk('d27', 2)), '<p>判断「有没有」用 <code>exists()</code>(<code>LIMIT 1</code>),不要 <code>bool(qs)</code> 或 <code>len(qs)</code>(会取回全部行)。只要个数用 <code>count()</code>。</p>'),
        sec('哪些操作会填充缓存', '', term('', blk('d27', 3)), '<p>一个常见的写法 <code>if qs.exists(): for x in qs:</code> 发两次查询;如果本来就要迭代,直接 <code>list(qs)</code> 再判断更省。</p>'),
        sec('缓存的副作用', '', term('', blk('d27', 4)), '<p>长期持有的 QuerySet(模块级变量)会一直返回第一次的结果,这是个常见 bug。要「重新查」就要生成新的 QuerySet。</p>'),
        sec('分步演示:何时查库', '', demo('QuerySet 惰性与缓存', [('t', 'term', '查询次数 / SQL'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;计数用 CaptureQueriesContext', '没有验证:切片带步长(qs[::2])的求值、prefetch 结果的缓存、异步 QuerySet(aiterator)、__len__ / __bool__ 在其它数据库上的 SQL 差异'],
)
