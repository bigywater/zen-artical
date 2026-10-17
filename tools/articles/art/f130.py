from lib import *
S = SS('f130')
R = J('f130'); c = R['cost']; lg = R['long']
w, p6, sc, sc4, ar, sh, p1 = c['scrypt(Werkzeug 默认 32768:8:1)'], c['pbkdf2:sha256:600000'], c['scrypt(Werkzeug 默认 32768:8:1)'], c['scrypt:131072:8:1'], c['argon2id(argon2-cffi 默认)'], c['sha256 一次(错误示范,不要用)'], c['pbkdf2:sha256:1000(旧的、太弱)']
steps = [
    step(f"Werkzeug 默认哈希(3.1.9)的格式是「方法$盐$摘要」:scrypt:32768:8:1$<16 个字符的盐>$<128 个十六进制字符的摘要>,总长 162。同一个密码哈希两次结果不同(盐是随机的),但 check_password_hash 对正确的密码返回 True、错误的返回 False——验证时从哈希字符串里取出方法与盐重新算。", t=tl(S(1)), done=lidx(S(1), '默认哈希', '同一个密码再来一次', 'check_password_hash'), kv=KV([['格式', '方法$盐$摘要'], ['盐', '每次随机,同密码结果不同']], ['格式'])),
    step(f"单次耗时(5 次中位数),也就是攻击者每猜一次要付的代价:pbkdf2:sha256:1000 {p1:.3f} ms(太弱);pbkdf2:sha256:600000 {p6:.1f} ms;Werkzeug 默认 scrypt {sc:.1f} ms;scrypt:131072:8:1 {sc4:.0f} ms;argon2id(argon2-cffi 默认){ar:.1f} ms;一次 sha256 {sh:.3f} ms(错误示范)。默认 scrypt 比一次 sha256 慢约 {sc / sh:.0f} 倍。参数越高越慢,登录接口本身每次验证也要付同样的时间,所以要在服务器能承受的范围内取。", b=bars([['sha256 一次', max(sh, 0.5), f'{sh:.3f} ms'], ['pbkdf2 1000', max(p1, 0.5), f'{p1:.2f} ms'], ['argon2id', ar, f'{ar:.0f} ms'], ['scrypt 默认', sc, f'{sc:.0f} ms'], ['scrypt 131072', sc4, f'{sc4:.0f} ms']], sc4, mark=[0, 1], done=[2, 3, 4]), t=tl(S(2)), mark=lidx(S(2), 'sha256 一次', 'pbkdf2:sha256:1000'), done=lidx(S(2), 'scrypt(Werkzeug', 'argon2id'), kv=KV([['sha256 一次', f'{sh:.3f} ms,不要用'], ['scrypt 默认', f'{sc:.0f} ms'], ['argon2id', f'{ar:.0f} ms']], ['scrypt 默认'])),
    step("密码升级:库里 ann 还是 pbkdf2:sha256:1000 的弱哈希,bob 已经是 scrypt。ann 用错误密码登录 → 失败,哈希保持不变;ann 正确登录 → 成功并重新哈希写回(变成 scrypt:32768:8:1);再登录一次直接成功。没有登录过的用户仍是旧哈希——升级只发生在用户登录、手里有明文密码的时候,所以要长期保留旧算法的验证能力。", t=tl(S(3)), done=lidx(S(3), '升级前', 'ann 正确登录', '升级后'), mark=lidx(S(3), 'ann 用错误'), kv=KV([['登录成功时', '检查是否需要升级,重新哈希写回'], ['没登录的用户', '仍是旧哈希']], ['登录成功时'])),
    step("算法参数写在哈希字符串里:scrypt:16384:8:1 与 scrypt:131072:8:1 两种参数的哈希,都能用同一个 check_password_hash 验证(True、True)。所以提高参数后,旧用户不受影响,在下次登录时再升级。", t=tl(S(4)), done=lidx(S(4), '旧参数哈希头', '两者都能'), kv=KV([['参数在哈希里', '旧哈希仍可验证']], ['参数在哈希里'])),
    step(f"超长与空密码:10 万个字符的密码哈希耗时 {lg[0]:.1f} ms、哈希长度 {lg[1]},和普通密码的 {sc:.0f} ms 差不多(这次测量里没有随长度变慢);空字符串密码也能哈希并验证。是否还要在应用层限制密码长度,这里没有验证。", t=tl(S(5)), done=lidx(S(5), '10 万个', '空字符串'), kv=KV([['10 万字符', f'{lg[0]:.0f} ms,没有明显变慢']], ['10 万字符'])),
    step("argon2id(argon2-cffi 25.1.0):哈希形如 $argon2id$v=19$m=65536,t=3,p=4$<盐>$<摘要>,参数也在字符串里;verify 通过,按默认参数 check_needs_rehash 返回 False;用更弱的参数(t=1、m=8)生成的哈希,check_needs_rehash 返回 True——这个库自带「是否需要升级」的判断,不用自己解析字符串。", t=tl(S(6)), done=lidx(S(6), '验证', '更弱参数'), kv=KV([['check_needs_rehash', '库自带的升级判断'], ['参数', '写在哈希字符串里']], ['check_needs_rehash'])),
]
A = mkartf('f130', 130, 'Flask,密码哈希,scrypt,argon2,Werkzeug,真实验证,动画演示',
    f'实测 Werkzeug 密码哈希:默认 scrypt 的格式与随机盐、各方法单次耗时(sha256 一次 {sh:.3f} ms 对 scrypt {sc:.0f} ms 对 argon2id {ar:.0f} ms)、登录成功时把旧的弱哈希升级写回、参数写在哈希里旧哈希仍可验证、超长密码、argon2-cffi 的 check_needs_rehash。',
    '密码该怎么存?默认的哈希够不够强?库里还有旧的弱哈希怎么办?这篇量出每种方法的真实耗时,并实现一遍「登录时顺便升级」的流程。',
    [(f'{sc:.0f} ms', 'Werkzeug 默认 scrypt 哈希一次的耗时(单核)'), (f'约 {sc / sh:.0f} 倍', 'scrypt 默认相对一次 sha256 的耗时'), ('登录时升级', '用户登录成功、手里有明文密码时把旧哈希重新哈希写回')],
    [('哈希的格式', '<p>上一篇:<a href="flask-rate-limiting-security.html">Rate Limiting</a>;下一篇:<a href="flask-login-lockout.html">登录失败锁定</a>。</p>'), ('各方法的耗时', None), ('密码升级', None), ('参数在哈希里', None), ('超长与空密码', None), ('argon2', '<p>argon2-cffi 是我额外装进环境的,Flask 与 Werkzeug 本身不带它。</p>')],
    steps, [ENV_F + '。Werkzeug 3.1.9、argon2-cffi 25.1.0', '没有验证:bcrypt 与 passlib 的行为、pepper(应用层的额外密钥)、哈希在 GPU 或专用硬件上的破解成本(这里只量了本机单核的耗时)、数据库里已有哈希的批量迁移与回滚、密码强度策略'], '密码哈希与升级')
