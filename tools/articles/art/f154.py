from lib import *
S = SS('f154')
R = J('f154'); cs = R['cost']; k = list(cs); fn_, ss_ = cs[k[0]], cs[k[1]]
steps = [
    step("函数级 fixture(默认作用域):conftest.py 里 app fixture 调用 create_app(),建表后 yield;client fixture 依赖它。pytest -v 的结果:3 个测试全部通过(test_add_one、test_starts_empty、test_config_override)——test_starts_empty 看到的是空表,因为每个测试各有一个全新的应用与内存数据库,test_add_one 留下的数据不会影响它。", t=tl(S(1)), done=lidx(S(1), 'PASSED', 'passed'), kv=KV([['函数级 app', '每个测试一份全新的应用与数据库'], ['结果', '3 passed']], ['函数级 app'])),
    step("--setup-show 显示 fixture 的创建与清理顺序:SETUP F app(F 表示函数级),然后 SETUP F client(依赖 app),测试执行,TEARDOWN F client,再 TEARDOWN F app——依赖的 fixture 先创建、后清理。yield 之后的代码就是清理,出错也会执行。", t=tl(S(2)), done=lidx(S(2), 'SETUP', 'TEARDOWN'), kv=KV([['创建顺序', '被依赖的先建'], ['清理顺序', '依赖别人的先清理']], ['创建顺序'])),
    step("把 app 改成 scope=\"session\"(整个测试会话共用一个应用与内存数据库):按文件里的顺序运行,test_add_one 先加了一行,test_starts_empty 看到 count = 1,断言「assert 1 == 0」失败——测试之间互相污染。共享的状态(数据库、模块级缓存)不会因为换了测试而重置。", t=tl(S(3)), mark=lidx(S(3), 'FAILED', 'assert'), kv=KV([['session 级 app + 共享数据库', '前一个测试的数据留给后一个'], ['后果', 'test_starts_empty 失败']], ['session 级 app + 共享数据库'])),
    step("同样的 session 级 fixture,换成倒序运行(先 test_starts_empty 再 test_add_one):两个都通过。也就是这个污染是顺序依赖的——正序失败、倒序通过。只在某种顺序下才暴露的测试问题最难排查;可以用随机顺序插件(如 pytest-randomly)跑一遍来发现(本篇没有使用)。", t=tl(S(4)), done=lidx(S(4), 'PASSED', 'passed'), kv=KV([['顺序依赖', '正序失败,倒序通过']], ['顺序依赖'])),
    step(f"创建应用的代价(各跑 200 个简单测试,含启动 pytest):函数级每个测试新建应用 {fn_[0]},总耗时 {fn_[1] / 1000:.2f} 秒;会话级一个应用、每个测试之后清空数据 {ss_[0]},总耗时 {ss_[1] / 1000:.2f} 秒。每个测试新建一次应用大约多花 {(fn_[1] - ss_[1]) / 200:.1f} ms;应用小、用内存数据库时,函数级的隔离代价很小,不值得为省这点时间去共享状态。", b=bars([['函数级 app', fn_[1] / 1000, f'{fn_[1] / 1000:.2f} s'], ['会话级 + 清空', ss_[1] / 1000, f'{ss_[1] / 1000:.2f} s']], fn_[1] / 1000, mark=[0], done=[1]), t=tl(S(5)), done=lidx(S(5), '函数级 app', '会话级 app'), kv=KV([['函数级 app', f'{fn_[1] / 1000:.2f} 秒 / 200 个测试'], ['会话级 + 清空', f'{ss_[1] / 1000:.2f} 秒']], ['函数级 app'])),
]
A = mkartf('f154', 154, 'Flask,pytest,fixture,应用工厂,测试隔离,真实验证,动画演示',
    f'用真实的 pytest 实测 Flask 测试里的 fixture 与应用工厂:函数级 app 让每个测试一份全新的应用与内存数据库、--setup-show 的创建与清理顺序、session 级共用应用时 test_starts_empty 因前一个测试留下的数据失败而倒序却通过、200 个测试里函数级 {fn_[1] / 1000:.2f} 秒对会话级 {ss_[1] / 1000:.2f} 秒。',
    'Flask 的测试该怎么组织 fixture?为什么要用应用工厂?共享一个应用会出什么问题?每个测试新建应用慢不慢?这篇用真实的 pytest 把每种写法的结果跑出来。',
    [('3 passed', '函数级 fixture 下三个测试的结果,互不影响'), ('assert 1 == 0', 'session 级应用共享数据库时,test_starts_empty 看到上一个测试留下的数据'), (f'约 {(fn_[1] - ss_[1]) / 200:.1f} ms', '每个测试新建一个应用与数据库多花的时间')],
    [('函数级 fixture', '<p>上一篇:<a href="flask-test-client-vs-real-http.html">test_client() 与真实 HTTP 请求差异</a>;下一篇:<a href="flask-test-db-transaction.html">测试数据库事务</a>。</p>'), ('fixture 的顺序', None), ('共享应用的污染', None), ('倒序运行', None), ('创建应用的代价', None)],
    steps, [ENV_F + '。pytest 9.1.1、SQLite 内存库', '没有验证:pytest-randomly 等随机顺序插件、pytest-xdist 并行运行时的隔离、使用文件型 SQLite 或 PostgreSQL 时的清理方式(见第 155 篇)、autouse fixture 与 fixture 参数化'], 'Fixture 与测试应用工厂')
