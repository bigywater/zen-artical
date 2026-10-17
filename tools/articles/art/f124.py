from lib import *
S = SS('f124')
R = J('f124')
steps = [
    step("名字里带单引号的正常用户(O'Brien):用 f-string 把名字拼进 SQL,PostgreSQL 直接报语法错误「syntax error at or near \"Brien\"」——拼接把数据当成了 SQL 文本的一部分,连正常输入都会出错。用 text() 加绑定参数 :n,查询成功;发给数据库的是语句 where name = %(n)s 与参数 {n: \"O'Brien\"},两者分开传递。ORM 表达式 User.name == name 同样生成 %(name_1)s 占位符加独立的参数。引号在这里就是普通字符,不需要自己转义。", t=tl(S(1)), mark=lidx(S(1), 'f-string'), done=lidx(S(1), '绑定参数', 'ORM 表达式'), kv=KV([['拼接', '数据混进 SQL 文本'], ['绑定参数', '语句与值分开传'], ['ORM 表达式', '同样自动绑定']], ['绑定参数'])),
    step("参数只能代替「值」,不能代替表名、列名、排序方向:把列名当绑定参数写 order by :c,得到的只是按常量字符串排序,结果并没有按 name 列排序;需要动态排序时用白名单把用户传来的列名映射到真正的列对象(这里 name 与 id 允许,password 被拒绝)。白名单之外的名字永远不要拼进 SQL。", t=tl(S(2)), done=lidx(S(2), "'name' asc", "'id' desc"), mark=lidx(S(2), 'password', 'order by :c'), kv=KV([['绑定参数', '只能代替值'], ['列名 / 排序', '白名单映射到列对象']], ['列名 / 排序'])),
    step("LIKE 里的 % 与 _ 也是数据:contains(term, autoescape=True) 发出的语句是 LIKE '%' || %(name_1)s || '%' ESCAPE '/',参数被转成 50/%/_off,通配符不再起作用;不转义的 like(f'%{term}%') 里的 % 与 _ 会被当作通配符(这份只有一行数据,两种写法的结果恰好相同,差别在发出的语句与参数里)。IN 列表用 in_([...]),每个元素各有一个占位符。", t=tl(S(3)), done=lidx(S(3), 'contains', 'in_'), mark=lidx(S(3), "like('%"), kv=KV([['autoescape=True', '转义 % _ 与转义符'], ['in_()', '每个元素一个占位符']], ['autoescape=True'])),
    step("看 PostgreSQL 服务端日志(log_statement=all):text() 带 :n 的查询在服务端以 execute <unnamed>: select id from \"user\" where name = $1 的形式执行——psycopg 3 用的是服务端绑定,值不经过 SQL 文本。日志里另一行 STATEMENT 是第一节那条拼接出来的、出错的语句。", t=tl(S(4)), done=lidx(S(4), 'execute <unnamed>'), mark=lidx(S(4), 'STATEMENT'), kv=KV([['psycopg 3', '服务端绑定 $1'], ['拼接', '值成为 SQL 文本的一部分']], ['psycopg 3'])),
]
A = mkartf('f124', 124, 'Flask,SQL注入,参数化查询,SQLAlchemy,真实验证,动画演示',
    '从防御角度实测参数化查询:带单引号的正常名字在字符串拼接下语法错误而绑定参数正常;ORM 表达式自动生成占位符;列名与排序用白名单;LIKE 的通配符用 autoescape;PostgreSQL 服务端日志里语句以 $1 占位符执行。',
    '为什么要用参数化查询?ORM 是不是自动安全?哪些位置参数化帮不上忙?这篇不演示攻击,只用一个名字里带单引号的正常用户,看拼接与绑定在真实的 PostgreSQL 里各自发生了什么。',
    [('$1', 'PostgreSQL 日志里 text() 绑定参数的执行形式(服务端绑定)'), ('白名单', '表名、列名、排序方向这些不能参数化的位置的处理方式'), ('autoescape', 'LIKE 里转义 % 与 _ 的选项')],
    [('拼接与绑定', '<p>上一篇:<a href="flask-xss-protection.html">XSS 防护</a>;下一篇:<a href="flask-path-traversal-download.html">路径穿越与文件下载</a>。</p>'), ('不能参数化的位置', None), ('LIKE 与 IN', None), ('服务端日志', '<p>本篇只做防御向的验证:没有构造任何利用语句。</p>')],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、psycopg 3.3.6、自己起的 PostgreSQL(非默认端口,临时打开了 log_statement)', '没有验证:存储过程与动态 SQL(EXECUTE format)里的拼接、ORM 的 text() 片段里混入变量、JSON 路径与 order_by(text(...)) 这类容易被拼接的 API、数据库账号最小权限的缓解作用、WAF'], 'SQL 参数化查询')
