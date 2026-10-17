from lib import *
R = J('d72')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("session 是「用到才创建」:GET /nothing/(不碰 session)、/ro/(只读一个键)、/read/(读),都没有 Set-Cookie、表里行数为 0;只有 GET /set/(写入 request.session['cart'])才创建 session 行并发 Set-Cookie: sessionid。", t=tl(L('create')), kv=KV([['只读', '不创建 session'], ['写入', '才创建行 + Set-Cookie']], ['写入'])),
    step("表里存的:session_key 32 位随机字符串;expire_date 距现在 14.0 天(SESSION_COOKIE_AGE 默认 1209600 秒);session_data 是「base64 编码的 JSON : 时间戳 : 签名」,解码后是 {'cart': [1, 2, 3]}。cookie 属性:HttpOnly、SameSite=Lax、Max-Age=1209600、Path=/;没有 Secure(HTTP 测试)。", t=tl(L('data')), kv=KV([['数据', '签名过的 JSON'], ['cookie', 'HttpOnly + SameSite=Lax']], ['cookie'])),
    step("每个请求的查询:/read/ 只读 → 1 次 SELECT;/set/ 修改 → SELECT + BEGIN + UPDATE + COMMIT(4 条,其中 UPDATE 1 次);/nothing/ 不访问 session → 0 次。有修改才写库(SESSION_SAVE_EVERY_REQUEST 默认 False)。", t=tl(L('queries')), kv=KV([['只读', '1 次 SELECT'], ['修改', '再 UPDATE 一次']], ['修改'])),
    step("默认值:SESSION_COOKIE_AGE = 1209600 秒(14 天)、SESSION_SAVE_EVERY_REQUEST = False、SESSION_COOKIE_HTTPONLY = True、SESSION_COOKIE_SAMESITE = Lax、SESSION_EXPIRE_AT_BROWSER_CLOSE = False。所以默认是固定 14 天过期,不是「滑动过期」。", t=tl(L('defaults')), kv=KV([['过期', '默认固定 14 天,不续期']], ['过期'])),
    step("过期的 session 行不会自动删除:把 expire_date 改到昨天后,用该 cookie 读取得到空({'cart': None}),但表里仍有 1 行;需要定期运行 manage.py clearsessions 清理(之后表里 0 行)。", t=tl(L('expired') + [R['cleared']], mark=[0], done=[2]), kv=KV([['过期行', '不自动删除,要 clearsessions']], ['过期行'])),
]
A = dict(
    n=72, series='django', tags='Django,session,登录状态,真实验证,动画演示',
    desc='实测 Session 默认(数据库后端)如何保存登录状态:只读不创建 session、写入才发 Set-Cookie;session 表的 key / data / expire_date;每个请求 1 次 SELECT、修改再 UPDATE;默认固定 14 天过期;过期行不会自动清理,需要 clearsessions。',
    lead='用户的登录状态放在哪里?每个请求为它付出多少次查询?过期了会被自动清掉吗?这篇看默认的数据库 session 后端,把创建时机、表内容、cookie 属性、查询数和过期都验证一遍。',
    facts=[('用到才创建', '只读 session 不创建行也不发 Set-Cookie;写入才创建'), ('14 天固定', 'SESSION_COOKIE_AGE 默认 1209600 秒;SESSION_SAVE_EVERY_REQUEST 默认 False,不续期'), ('不自动清理', '过期的 session 行仍留在表里,要运行 clearsessions')],
    body=[
        sec('什么时候创建', '', term('', blk('d72', 1)), '<p>这也是「不登录的访客不产生 session 行」的原因;但一旦有代码往 session 里写(比如 messages 框架、CSRF 用 session 时),就会给每个访客创建一行。</p>'),
        sec('表里与 cookie', '', term('', blk('d72', 2)), '<p><code>session_data</code> 的格式是「base64 的 JSON : 时间戳 : 签名」(实测),所以数据库里的内容不能被随便伪造,但也<b>不是加密的</b>(base64 可读)。</p>'),
        sec('查询与写入', '', term('', blk('d72', 3)), '<p>Django 会在响应阶段判断 <code>session.modified</code>,才决定是否写库。</p>'),
        sec('默认值', '', term('', blk('d72', 4)), '<p>要「用户活跃就续期」需要 <code>SESSION_SAVE_EVERY_REQUEST = True</code>(每个请求都写库,本文没有测它的代价)。</p>'),
        sec('过期与清理', '', term('', blk('d72', 5)), '<p>数据库后端的表会一直增长。定时任务运行 <code>clearsessions</code>(cron / celery beat)。缓存后端靠缓存自己的过期。</p>'),
        sec('分步演示:登录状态的存放', '', demo('Session 保存登录状态', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite 后端;cookie 属性来自 Set-Cookie 头', '没有验证:SESSION_SAVE_EVERY_REQUEST=True 的代价、SESSION_COOKIE_SECURE 与 HTTPS、session 序列化器(JSON vs pickle)的选择、session 数据大小的上限(见第 79 篇的 cookie 后端)'],
)
