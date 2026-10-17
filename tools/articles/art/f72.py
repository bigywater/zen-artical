from lib import *
S = SS('f72')
R = J('f72')
steps = [
    step("未登录访问被 login_required 保护的 /secret:返回 302,Location 是 /login?next=%2Fsecret(login_view 加上 next 参数);访问不受保护的 / 得到 hello anonymous;未登录时 current_user 的类型是 AnonymousUserMixin(is_authenticated 为 False,id 为 None)。", t=tl(S(1)), done=lidx(S(1), 'GET /secret', 'AnonymousUserMixin'), kv=KV([['未登录访问受保护页', '302 → /login?next=...'], ['current_user', 'AnonymousUserMixin']], ['未登录访问受保护页'])),
    step("POST /login?next=/secret 之后 302 回到 /secret。login_user 往 session 里写了 _fresh、_id(一长串哈希)、_user_id,另外还有登录前 flash 的提示;/secret 返回 secret for ann,current_user 的类型是 User。session cookie 用 base64 解码就能看到内容,不需要密钥(签名防篡改,不防查看)。", t=tl(S(2)), done=lidx(S(2), 'POST /login', '登录后 GET /secret'), mark=lidx(S(2), '明文'), kv=KV([['session 里的键', '_fresh / _id / _user_id'], ['cookie 内容', '签名但不加密']], ['cookie 内容'])),
    step("user_loader:3 个访问 current_user 的请求,user_loader 被调用了 3 次(每个请求一次,从 session 里的用户 id 重新加载);未登录的请求 session 里没有 id,调用 0 次。", t=tl(S(3)), done=lidx(S(3), '3 个请求'), mark=lidx(S(3), '0 次'), kv=KV([['已登录的请求', '每个请求调用一次 user_loader'], ['未登录的请求', '0 次']], ['已登录的请求'])),
    step("remember=True:除了 session 还会设置 remember_token cookie,值形如「用户 id|哈希」,属性 Expires、HttpOnly、Path=/。把 session cookie 删掉、只剩 remember_token,访问 /whoami 仍然是已登录;但此时 session 里 _fresh 是 False,访问 fresh_login_required 的页面返回 401。", t=tl(S(4)), done=lidx(S(4), 'Set-Cookie', '恢复之后', '删掉'), mark=lidx(S(4), '401'), kv=KV([['remember_token', '用户 id|哈希,HttpOnly'], ['丢了 session', '靠 remember 恢复登录'], ['恢复后的会话', '_fresh = False']], ['恢复后的会话'])),
    step("logout_user 之后响应里 remember_token 与 session 两个 cookie 都被清空(Set-Cookie: remember_token= 与 session=),再访问 whoami 是未登录。", t=tl(S(5)), done=lidx(S(5), 'Set-Cookie', '登出后'), kv=KV([['logout_user', '清 session 与 remember cookie']], ['logout_user'])),
    step("session_protection:默认的 basic 下,同一个 session 换了 User-Agent,whoami 仍是已登录(True);设成 strong 后,同样的操作 whoami 变成未登录(False)——会话被直接清空。", t=tl(S(6)), done=lidx(S(6), 'basic'), mark=lidx(S(6), 'strong'), kv=KV([['basic', '换 User-Agent 仍登录'], ['strong', '换 User-Agent 被登出']], ['strong'])),
    step("API 接口不想要重定向:自定义 unauthorized_handler,未登录时返回 401 与 JSON {'error': 'login required'}。", t=tl(S(7)), done=lidx(S(7), '401'), kv=KV([['unauthorized_handler', '401 + JSON']], ['unauthorized_handler'])),
]
A = mkartf('f72', 72, 'Flask,Flask-Login,登录,session,remember me,真实验证,动画演示',
    '实测 Flask-Login 的登录流程:未登录重定向与 next 参数、AnonymousUserMixin、login_user 写进 session 的键、user_loader 每个请求调用一次、remember_token cookie 与 fresh 标记、登出清 cookie、session_protection 的 basic 与 strong、API 的 401 处理。',
    'Flask-Login 把「已登录」存在哪里?每个请求做了什么?remember me 是怎么在 session 丢失后恢复登录的?这篇用 test_client 把整条流程的 cookie 与 session 内容打印出来。',
    [('3 次', '3 个访问 current_user 的请求里 user_loader 被调用的次数'), ('_fresh', 'remember 恢复的会话是 False,fresh_login_required 页面返回 401'), ('strong', 'session_protection 设成 strong 后换 User-Agent 就被登出')],
    [('未登录与 next', '<p>上一篇:<a href="flask-extension-init-timing.html">Extension 初始化时机</a>;下一篇:<a href="flask-flask-wtf-validation.html">Flask-WTF 表单验证</a>。</p>'), ('login_user 写了什么', None), ('user_loader', None), ('remember me', None), ('登出', None), ('session_protection', '<p>这里只验证了「换 User-Agent 后是否仍登录」这一个变化;basic 下的 fresh 标记变化没有单独验证。</p>'), ('API 的未授权处理', None)],
    steps, [ENV_F + '。Flask-Login 0.6.3', '没有验证:basic 模式下标识变化后 _fresh 的具体变化、换 IP 触发 session_protection、Flask-Login 与 Flask-Session 等服务端 session 搭配、remember cookie 的 duration 配置项与 refresh 机制、多设备同时登录'], 'Flask-Login 登录流程')
