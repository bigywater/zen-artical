from lib import *
R = J('d80')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("session 里存的 _auth_user_hash 是从用户的密码哈希派生出来的(64 位)。u.get_session_auth_hash() 与 session 里的值一致;u.set_password('new') 之后再算,与旧 session 里的值不再一致。", t=tl(L('hash')), kv=KV([['_auth_user_hash', '由密码哈希派生']], ['_auth_user_hash'])),
    step("两台设备 A、B 都登录着。在 A 上改密码(不调用 update_session_auth_hash):A、B 下一个请求 request.user 都变成 AnonymousUser——包括发起修改的 A 自己。", t=tl(L('nokeep')), n=fl([['A、B 登录着', ''], ['A 上 set_password + save()', ''], ['A 与 B 的下一个请求', '都是 AnonymousUser']], mark=[2]), kv=KV([['改密码', '所有会话失效(含当前)']], ['改密码'])),
    step("在 A 上改密码后调用 update_session_auth_hash(request, user):A 保持登录(用新 hash 刷新了自己 session 里的值),B 仍然被踢下线(AnonymousUser)。这是 PasswordChangeView 的做法:改密码后留住当前设备,踢掉其它设备。", t=tl(L('keep')), kv=KV([['update_session_auth_hash', '只保住当前会话']], ['update_session_auth_hash'])),
    step("机制:每个请求的 get_user 用用户表里的密码哈希重新算 hash,与 session 里存的比较,不一致就当匿名;没有额外的查询(已登录请求仍是 session + user 两次)。只改 last_login 等字段不影响会话;把密码用同一明文重新哈希(盐变了)会让所有会话失效。", t=tl(L('queries') + L('reset')), kv=KV([['校验', '每个请求比对 hash'], ['改 last_login', '不影响'], ['重新哈希同一密码', '会踢掉所有会话']], ['重新哈希同一密码'])),
    step("想「登出所有设备」而不改密码:直接删除该用户的所有 session 行(本实验删了 2 个)——A、B 都变成匿名。也可以强制用户重设密码(这是通过让 hash 变化实现的)。", t=tl(L('purge')), kv=KV([['登出所有设备', '删 session,或让 hash 变化']], ['登出所有设备'])),
]
A = dict(
    n=80, series='django', tags='Django,session,密码修改,安全,真实验证,动画演示',
    desc='实测改密码为什么让其他设备下线:session 里的 _auth_user_hash 由密码哈希派生,每个请求重新比对;改密码后所有会话失效(含当前),用 update_session_auth_hash 保住当前设备;把同一明文重新哈希也会踢掉所有会话;只改 last_login 不影响。',
    lead='用户在手机上改了密码,电脑上的登录为什么立刻失效?为什么改密码的这台设备自己也被登出了?Django 是怎么做到的?这篇用两个「设备」把机制和例外都跑一遍。',
    facts=[('hash 比对', 'session 里存了由密码哈希派生的 _auth_user_hash,每个请求与用户表重新比对'), ('含当前设备', '改密码后不调用 update_session_auth_hash,发起修改的那台设备也被登出'), ('重新哈希', '同一个明文重新哈希(盐变了)也会让所有会话失效')],
    body=[
        sec('hash 从哪来', '', term('', blk('d80', 1)), '<p>密码哈希变了,派生出来的 session hash 就变了。这也是 <code>SESSION_ENGINE = signed_cookies</code> 时仍能「登出所有设备」的原因(第 79 篇)。</p>'),
        sec('两台设备', '', term('', blk('d80', 2)), term('', blk('d80', 3)), '<p>Django 自带的 <code>PasswordChangeView</code> 内部会调用 <code>update_session_auth_hash</code>;自己写改密码视图时一定别忘。</p>'),
        sec('每个请求怎么校验', '', term('', blk('d80', 4)), '<p>校验用的是用户对象里已经取出的密码哈希,不需要额外查询。</p>'),
        sec('登出所有设备', '', term('', blk('d80', 5)), '<p>删除 session 行只适用于数据库(或缓存)后端;cookie 后端要靠让 hash 变化。</p>'),
        sec('分步演示:改密码之后', '', demo('改密码与会话', [('t', 'term', '输出'), ('n', 'flow', '结果'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;两个 Client 代表两台设备', '没有验证:SECRET_KEY_FALLBACKS 轮换对 session hash 的影响、PasswordChangeView / PasswordResetView 的完整流程、单点登录场景、记住我(持久 cookie)的设备'],
)
