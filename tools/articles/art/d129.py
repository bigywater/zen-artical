from lib import *
R = J('d129'); st = R['static']
def S(k): return [l for l in out('d129').split('== ')[k].splitlines()[1:] if l.strip()]
s1 = S(1); s4 = S(4)
steps = [
    step("同一个不存在的路径与同一个抛异常的视图:DEBUG=True 时 404 页面 2674 字节(Page not found at /nope/,列出 URL 模式),500 页面 51454 字节,标题 RuntimeError at /boom/,包含异常文本,也包含局部变量 card_number 的值;DEBUG=False 时 404 只有 179 字节(Not Found),500 只有 145 字节(Server Error (500)),没有异常文本和变量。", t=tl(s1), done=[3, 4, 5], mark=[1, 2], b=bars([['500 页面 DEBUG=True', 51454, '51454 字节'], ['500 页面 DEBUG=False', 145, '145 字节']], 52000, mark=[0], done=[1]), kv=KV([['DEBUG=True', '异常、变量、URL 模式都展示'], ['DEBUG=False', '只有通用页面']], ['DEBUG=True'])),
    step("@sensitive_variables('card_number') 在 DEBUG=True 时没有起作用:页面里照样有 card_number 的值(True);它只在 DEBUG=False 的错误报告里才生效。DEBUG=True 的页面里有 Settings 表,SECRET_KEY 这个名字在,但密钥原文没有(显示 ********************);ALLOWED_HOSTS 的值、数据库文件路径都在页面里。", t=tl(S(2)), mark=[0], kv=KV([['设置页', 'SECRET_KEY 被脱敏,其余设置可见'], ['sensitive_variables', 'DEBUG=True 时不生效']], ['sensitive_variables'])),
    step("DEBUG=True 时每条 SQL 都记进 connection.queries:视图里做 50 次查询后 len 是 50;DEBUG=False 时是 0。", t=tl(S(3)), b=bars([['DEBUG=True', 50, '50'], ['DEBUG=False', 0, '0']], 55, done=[0]), kv=KV([['connection.queries', 'DEBUG=True 才记录']], ['connection.queries'])),
    step("DEBUG=False 时出错会给 ADMINS 发邮件:DEBUG=True 邮件数 0;DEBUG=False 每次 500 发 1 封,主题「[Django] ERROR (EXTERNAL IP): Internal Server Error…」。本实验里两封邮件的文本正文都没有 card_number 的值(默认的邮件正文是 traceback 文本;包含局部变量的 HTML 版本没有测)。", t=tl(s4), done=[2, 3], kv=KV([['DEBUG=False', '500 → 邮件给 ADMINS']], ['DEBUG=False'])),
    step(f"runserver 与静态文件:DEBUG=True 时 /static/hello.txt → {st['DEBUG=True']};DEBUG=False → {st['DEBUG=False']}(runserver 不再提供静态文件);DEBUG=False 加 --insecure → {st['DEBUG=False + --insecure']}。manage.py check --deploy 对 DEBUG=True 给出 security.W018「You should not have DEBUG set to True in deployment.」。", t=tl(S(5) + S(6)), mark=[1], done=[0, 2], kv=KV([['DEBUG=False', 'runserver 不提供静态文件'], ['check --deploy', 'W018']], ['DEBUG=False'])),
]
A = dict(
    n=129, series='django', tags='Django,安全,DEBUG,错误页面,真实验证,动画演示',
    desc=f'DEBUG=False 的实际差别:500 页面从 51454 字节(含异常、局部变量、设置)变成 145 字节;connection.queries 50 → 0;500 会邮件通知 ADMINS;runserver 不再提供静态文件({st["DEBUG=True"]} → {st["DEBUG=False"]});@sensitive_variables 在 DEBUG=True 时不生效。',
    lead='「生产环境一定要关 DEBUG」是常识,但关掉之后具体少了什么、多了什么?这篇把同一个项目在 DEBUG=True 和 False 下的 404 / 500 页面、SQL 记录、错误邮件和 runserver 的静态文件行为逐项对比。',
    facts=[('51454 → 145 字节', '同一个 500 错误:DEBUG=True 的技术页面 vs DEBUG=False 的通用页面'), ('card_number', 'DEBUG=True 的 500 页面会展示局部变量,@sensitive_variables 此时也不起作用'), ('邮件', 'DEBUG=False 时 500 给 ADMINS 发邮件,DEBUG=True 不发')],
    body=[
        sec('404 / 500 页面', '', term('', blk('d129', 1)), '<p>DEBUG=True 的技术页面对开发很有用,但它会把源码片段、局部变量、请求信息都展示出来,对外暴露就是信息泄漏。</p>'),
        sec('设置页的脱敏', '', term('', blk('d129', 2)), '<p>Django 会把名字里有 KEY、SECRET、PASSWORD 等字样的设置脱敏,但其它设置(主机列表、路径)照样显示;局部变量更不会自动脱敏,要在 <code>DEBUG=False</code> 的错误报告里用 <code>@sensitive_variables</code> 才生效。</p>'),
        sec('SQL 记录', '', term('', blk('d129', 3)), '<p>DEBUG=True 时每条 SQL 都留在内存里的 <code>connection.queries</code>,长时间运行的进程里会一直增长(本文只量了条数,没有量内存)。</p>'),
        sec('错误邮件', '', term('', blk('d129', 4))),
        sec('静态文件与 check --deploy', '', term('', blk('d129', 5) + '\n' + blk('d129', 6)), '<p>DEBUG=False 后 <code>runserver</code> 不再提供静态文件,生产环境本来就该由 nginx / WhiteNoise / CDN 提供(第 132 篇)。</p>'),
        sec('分步演示', '', demo('DEBUG=False 的影响', [('t', 'term', '输出'), ('b', 'bars', '数字'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;Client(raise_request_exception=False);邮件用 locmem 后端 + setup_test_environment;runserver 用 --noreload 在本机 9543 端口', '没有验证:自定义 404.html / 500.html 模板、HTML 版错误邮件(AdminEmailHandler 的 include_html)、Sentry 等第三方错误追踪(第 135 篇)、DEBUG=True 时 queries_log 的内存增长量、DEBUG 对模板缓存的影响(第 82 篇已测)'],
)
