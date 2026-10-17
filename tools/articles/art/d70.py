from lib import *
R = J('d70')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("cookie 里的 csrftoken 是 32 位的 secret,两次请求相同;表单里 {% csrf_token %} 渲染出的 token 是 64 位,而且每次请求都不同——是 secret 每次重新「掩码」的结果(缓解 BREACH 类攻击)。默认名字:cookie csrftoken,请求头 HTTP_X_CSRFTOKEN(即 X-CSRFToken),CSRF_USE_SESSIONS = False。", t=tl(L('token')), kv=KV([['cookie', '32 位 secret,不变'], ['表单 token', '64 位,每次不同']], ['表单 token'])),
    step("两个不同的表单 token 都能通过校验(解掩码后 secret 相同)。POST 不带 token → 403(CSRF verification failed. Request aborted.);带错误的 token → 403;没有 cookie 的新会话带了别人的 token → 403;用请求头 X-CSRFToken 传 token → 200。", t=tl(L('verify')), n=fl([['带有效 token(任一个)', '200'], ['缺 token / 错 token', '403'], ['没有 cookie', '403'], ['X-CSRFToken 请求头', '200']], done=[0, 3], mark=[1, 2]), kv=KV([['校验', 'cookie 里的 secret 与提交的 token 解掩码后比对']], ['校验'])),
    step("GET 等安全方法不检查 CSRF。通过真实的登录视图(调用 django.contrib.auth.login)登录后,csrftoken cookie 变了(登录前 G36c… → 登录后 JuBx…),登录前拿到的旧表单 token 再提交 → 403,用登录后的新 token → 200——登录时 token 会轮换。退出登录(logout)前后这个 cookie 没有变化。", t=tl(L('rotate')), kv=KV([['登录', '轮换 token,旧 token 失效'], ['退出', '本次实测 cookie 没变']], ['登录'])),
]
A = dict(
    n=70, series='django', tags='Django,CSRF,安全,真实验证,动画演示',
    desc='实测 CSRF:cookie 里是 32 位 secret(不变),表单 token 是 64 位且每次不同(掩码);缺 token / 错 token / 缺 cookie 都是 403,请求头 X-CSRFToken 可用;通过 login() 登录会轮换 cookie 并使旧表单 token 失效,logout 不轮换。',
    lead='{% csrf_token %} 渲染的那串字符是什么?为什么每次刷新都不一样却都能通过?登录之后为什么旧页面的表单提交会 403?这篇用真实的 CSRF 中间件把这些行为逐个验证。',
    facts=[('32 vs 64', 'cookie 里是 32 位 secret;表单 token 是 64 位,每次请求重新掩码'), ('403', '缺 token、错 token、缺 cookie 都被拒;X-CSRFToken 请求头可代替表单字段'), ('登录轮换', 'login() 会轮换 CSRF token:登录前的旧表单 token 之后提交得到 403')],
    body=[
        sec('token 的形态', '', term('', blk('d70', 1)), '<p>服务端不需要存储 token:cookie 里的 secret 就是依据。表单里的 token 是「掩码 + 密文」,每次不同,但解出的 secret 一致。</p>'),
        sec('校验', '', term('', blk('d70', 2)), '<p>403 页面上具体的失败原因文案本文没有逐个测;测试里必须用 <code>Client(enforce_csrf_checks=True)</code>,否则测试客户端默认跳过 CSRF。</p>'),
        sec('轮换', '', term('', blk('d70', 3)), '<p>登录后轮换 token 是防止「会话固定」类的攻击。副作用:用户在登录前打开的其它标签页里的表单会失效。</p>'),
        sec('分步演示:CSRF token', '', demo('CSRF token', [('t', 'term', '输出'), ('n', 'flow', '结果'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。django.test.Client(enforce_csrf_checks=True);HTTP 而非 HTTPS', '没有验证:HTTPS 下的 Origin / Referer 检查与 CSRF_TRUSTED_ORIGINS(第 123 篇)、CSRF_USE_SESSIONS = True 的行为、SameSite 与 CSRF_COOKIE_SECURE、AJAX 从 cookie 取 token、超出 CSRF_COOKIE_AGE 的 cookie 过期'],
)
