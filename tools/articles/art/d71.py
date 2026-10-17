from lib import *
R = J('d71')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("request.user 是惰性的(SimpleLazyObject):匿名请求、已登录请求只要视图不碰 request.user,都是 0 次查询。已登录且访问 request.user 时才有 2 次查询:先 SELECT django_session 取会话,再 SELECT auth_user 取用户。没有 sessionid cookie 的匿名访问 request.user:0 次查询(没有会话可查)。", t=tl(L('lazy')[:9], cur=[0, 1, 2, 3], mark=[3]), kv=KV([['request.user', '惰性'], ['已登录一次访问', '2 次查询(session + user)']], ['已登录一次访问'])),
    step("authenticate():遍历后端,ModelBackend 对密码错误 → None,并发出 user_login_failed 信号(信号里的 credentials 中 username 保留,password 被替换成 ********************);密码对 → 返回用户,此刻不发信号(信号在 login() 时发);多余参数(foo='bar')ModelBackend 也接受;凭据不匹配(只有 token)→ None 且发 user_login_failed(token 的值同样被打码);is_active=False 的用户即使密码对也返回 None。", t=tl(L('auth')), kv=KV([['失败', 'user_login_failed'], ['不活跃', '直接拒绝']], ['失败'])),
    step("登录后 session 里只存三样:_auth_user_id(用户 id,字符串)、_auth_user_backend(后端路径)、_auth_user_hash(64 位,从密码哈希派生)。用户对象本身不存进 session——每个请求用 id 重新取用户。", t=tl(L('session')), kv=KV([['session 里的认证信息', 'id + 后端 + hash']], ['session 里的认证信息'])),
]
A = dict(
    n=71, series='django', tags='Django,认证,session,authenticate,真实验证,动画演示',
    desc='实测 Django 用户认证流程:request.user 是惰性的(不访问则 0 次查询,访问一次 2 次:session + user);authenticate 依次尝试后端、失败发 user_login_failed(信号里的凭据只保留键名);登录后 session 只存用户 id、后端路径和密码派生的 hash。',
    lead='从请求进来到 request.user 有值,中间发生了什么?authenticate 和 login 各做什么?session 里到底存了什么?这篇用查询捕获和信号,把认证的每一步展开。',
    facts=[('0 或 2', 'request.user 惰性:不访问 0 次查询;已登录访问一次 2 次(session + user)'), ('3 个键', 'session 里的认证信息只有用户 id、后端路径、密码派生的 hash'), ('凭据被打码', 'user_login_failed 信号里 credentials 的密码与 token 值被替换成星号,用户名保留')],
    body=[
        sec('request.user 的惰性', '', term('', blk('d71', 1)), '<p><code>AuthenticationMiddleware</code> 只是给 <code>request.user</code> 放了一个惰性对象。视图不访问就不会有任何数据库开销;访问时先读 session、再按 id 取用户。</p>'),
        sec('authenticate()', '', term('', blk('d71', 2)), '<p>它只负责「凭据 → 用户」,不改变 session。失败信号里的凭据是打过码的(实测:<code>password</code> 与 <code>token</code> 都是 20 个星号,<code>username</code> 保留),所以信号接收者写日志也不会泄露密码。</p>'),
        sec('登录后的 session', '', term('', blk('d71', 3)), '<p>下一篇(第 72 篇)看 session 本身怎么存,第 73 篇看 <code>login()</code> 的内部,第 80 篇看这个 hash 的作用。</p>'),
        sec('分步演示:认证的三步', '', demo('认证流程', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;用 django.test.Client 与 CaptureQueriesContext', '没有验证:多个 AUTHENTICATION_BACKENDS 的顺序(第 76 篇)、异步认证(aauthenticate)、RemoteUserMiddleware、哪些键名会被打码的完整规则(实测了 password 与 token)'],
)
