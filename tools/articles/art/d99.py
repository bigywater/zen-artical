from lib import *
R = J('d99')
steps = [
    step("在 lab/tests.py 里写 6 个测试:assertNumQueries(1) 的精确断言、故意写错的 N+1 断言、select_related 修复版、CaptureQueriesContext 的上界断言、TestCase 与 TransactionTestCase 里 atomic 的查询数。运行 manage.py test lab -v 2:5 个 ok,1 个 FAIL(那个故意写错的)。", t=tl(R['summary']), mark=[2], done=[0, 1, 3, 4, 5], kv=KV([['结果', '5 ok / 1 FAIL']], ['结果'])),
    step("assertNumQueries 失败时的报错很有用:AssertionError: 6 != 2 : 6 queries executed, 2 expected,并且把每一条被执行的 SQL 列出来——第 1 条取文章,第 2~6 条是同样的「SELECT lab_author … WHERE id = 1」五次:一眼就看出是 N+1。", t=tl([l.strip() for l in R['fail_msg'][7:19]], mark=[0, 3, 4, 5, 6, 7], cur=[2]), kv=KV([['失败信息', '列出每条 SQL,直接看出 N+1']], ['失败信息'])),
    step("同一段 atomic 代码在两种测试基类下查询数相同(都是 3 条),内容不同:TestCase 已包了一层事务,atomic 变成 SAVEPOINT + INSERT + RELEASE SAVEPOINT;TransactionTestCase 没有外层事务,atomic 是 BEGIN + INSERT + COMMIT。断言里的数字要按你用的基类算,不能拿别的环境的数字照抄。", t=tl(R['tx'].splitlines()), kv=KV([['TestCase', 'SAVEPOINT'], ['TransactionTestCase', 'BEGIN / COMMIT']], ['TestCase'])),
    step("实践:①给每个重要视图写 assertNumQueries(修复前先让它失败,证明测试有效);②想要上界而不是精确值,用 CaptureQueriesContext + assertLessEqual,并把 captured_queries 放进失败消息;③setUpTestData 里创建的数据不算进被测代码块的查询数;④断言数字随迁移、认证、session 中间件变化,要在真实请求(Client)上量。", kv=KV([['写法', 'assertNumQueries 精确;CaptureQueriesContext 上界']], ['写法'])),
]
A = dict(
    n=99, series='django', tags='Django,测试,assertNumQueries,查询次数,真实验证,动画演示',
    desc='用真实的 manage.py test 演示查询次数测试:assertNumQueries 精确断言与 N+1 失败时列出每条 SQL 的报错;CaptureQueriesContext 上界断言;TestCase 里 atomic 是 SAVEPOINT、TransactionTestCase 里是 BEGIN / COMMIT。',
    lead='怎么让「不许出现 N+1」变成一条自动化测试?assertNumQueries 失败时能看到什么?这篇写 6 个真实测试并运行,把通过与失败的输出都贴出来。',
    facts=[('6 != 2', 'assertNumQueries 失败信息:6 queries executed, 2 expected,并列出每条 SQL'), ('SAVEPOINT', 'TestCase 里 atomic 变成 SAVEPOINT,TransactionTestCase 里是 BEGIN / COMMIT'), ('上界', 'CaptureQueriesContext + assertLessEqual 适合只想限制上限的场景')],
    body=[
        sec('运行结果', '', term('', blk('d99', 1)), '<p>测试文件里五个通过、一个故意写错(<code>assertNumQueries(2)</code> 而实际是 6 次)。</p>'),
        sec('失败信息', '', term('', blk('d99', 2)), '<p>这是 <code>assertNumQueries</code> 最有价值的一点:失败信息就是 N+1 的证据。</p>'),
        sec('TestCase 与 TransactionTestCase', '', term('', blk('d99', 3)), '<p>因为 <code>TestCase</code> 把每个测试包在事务里,涉及 <code>on_commit</code>(第 45 篇)和 <code>select_for_update</code>(第 46 篇)的测试要注意选对基类。</p>'),
        sec('分步演示:测试里的查询数', '', demo('查询次数测试', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;测试由 manage.py test 真实运行,输出来自它', '没有验证:pytest-django 的 django_assert_num_queries、并行测试(--parallel)下的查询计数、异步测试中的计数、测试数据库为 PostgreSQL 时的差异'],
)
