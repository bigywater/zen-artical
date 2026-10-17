from lib import *
S = SS('f156')
steps = [
    step("读取与预置 session:with c.session_transaction() as s: s['user'] = 'preset'; s['cart'] = ['x'] 在不走登录接口的情况下写好 session,之后 GET /me 读到 user = preset、keys 是 [cart, user];再用 session_transaction 读取,拿到的就是服务端写进去的内容 {cart: ['x'], user: 'preset'}。", t=tl(S(1)), done=lidx(S(1), '预置之后', '再用 session_transaction'), kv=KV([['session_transaction()', '读写测试客户端的 session cookie']], ['session_transaction()'])),
    step("请求之后检查 session:with client: 保留上下文,连续两次 POST /cart/add 之后,在 with 里直接读 flask.session['cart'] 得到 ['apple', 'pear']——不需要再发一个请求去读。", t=tl(S(2)), done=lidx(S(2), 'with client'), kv=KV([['with client:', '请求之后仍能直接读 session']], ['with client:'])),
    step("flash 消息存在 session 的 _flashes 里:POST /notify 里 flash('saved!', 'success') 再重定向,follow_redirects 之后的页面读到 [['success', 'saved!']];再请求一次就是空的([])——get_flashed_messages 读一次就消费了。测试一个已经带 flash 的页面,可以用 session_transaction 预置 _flashes(这里预置 [('warning', 'preset flash')] 后页面读到 warning 那一条)。", t=tl(S(3)), done=lidx(S(3), '重定向后的页面', '预置 _flashes'), mark=lidx(S(3), '再请求一次'), kv=KV([['flash', '存在 session 的 _flashes 里'], ['读取', '消费一次就没了']], ['flash'])),
    step("Flask-Login:不走登录表单,直接在 session 里写 _user_id 就是「已登录」:未登录访问 /secret 是 401;session_transaction 里预置 _user_id = '1'(再加 _fresh = True)之后是 200 {who: '1'};预置一个 user_loader 找不到的 id(999)仍然是 401(user_loader 返回 None 时当作未登录)。测试需要「已登录」前提时,这比模拟表单登录简单也更快(第 72 篇看过这些 session 键)。", t=tl(S(4)), mark=lidx(S(4), '未登录访问', '不存在的用户'), done=lidx(S(4), '预置 _user_id=1'), kv=KV([['_user_id', '预置它就是已登录'], ['user_loader 返回 None', '仍当作未登录']], ['_user_id'])),
    step("登录之后 Set-Cookie 里的属性:session、Expires(permanent 的)、HttpOnly、Path。SESSION_COOKIE_* 的配置会体现在这里,所以测试里可以直接断言 cookie 属性(Secure 是否「生效」test client 不执行,见第 120 篇)。", t=tl(S(5)), done=lidx(S(5), 'Set-Cookie 属性'), kv=KV([['Set-Cookie 属性', '可以直接断言']], ['Set-Cookie 属性'])),
    step("测试 session 过期:PERMANENT_SESSION_LIFETIME = 60 秒;刚登录读到 user = ann;把 time.time() 拨后 120 秒之后,同一个 cookie 读到 None——itsdangerous 用签名里的时间戳加当前时间判断过期,所以改时钟(或用 freezegun 之类的库)就能测试过期,不必真的等。(这里是直接替换 time.time 做的,用完立刻还原。)", t=tl(S(6)), done=lidx(S(6), '刚登录'), mark=lidx(S(6), '往后拨'), kv=KV([['过期判断', '签名时间戳 + 当前时间'], ['测试办法', '改时钟,不用等']], ['测试办法'])),
]
A = mkartf('f156', 156, 'Flask,测试,session,flash,Flask-Login,真实验证,动画演示',
    '实测怎样测试 Flask 的 session:session_transaction 预置与读取、with client 保留上下文读 session、flash 消息存在 _flashes 里读一次就消费、直接预置 _user_id 来模拟 Flask-Login 登录、断言登录后的 Set-Cookie 属性、拨快时钟测试 permanent session 的过期。',
    '测试需要「已登录」的前提时,怎么不走登录表单就做到?flash 消息怎么测?session 过期怎么不等就测?这篇逐项运行并打印结果。',
    [('_user_id', '预置它就能让 Flask-Login 认为用户已登录'), ('_flashes', 'flash 消息在 session 里的键,读一次就清空'), ('拨快时钟', '不用真的等,就能测 permanent session 的过期')],
    [('预置 session', '<p>上一篇:<a href="flask-test-db-transaction.html">测试数据库事务</a>;下一篇:<a href="flask-test-file-upload.html">测试文件上传</a>。</p>'), ('请求之后读 session', None), ('测试 flash', None), ('模拟登录', None), ('cookie 属性', None), ('测试过期', None)],
    steps, [ENV_F + '。Flask-Login 0.6.3', '没有验证:服务端 session(Flask-Session)的测试方式、freezegun 库的用法、remember cookie 的测试、session 在多个客户端之间的隔离、CSRF token 在测试里的处理(第 73 篇)'], '测试 Session')
