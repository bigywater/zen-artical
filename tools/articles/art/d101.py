from lib import *
R = J('d101'); ov = R['overhead']; a, b = ov['没有工具栏'], ov['有工具栏']
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("被测页面:100 篇文章、10 个作者,视图里循环访问 p.author.name(经典 N+1)。请求这个页面,响应 HTML 里被注入了工具栏(djDebug);工具栏的数据不在响应里,而是按 request_id 存在服务端,前端再用这个 id 去取各个面板。", t=tl(L('panel')[:2]), kv=KV([['工具栏注入', '响应里有 djDebug'], ['面板内容', '按 request_id 在服务端取']], ['面板内容'])),
    step("SQL 面板摘要:101 次查询,其中 100 次 similar(同一条 SQL 模板)、100 次 duplicate(参数也相同),提示行是「100 similar queries. Duplicated 10 times.」——10 个作者各被查了 10 次。面板里还带调用栈,能定位到 views.py 的那一行。", t=tl(L('panel')[2:]), mark=[0, 1], kv=KV([['查询数', '101'], ['similar / duplicate', '100 / 100']], ['查询数'])),
    step("同一个页面改成 select_related('author') 后:面板摘要只有 1 次查询。", t=tl(L('fixed')), done=[0], kv=KV([['修复后查询数', '1']], ['修复后查询数'])),
    step("另一种问题:同一条 SQL 被完全一样地执行 3 次(比如同一个 Model.objects.get 在视图、模板、context processor 里各调一次)。面板摘要 3 次查询、3 次 similar、3 次 duplicate,提示「3 similar queries. Duplicated 3 times.」。", t=tl(L('dup')), mark=[0], kv=KV([['重复查询', '3 similar / 3 duplicate']], ['重复查询'])),
    step(f"代价:同一个 101 次查询的页面,没有工具栏时请求中位数 {a} ms,有工具栏时 {b} ms(30 次取中位数,Client 直调,DEBUG=True)——开销的来源我没有拆开测量。", b=bars([['没有工具栏', a, f'{a} ms'], ['有工具栏', b, f'{b} ms']], b * 1.1, mark=[1], done=[0]), kv=KV([['开销', f'≈ {b / a:.1f} 倍(这个页面)']], ['开销'])),
]
A = dict(
    n=101, series='django', tags='Django,Debug Toolbar,慢查询,N+1,真实验证,动画演示',
    desc=f'用 Django Debug Toolbar 的 SQL 面板看 N+1 页面:101 次查询、100 次 similar / 100 次 duplicate,并带调用栈;select_related 后只剩 1 次;同一页面有无工具栏的请求耗时 {a} ms → {b} ms。',
    lead='Debug Toolbar 是发现 N+1 和重复查询最快的办法:把它装在开发环境,页面右边的 SQL 面板会列出每条查询、耗时、调用栈,并标出相似与重复的查询。这篇用 django.test.Client 请求一个真实带工具栏的页面,取出 SQL 面板的内容,再量一下它自己的开销。',
    facts=[('101 → 1', 'N+1 页面的查询数:未优化 → select_related'), ('100 similar', '面板把同一模板的查询归为 similar,参数也相同的归为 duplicate'), (f'{a} → {b} ms', '同一页面有工具栏后的请求耗时(30 次中位数)')],
    body=[
        sec('工具栏的数据怎么来的', '', term('', blk('d101', 1)), '<p>工具栏中间件在响应里注入一段脚本和 <code>data-request-id</code>,面板本身的内容存在服务端,浏览器按 request_id 再发请求(这里请求 <code>/__debug__/render_panel/</code> 取 SQL 面板)。实验里设置了 <code>INTERNAL_IPS = ["127.0.0.1"]</code> 和 <code>DEBUG = True</code>;不满足这两个条件时的表现本文没有测。</p>'),
        sec('修复之后', '', term('', blk('d101', 2)), '<p>同样的页面用 <code>select_related</code> 后只有一次查询。</p>'),
        sec('重复查询', '', term('', blk('d101', 3)), '<p>N+1 是「相似」的一类;还有一类是完全相同的查询被重复执行。面板都会标出来,并给出 Duplicated 的次数。</p>'),
        sec('工具栏自己的开销', '', term('', blk('d101', 4)), '<p>它要记录每条查询、抓调用栈,所以请求会明显变慢。对比耗时应当在关掉工具栏的情况下量,不要拿带工具栏的数字当性能结论。</p>'),
        sec('分步演示:从面板读出问题', '', demo('Debug Toolbar 的 SQL 面板', [('t', 'term', '面板内容'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;django-debug-toolbar 由 pip 装入(版本以 pip 安装时的最新版为准);面板内容由 django.test.Client 直接请求 render_panel 端点取得并去掉 HTML 标签', '没有验证:浏览器里工具栏的实际界面、EXPLAIN 按钮、Profiling 面板、生产环境远程调试、其它数据库上的 EXPLAIN 输出、异步视图下的工具栏行为'],
)
