from lib import *
R = J('d23')
steps = [
    step("ConditionalGetMiddleware 自动给响应加 ETag(内容的哈希)。第一次 200,体 5000 字节;带 If-None-Match 再请求 → 304、体 0 字节,但视图仍然被执行了(调用次数 1 → 2):省的是带宽,不是计算。", t=tl(R['auto'].splitlines(), cur=[0], mark=[1]), kv=KV([['中间件自动 ETag', '省带宽,不省视图']], ['中间件自动 ETag'])),
    step("@condition(etag_func=…):在执行视图之前先比对。If-None-Match: \"v1\" → 304,视图调用次数没有增加(仍是 1),304 响应只带 ETag 头;\"v2\" 不匹配 → 200,视图执行;W/\"v1\"(弱校验器)也匹配 → 304;* → 304。", t=tl(R['cond'].splitlines(), cur=[0, 1], mark=[2]), kv=KV([['@condition', '命中就不执行视图']], ['@condition'])),
    step("Last-Modified:If-Modified-Since 等于 Last-Modified → 304;更早 → 200(内容比客户端的新);更晚 → 304;不合法的日期(garbage)→ 200,当作没带。", t=tl(R['lm'].splitlines(), cur=[1, 3], mark=[2, 4]), kv=KV([['If-Modified-Since', '晚于或等于最后修改时间 → 304']], ['If-Modified-Since'])),
    step("同时给 ETag 与 Last-Modified:两者都参与判断。\"v1\" 匹配 → 304,即使 If-Modified-Since 早于修改时间;\"v2\" 不匹配 → 200。另外:POST 请求带 If-None-Match: \"v1\"(与当前 ETag 相同)→ 412 Precondition Failed,而不是 304。", t=tl(R['both'].splitlines(), cur=[0, 2], mark=[1, 3]), kv=KV([['ETag 匹配', '优先于 If-Modified-Since'], ['POST + If-None-Match 命中', '412']], ['POST + If-None-Match 命中'])),
]
A = dict(
    n=23, series='django', tags='Django,HTTP缓存,ETag,条件请求,真实验证,动画演示',
    desc='实测条件 GET:ConditionalGetMiddleware 自动 ETag 只省带宽、视图照常执行;@condition 用 etag / last_modified 函数提前判断,命中时不执行视图(调用次数不增);If-None-Match 与 If-Modified-Since 的各种取值的结果,POST 带命中的 If-None-Match 得到 412。',
    lead='ETag 和 Last-Modified 能让浏览器少拉内容,但「少拉」的是带宽还是计算?Django 有两条路:中间件自动算,和 @condition 提前判断。这篇数视图被执行的次数,把两条路的差别直接量出来。',
    facts=[('视图仍执行', 'ConditionalGetMiddleware 自动生成 ETag 时,304 也是视图执行完之后才决定的'), ('不执行视图', '@condition 在视图之前比对,命中直接 304,视图调用次数不增'), ('412', 'POST 带一个与当前 ETag 相同的 If-None-Match 得到 412,不是 304')],
    body=[
        sec('中间件自动 ETag', '', term('', blk('d23', 1)), '<p>中间件在响应阶段根据内容算出 ETag,再和请求头比较。视图已经跑完、响应已经生成,所以只能省下传输,省不了计算。</p>'),
        sec('@condition', '', term('', blk('d23', 2)), '<p><code>etag_func</code> / <code>last_modified_func</code> 在视图之前调用(应当是便宜的,比如读一个版本号或最后更新时间)。命中时直接返回 304,昂贵的视图不执行。</p>'),
        sec('Last-Modified', '', term('', blk('d23', 3)), '<p>比较的是秒级时间。客户端传来不合法的日期时被当成没传。</p>'),
        sec('两个条件一起用', '', term('', blk('d23', 4)), '<p>同时提供两个函数时,两个条件都参与判断;实测 ETag 匹配即 304(哪怕 If-Modified-Since 更早)。注意对不安全方法(POST)带 <code>If-None-Match</code> 的处理是 412。</p>'),
        sec('分步演示:条件请求', '', demo('条件 GET', [('t', 'term', '实测输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。视图调用次数用视图里的计数器统计', '没有验证:If-Range / Range 请求、强弱校验器的更细区别(本文只测了 W/ 前缀在 If-None-Match 下匹配)、真实浏览器的缓存行为(这里只用 Client 手工带头)、GZipMiddleware 对自动 ETag 的影响'],
)
