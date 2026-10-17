from lib import *
S = SS('f119')
R = J('f119'); cw = R['crack_weak']; cst = R['crack_strong']
steps = [
    step("没有 SECRET_KEY 时往 session 里写东西:请求直接 500,异常是 RuntimeError「The session is unavailable because no secret key was set. Set the secret_key on the application to something unique and secret.」。SECRET_KEY 不设,session 根本不能用。", t=tl(S(1)), done=lidx(S(1), 'HTTP', '传播出来的异常'), kv=KV([['没有 SECRET_KEY', 'session 写入抛 RuntimeError']], ['没有 SECRET_KEY'])),
    step("session cookie 的结构:载荷、时间戳、签名三段,用点号分隔(这里 38、6、27 个字符)。载荷只是 base64 的 JSON,不需要密钥就能读出 {\"role\":\"user\",\"user\":\"ann\"}——SECRET_KEY 只负责签名防篡改,不负责加密,不要往 session 里放不能让用户看到的东西。", t=tl(S(2)), done=lidx(S(2), 'cookie', '不用密钥', 'cookie 的三段'), kv=KV([['载荷', 'base64 JSON,明文可读'], ['签名', 'HMAC,防篡改'], ['不加密', '不要放敏感信息']], ['不加密'])),
    step("知道 SECRET_KEY 就能伪造任意用户:用同样的序列化器给 {user: mallory, role: admin} 签名,服务端读到的就是 role = admin。用错误的 key 签的、或者篡改了签名的 cookie,服务端当作没有 session(user 与 role 都是 None)。SECRET_KEY 泄漏等于所有账号失守,不能写进代码仓库。", t=tl(S(3)), mark=lidx(S(3), '正确的 key'), done=lidx(S(3), '错误的 key', '篡改签名'), kv=KV([['有 key', '可以伪造任意 session'], ['没有 key', '改不了,也伪造不了']], ['有 key'])),
    step("换 SECRET_KEY:换之前同一个 cookie 读到 {role: user, user: ann},换之后读到 None——所有已登录用户的 session 立刻失效,全员被登出。", t=tl(S(4)), mark=lidx(S(4), '换 key 之后'), done=lidx(S(4), '换 key 之前'), kv=KV([['直接换 key', '所有人被登出']], ['直接换 key'])),
    step("SECRET_KEY_FALLBACKS(Flask 3.1)实现平滑轮换:新 key 加 FALLBACKS=[旧 key],带旧 cookie 的请求仍能读到 {role: user, user: ann};之后服务端新下发的 cookie 用新 key 签名(能被新 key 验证,旧 key 验证不了);只有新 key、没有 FALLBACKS 时,旧 cookie 作废。轮换时先配上 fallback,等旧 cookie 过期后再去掉旧 key。", t=tl(S(5)), done=lidx(S(5), 'FALLBACKS=[旧 key]', '新下发'), mark=lidx(S(5), '没有 FALLBACKS'), kv=KV([['FALLBACKS', '旧 cookie 仍可读,新 cookie 用新 key'], ['没有 FALLBACKS', '旧 cookie 作废']], ['FALLBACKS'])),
    step(f"弱 SECRET_KEY 能被字典猜出来:key 是 'dev' 时,拿一个简短的常见词表去验证自己拿到的 cookie,猜中 {cw[0]!r} 用了 {cw[1]:.1f} ms。强 key(secrets.token_hex(32),64 个字符)对 {cst[2]} 个候选一个也没猜中,每个候选约 {cst[1] / cst[2] * 1000:.1f} µs(单核 Python);32 字节的随机 key 有 2^256 种可能,穷举不可行(我没有真的穷举,这是算术判断,不是实验)。生成方式:secrets.token_hex(32)。", b=bars([['弱 key dev', max(cw[1], 0.05), f'{cw[1]:.1f} ms'], ['强 key 试 20 万个', cst[1], f'{cst[1]:.0f} ms 未猜中']], cst[1], mark=[0], done=[1]), t=tl(S(6)), mark=lidx(S(6), '字典猜测'), done=lidx(S(6), '强 key', '生成方式'), kv=KV([['弱 key', '一次词表就猜中'], ['强 key', 'secrets.token_hex(32)']], ['强 key'])),
]
A = mkartf('f119', 119, 'Flask,SECRET_KEY,session,安全,真实验证,动画演示',
    '实测 SECRET_KEY 的用途与风险:没设时 session 报 RuntimeError、cookie 载荷明文可读、知道 key 就能伪造 role=admin、换 key 让所有人被登出、SECRET_KEY_FALLBACKS 平滑轮换、弱 key 用词表瞬间被猜中而强 key 对 20 万个候选无一命中。',
    'SECRET_KEY 到底保护什么?cookie 里的内容能被用户看到吗?key 泄漏后果多严重?怎么轮换而不让所有人下线?这篇用真实的伪造、轮换和猜测把每个问题验证一遍。',
    [('明文可读', 'session cookie 的载荷不需要密钥就能解出'), ('admin', '用泄漏的 key 伪造的 session 被服务端接受的角色'), (f'{cw[1]:.1f} ms', '弱 key "dev" 被词表猜中的用时')],
    [('没有 SECRET_KEY', '<p>上一篇:<a href="flask-streaming-json.html">Streaming JSON</a>;下一篇:<a href="flask-session-cookie-security.html">Session Cookie 安全属性</a>。</p>'), ('cookie 的内容', None), ('key 泄漏', None), ('换 key', None), ('平滑轮换', None), ('弱 key', '<p>只对自己生成的 cookie 做猜测,没有对任何别人的系统做过测试。</p>')],
    steps, [ENV_F + '。itsdangerous(Flask 的 session 序列化器)', '没有验证:真实攻击工具的猜测速度(我的 Python 实现每秒约 8 万个,专业工具远快于此)、其它用到 SECRET_KEY 的扩展(Flask-WTF 的 CSRF token、Flask-Login 的 remember cookie)在轮换时的行为、把 key 存在环境变量或密钥管理服务里的做法'], 'SECRET_KEY 的用途')
