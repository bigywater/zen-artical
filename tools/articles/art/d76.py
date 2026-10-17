from lib import *
R = J('d76')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("AUTHENTICATION_BACKENDS = [TokenBackend, ModelBackend(带日志), EmailBackend]。用 username/password 登录:Token 后端先被调用(token=None,直接返回 None)、然后 ModelBackend 认证成功,后面的 EmailBackend 不再调用;用邮箱登录:Token → Model(用户名当邮箱查不到)→ Email 成功;token=good:只有 Token 后端被调用;密码错:三个后端都被试一遍,返回 None。", t=tl(L('order'), cur=[0, 1, 2], mark=[3]), kv=KV([['顺序', '按列表依次试,第一个返回用户的胜出']], ['顺序'])),
    step("后端里抛 PermissionDenied 会立刻终止认证:token='banned' 时 TokenBackend 抛异常,authenticate 返回 None,后面的 ModelBackend、EmailBackend 一个都没有被调用。", t=tl(L('denied')), kv=KV([['PermissionDenied', '立即终止,不再试后面的']], ['PermissionDenied'])),
    step("多个后端时 login() 必须知道用户来自哪个后端:直接 login(user)(用户不是 authenticate 返回的)→ ValueError: You have multiple authentication backends configured and therefore must provide the `backend` argument or set the `backend` attribute on the user;authenticate 返回的 user.backend 已带上后端路径,login 把它写进 session[_auth_user_backend];也可以显式传 backend=。", t=tl(L('login')), kv=KV([['user.backend', 'authenticate 返回的用户已经带着']], ['user.backend'])),
    step("每个请求的 get_user 用 session 里记录的后端来取用户:改成 TokenBackend 也能取到(它实现了 get_user,session 里的 hash 仍要校验);后端路径不存在(no.such.Backend)时 get_user 返回 AnonymousUser,不抛异常——用户会静默变成匿名。", t=tl(L('get_user')), kv=KV([['get_user', '由 session 里记录的后端实现'], ['后端被移除', '用户静默变匿名']], ['后端被移除'])),
]
A = dict(
    n=76, series='django', tags='Django,认证后端,authenticate,真实验证,动画演示',
    desc='用三个带日志的认证后端(Token / ModelBackend / Email)实测 AUTHENTICATION_BACKENDS:按顺序尝试、第一个成功的胜出;PermissionDenied 终止后续;多后端时 login() 需要 backend 参数;session 记录后端路径,后端被移除后用户静默变成匿名。',
    lead='想支持邮箱登录、token 登录,就要写认证后端。它们的调用顺序是什么?怎么被 login 记住?后端改了配置会发生什么?这篇写三个后端并打日志,把这些行为一一验证。',
    facts=[('按顺序', '依次尝试,第一个返回用户的胜出;每个后端按参数签名接收凭据'), ('PermissionDenied', '后端抛它会立刻终止认证,不再试后面的'), ('静默匿名', 'session 里记录的后端被从配置里移除后,get_user 返回 AnonymousUser,不报错')],
    body=[
        sec('调用顺序', '', term('', blk('d76', 1)), '<p>后端的 <code>authenticate</code> 通常用关键字参数接收凭据(<code>username</code>/<code>password</code>、<code>token</code>…),Django 会跳过签名不匹配的后端(本文的日志里 TokenBackend 收到 <code>token=None</code> 就是这个机制的结果)。</p>'),
        sec('PermissionDenied', '', term('', blk('d76', 2)), '<p>用于「这个用户被明确禁止,不要再问别的后端了」。</p>'),
        sec('login() 与 backend', '', term('', blk('d76', 3)), '<p>只有一个后端时可以省略;多个后端时缺 <code>backend</code> 直接报错。</p>'),
        sec('get_user 与后端变更', '', term('', blk('d76', 4)), '<p>上线时改 <code>AUTHENTICATION_BACKENDS</code>(比如移除旧后端),所有 session 里记着旧后端的用户会被静默登出,且没有任何错误日志。改之前要评估影响。</p>'),
        sec('分步演示:认证后端', '', demo('认证后端', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;后端里的日志写到文件', '没有验证:异步后端(aauthenticate)、后端里的权限方法(get_all_permissions 等)与多后端的合并规则、RemoteUserBackend、认证后端里的限流'],
)
