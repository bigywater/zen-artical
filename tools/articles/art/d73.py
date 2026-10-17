from lib import *
R = J('d73')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("匿名时往 session 放了购物车(cart=[1, 2]),再登录:session_key 换成了新的(cycle_key),购物车数据保留;旧 key 的行被 DELETE。这样可以防止「会话固定」:攻击者事先给受害者塞的 session id 在登录后就作废。登录发出的 SQL 依次是:验证用户 → 取旧 session → 写新 session 行(INSERT)→ 删旧行(DELETE)→ 更新 last_login → 再写一次 session 数据。", t=tl(L('cycle')[:3] + L('cycle')[4:]), kv=KV([['匿名 → 登录', '换 key,保留数据']], ['匿名 → 登录'])),
    step("已经以用户 u 登录时,再以另一个用户 v 登录:整个 session 被清空(cart = None,key 也换了),避免新用户继承旧用户的数据。同一个用户再登录一次:key 不变、cart 也保持(这次 cart 本来就已被清空,所以是 None;key 相同)。", t=tl(L('switch')), kv=KV([['换用户登录', 'flush:清空全部数据'], ['同用户再登录', 'key 不变']], ['换用户登录'])),
    step("logout():整个 session 被 flush——先读 session 与用户,最后 DELETE django_session 一行;登出后行数 1 → 0、cart = None、key 换了。再访问会得到一个全新的 session。", t=tl(L('logout')), kv=KV([['logout()', 'flush:删除行、清空数据']], ['logout()'])),
    step("login() 会更新 user.last_login(登录前 None → 登录后有时间)并发 user_logged_in 信号——这是一次额外的数据库写。断开 update_last_login 信号接收者后再登录,last_login 保持 None:高并发登录场景可以这样省一次写(本文只验证了断开后不再更新)。", t=tl(L('lastlogin')), kv=KV([['last_login', 'login() 顺带写一次'], ['可断开', 'user_logged_in.disconnect(update_last_login)']], ['可断开'])),
]
A = dict(
    n=73, series='django', tags='Django,login,logout,session,真实验证,动画演示',
    desc='实测 login() / logout() 的内部:匿名登录时 session_key 换新、数据保留、旧行被删(防会话固定);换用户登录会清空 session;logout 清空并删除 session 行;login 顺带写 last_login,断开 update_last_login 信号可省一次写。',
    lead='login() 和 logout() 到底对 session 做了什么?key 会变吗?数据保留吗?这篇分四种情形逐一验证,并列出登录时发出的 SQL。',
    facts=[('cycle_key', '匿名 → 登录:session_key 换新、数据保留、旧行删除'), ('flush', '换用户登录或 logout:清空整个 session(行删除、数据没了)'), ('last_login', 'login() 顺带 UPDATE 用户的 last_login,是登录路径上的一次额外写')],
    body=[
        sec('登录:cycle_key', '', term('', blk('d73', 1)), '<p>购物车保留是有意的:用户在登录前加入购物车,登录后不应丢失。但 session id 必须换,防止会话固定攻击。</p>'),
        sec('换用户与同用户', '', term('', blk('d73', 2)), '<p>规则:session 里已有另一个用户 id → flush;已有同一个用户 → 只是沿用。</p>'),
        sec('登出', '', term('', blk('d73', 3)), '<p><code>logout()</code> 会 <code>session.flush()</code>,所以登出前放在 session 里的其他数据(如语言偏好)也没了——想保留的要在登出后重新写。</p>'),
        sec('last_login', '', term('', blk('d73', 4)), '<p>信号 <code>user_logged_in</code> 的默认接收者是 <code>update_last_login</code>。</p>'),
        sec('分步演示:登录与登出', '', demo('login / logout', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;session 行数用 Session.objects.count() 统计', '没有验证:SESSION_SAVE_EVERY_REQUEST 下的登录、多个标签页并发登录、logout 与 CSRF token 轮换的关系(第 70 篇只看到登出前后 cookie 不变)、异步 alogin'],
)
