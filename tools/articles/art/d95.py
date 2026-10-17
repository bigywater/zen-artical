from lib import *
R = J('d95')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("@cache_page(60):同一个 URL 第二次请求命中缓存(视图不执行:两次都是 page 1);换查询串 ?q=2 是另一份(page 2),视图共执行 2 次。响应头带 Cache-Control: max-age=60 与 Expires,告诉浏览器也缓存 60 秒;这个缓存 key 由 URL、方法和 Vary 里的头组成。", t=tl(L('page')), kv=KV([['key', 'URL(含查询串)+ 方法 + Vary 头']], ['key'])),
    step("Vary:自定义头 X-Device 加了 vary_on_headers 后,phone 与 desktop 各是一份(视图执行 2 次),再来 phone 命中缓存。但 Accept-Language 不同:USE_I18N=True 时 Django 不把它算进 key(改用当前激活的语言当后缀),没有 LocaleMiddleware 时 en 和 zh 都是默认语言——zh 请求拿到了 en 的缓存('lang 1 en',视图只执行 1 次)。", t=tl(L('vary')), n=fl([['X-Device: phone / desktop', '各一份'], ['Accept-Language: en / zh', '同一份(没有 LocaleMiddleware)']], done=[0], mark=[1]), kv=KV([['Accept-Language', 'USE_I18N 时不参与 key'], ['多语言站', '需要 LocaleMiddleware']], ['Accept-Language'])),
    step("不缓存的情况:POST 两次视图执行 2 次;返回 500 的响应不缓存(执行 2 次)。危险的是带 Set-Cookie 的响应:视图 set_cookie('sid') 后没有 Vary: Cookie,响应被缓存,视图只执行 1 次,第二次(缓存里)的响应仍带着同一个 Set-Cookie——所有用户会拿到同一个 cookie。", t=tl(L('nocache')), mark=[2], kv=KV([['带 Set-Cookie 的响应', '若被缓存会把同一个 cookie 发给所有人']], ['带 Set-Cookie 的响应'])),
    step("低级缓存:自己决定 key 和超时。id=1、1、2、1 四次请求只计算 2 次(id=1 一次、id=2 一次,其余命中);适合「一个视图里只有一部分昂贵」的场景。模板片段缓存 {% cache 60 sidebar user_id %}:user 1 第二次命中('[计算 1]'不变),user 2 是另一个 key;片段 key 形如 template.cache.sidebar.<哈希>(make_template_fragment_key 生成)。", t=tl(L('low') + L('frag')), kv=KV([['低级缓存', '自己定 key 与时间'], ['{% cache %}', '片段缓存,key 由名字 + 变量哈希']], ['低级缓存'])),
]
A = dict(
    n=95, series='django', tags='Django,缓存,cache_page,页面缓存,真实验证,动画演示',
    desc='实测页面缓存与低级缓存:cache_page 按 URL(含查询串)+ Vary 头区分,响应头带 Cache-Control: max-age;自定义头 Vary 有效,而 Accept-Language 在 USE_I18N 下不参与 key(没有 LocaleMiddleware 时 zh 拿到 en 的缓存);带 Set-Cookie 的响应被缓存会把同一 cookie 发给所有人;{% cache %} 片段缓存。',
    lead='cache_page 怎么决定缓存几份?哪些响应不会被缓存?带登录信息的页面会不会缓存串了?这篇分别试页面缓存、Vary、低级缓存和模板片段缓存,并复现两个容易出事故的情形。',
    facts=[('Accept-Language', 'USE_I18N=True 时不进缓存 key;没有 LocaleMiddleware,zh 与 en 共用一份缓存'), ('Set-Cookie', '视图设置 cookie 且没有 Vary: Cookie 的响应会被 cache_page 缓存,cookie 被重放给所有用户'), ('max-age=60', 'cache_page(60) 同时让响应带 Cache-Control: max-age=60')],
    body=[
        sec('cache_page', '', term('', blk('d95', 1)), '<p>装饰在视图上的整页缓存。key 包含完整 URL(含查询串),所以带跟踪参数的 URL 会各存一份。</p>'),
        sec('Vary', '', term('', blk('d95', 2)), '<p>需要按语言缓存时,要用 <code>LocaleMiddleware</code> 让语言激活;需要按登录用户缓存时,用 <code>vary_on_cookie</code>——更稳妥的做法是,对有用户个性化内容的页面不用整页缓存,改用片段缓存。</p>'),
        sec('不缓存与危险的情形', '', term('', blk('d95', 3)), '<p>读 Django 6.1.1 的缓存中间件源码:不缓存的情形有——流式响应、状态码不是 200/304、响应设置了 cookie 且 <code>Vary: Cookie</code>、<code>Cache-Control</code> 含 private / no-cache / no-store、<code>Vary: *</code>。视图只是 <code>set_cookie</code> 而没有 <code>Vary: Cookie</code> 时不在此列,所以会被缓存(上面的实测)。</p>'),
        sec('低级缓存', '', term('', blk('d95', 4)), term('', blk('d95', 5)), '<p>片段缓存的 key 由片段名和额外变量的哈希组成,变量里放用户 id 即可按用户区分。</p>'),
        sec('分步演示:页面缓存与低级缓存', '', demo('页面缓存', [('t', 'term', '实测输出'), ('n', 'flow', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。LocMemCache;django.test.Client', '没有验证:UpdateCacheMiddleware / FetchFromCacheMiddleware 整站缓存、Vary: Cookie 与 Cache-Control: private 时不缓存(只读了源码,没有实测)、cache_control 装饰器、ETag 与缓存的组合(第 23 篇)、CDN 层缓存'],
)
