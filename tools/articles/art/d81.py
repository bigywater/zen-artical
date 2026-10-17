from lib import *
R = J('d81')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
st = R['stores']
steps = [
    step("默认存储 FallbackStorage:先尝试放进 cookie(名字 messages)。添加 2 条短消息:响应带 Set-Cookie: messages(长度 120),session 表 0 行;下一个请求读取到 2 条,读取之后响应里 messages cookie 被设成过期(1970-01-01)——消息「用完即删」;再读一次得到空列表。", t=tl(L('basic')), kv=KV([['默认', '先放 cookie'], ['读取', '读完即删']], ['读取'])),
    step("消息级别:MESSAGE_LEVEL 没有设置时,最低保存 INFO(20);debug()(10)被丢弃,读取到的是 info / success / warning / error 四条。每条消息的 level_tag 对应它的级别名(可用 MESSAGE_TAGS 改)。", t=tl(L('levels')), kv=KV([['debug()', '低于最低级别,不保存']], ['debug()'])),
    step("「用过」是在遍历时标记的:只取 len() 与类型(/peek/)不算用过,之后 /show/ 还能读到那条消息;中间即使发了一个没读消息的请求(/noop/),消息也一直保留到被真正读取为止。所以消息可以跨多次重定向存活。", t=tl(L('used')), kv=KV([['len() / 类型', '不消耗消息'], ['遍历', '才标记为已用']], ['遍历'])),
    step("cookie 放不下时回退到 session(FallbackStorage 的名字由来):随机内容下 1 条 × 50 字符、5 条 × 300 字符都在 cookie 里(长度 163 / 1274,session 行数 0);2 条 × 3000 字符超过 cookie 上限,messages cookie 只剩 87 字符,消息转存到 session(表里 1 行),读取仍得到 2 条。", t=tl(L('overflow')), b=bars([['1×50 的 cookie 长度', 163, '163'], ['5×300 的 cookie 长度', 1274, '1274'], ['2×3000 的 cookie 长度', 87, '87(转存 session)']], 1400, mark=[2]), kv=KV([['cookie 上限约 2 KB', '超出转存 session']], ['cookie 上限约 2 KB'])),
    step("三种存储:CookieStorage → Set-Cookie messages、session 0 行;SessionStorage → 没有 messages cookie、session 1 行;FallbackStorage → 短消息走 cookie。CookieStorage 放不下的消息会被丢弃(不回退)——本文只验证了三种的基本行为,没有验证 CookieStorage 超限时丢弃的说法。", t=tl([f"{k}:{v}" for k, v in st.items()], cur=[0, 1, 2]), kv=KV([['Cookie', '客户端存'], ['Session', '服务端存'], ['Fallback', 'cookie 优先']], ['Fallback'])),
]
A = dict(
    n=81, series='django', tags='Django,messages,消息框架,cookie,真实验证,动画演示',
    desc='实测 Django 消息框架:默认 FallbackStorage 先放 cookie(用完即删,读完 cookie 被置为过期);默认最低级别 INFO,debug() 被丢弃;只有遍历才算用过;随机内容下 cookie 放不下时(2 条 × 3000 字符)转存到 session;三种存储各自放哪里。',
    lead='messages.success(request, "保存成功") 之后,那条消息存在哪里?什么时候被删?消息很长怎么办?这篇看默认的 FallbackStorage,以及 Cookie / Session 两种存储的行为。',
    facts=[('用完即删', '读取后响应把 messages cookie 设成过期;没读之前跨请求一直保留'), ('INFO', '未设置 MESSAGE_LEVEL 时最低保存 INFO,debug() 被忽略'), ('2 KB', 'cookie 放不下时(2 条 × 3000 字符随机内容)FallbackStorage 转存 session')],
    body=[
        sec('默认存储', '', term('', blk('d81', 1)), '<p>消息框架适合「重定向后提示一次」。数据先在 cookie 里,所以短消息不需要 session、也没有数据库开销。</p>'),
        sec('级别', '', term('', blk('d81', 2)), '<p>用 <code>MESSAGE_LEVEL</code> 调整最低级别,比如开发时设成 <code>DEBUG</code> 才能看到调试消息。</p>'),
        sec('什么算「用过」', '', term('', blk('d81', 3)), '<p>模板里 <code>{% for m in messages %}</code> 遍历就是「用过」。所以如果一个页面没有遍历消息(比如 API 视图),消息会一直留到下一个会遍历的页面。</p>'),
        sec('放不下时', '', term('', blk('d81', 4)), '<p>注意:我第一次用重复字符 <code>x*3000</code> 测,cookie 里的内容被压缩后很小,看不到溢出——测存储上限要用随机内容。</p>'),
        sec('三种存储', '', term('', blk('d81', 5)), '<p>选择:不想用 session(无状态)选 <code>CookieStorage</code>,消息内容注意不要放敏感信息(cookie 里可读,签名只防篡改);要可靠就用 <code>SessionStorage</code>。</p>'),
        sec('分步演示:消息的一生', '', demo('消息框架', [('t', 'term', '实测输出'), ('b', 'bars', 'cookie 长度'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。django.test.Client;cookie 长度取自响应的 Set-Cookie', '没有验证:CookieStorage 超限时的丢弃行为、消息 tags 与 extra_tags 的渲染、异步视图里的消息、消息中 HTML 的转义(第 84 篇)'],
)
