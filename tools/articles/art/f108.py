from lib import *
S = SS('f108')
R = J('f108')
steps = [
    step("Bearer 令牌的请求:没有 Authorization 头 → 401(reason: missing),带 WWW-Authenticate: Bearer realm=\"api\";用 Token abc 或只有 Bearer 没有令牌 → 401(malformed);错误令牌 → 401,WWW-Authenticate: Bearer error=\"invalid_token\";正确令牌 → 200,小写的 bearer 也被接受(方案名不区分大小写)。401 表示「你是谁没搞清」,普通用户访问 /admin 是 403(身份清楚但没权限),管理员是 200。", t=tl(S(1)), mark=lidx(S(1), '没有 Authorization', 'Token abc', '错误令牌'), done=lidx(S(1), '正确令牌', '401 与 403'), kv=KV([['401', '没有或无效的凭证,带 WWW-Authenticate'], ['403', '身份有效但权限不够']], ['401'])),
    step("令牌怎么存:secrets.token_urlsafe(32) 生成 32 字节随机数,编码成 43 个字符;服务端只存它的 sha256(64 个十六进制字符),不存明文,数据库泄漏时拿不到可直接使用的令牌。比较哈希用 hmac.compare_digest,不用 ==(常数时间比较;这里没有量化计时差别)。", t=tl(S(2)), done=lidx(S(2), '令牌', 'sha256', 'compare_digest'), kv=KV([['生成', 'secrets.token_urlsafe(32)'], ['存储', 'sha256 哈希,不存明文']], ['存储'])),
    step("签名令牌(itsdangerous):令牌形如 eyJ1aWQiOjF9.ar87ow.…,不需要密钥就能把 payload 解出来({\"uid\":1})——签名防篡改,不防查看,不要放敏感信息。验证通过 200;篡改签名 → 401;把 payload 里的 uid 改成 2、沿用原签名 → 401;max_age=1 秒、等 2 秒后 → 401「token expired」。", t=tl(S(3)), done=lidx(S(3), '令牌:', 'payload', '验证通过'), mark=lidx(S(3), '篡改签名', '改 payload', 'max_age'), kv=KV([['payload', '明文可读'], ['篡改', '签名校验失败 → 401'], ['过期', 'SignatureExpired → 401']], ['payload'])),
    step("吊销:不透明令牌删掉服务端记录就立即失效(401);签名令牌是无状态的,在过期之前仍然 200——吊销动作之后依旧通过,要吊销必须另存黑名单,或像这里的视图一样每次再检查用户是否还存在(用户被删后 401)。无状态的好处是不用查库,代价是不能立即撤销。", t=tl(S(4)), done=lidx(S(4), '不透明令牌删除后'), mark=lidx(S(4), '仍然 200', '用户被删除后'), kv=KV([['不透明令牌', '删记录即失效'], ['签名令牌', '到期前一直有效']], ['签名令牌'])),
    step("令牌放在查询参数里会进访问日志:gunicorn 的访问日志里能搜到 GET /me?token=SECRET-IN-QUERY,而放在 Authorization 头里的令牌在日志里搜不到。令牌要放头里,不要放 URL。", t=tl(S(5)), mark=lidx(S(5), '日志里能搜到', '访问日志行'), kv=KV([['查询参数', '进访问日志'], ['Authorization 头', '不进访问日志']], ['查询参数'])),
]
A = mkartf('f108', 108, 'Flask,API,Token认证,Bearer,itsdangerous,真实验证,动画演示',
    '实测 Flask API 的令牌认证:Bearer 头的各种情况与 401、WWW-Authenticate、403 的区别;令牌只存 sha256 哈希;itsdangerous 签名令牌的 payload 明文可读、篡改与过期都 401;不透明令牌可立即吊销而签名令牌不能;令牌放在查询参数里会进访问日志。',
    'API 令牌怎么发、怎么存、怎么验?签名令牌安全吗?怎么吊销?放在 URL 里行不行?这篇把每个问题都用实际请求验证一遍,包括真实 gunicorn 访问日志的检查。',
    [('401 vs 403', '没有有效凭证与权限不足的状态码区分'), ('明文可读', '签名令牌的 payload 不需要密钥就能解出'), ('进访问日志', '放在查询参数里的令牌会出现在 gunicorn 访问日志里')],
    [('Bearer 与状态码', '<p>上一篇:<a href="flask-idempotency-key.html">Idempotency-Key</a>;下一篇:<a href="flask-jwt-login.html">JWT 登录认证</a>。</p>'), ('令牌的存储', None), ('签名令牌', None), ('吊销', None), ('查询参数里的令牌', None)],
    steps, [ENV_F + '。itsdangerous、gunicorn 访问日志', '没有验证:compare_digest 与 == 的计时差别、令牌的作用域(scope)与过期策略、客户端存放令牌的位置(浏览器 localStorage 与 cookie 的风险)、令牌泄漏后的检测与轮换、OAuth 2.0 的完整流程'], 'API Token 认证')
