from lib import *
S = SS('f75')
R = J('f75'); lat = R['lat']; st = R['stampede']
steps = [
    step("@cache.cached(timeout=2):第一次请求 54 ms(计算),后两次各 1 ms(命中,返回同一个 call#1);2.2 秒后过期,重新计算得到 call#2(56 ms)。没加装饰器的 /plain 每次都计算(call#3、call#4)。", t=tl(S(1)), done=lidx(S(1), '连续 3 次', '过期后'), mark=lidx(S(1), '/plain'), kv=KV([['命中', '1 ms'], ['未命中', '约 55 ms'], ['过期', '2 秒后重算']], ['命中'])),
    step("查询参数默认不进缓存键:/qs-ignored?a=1 与 ?a=2 返回同一份(都是 a=1 的结果);加 query_string=True 后才按参数区分(a=1 与 a=2 各自计算)。用户相关或带参数的页面忘了这一点会串数据。", t=tl(S(2)), mark=lidx(S(2), '默认'), done=lidx(S(2), 'query_string=True'), kv=KV([['默认', '忽略查询参数'], ['query_string=True', '按参数区分']], ['默认'])),
    step("memoize 按函数参数分别缓存:memo(1)、memo(1)、memo(2)、memo(1, y=5) 里只有第二次命中,其余各算一次;delete_memoized(compute, 1) 之后 memo(1) 重新计算(call#4),而 memo(1, y=5) 仍然命中(call#3)——它按参数组合精确清除。", t=tl(S(3)), done=lidx(S(3), 'delete_memoized'), kv=KV([['memoize', '按参数组合缓存'], ['delete_memoized', '按参数精确清除']], ['delete_memoized'])),
    step("后端不同,存储位置不同:RedisCache 里有键 lab_view//cached(TTL 2 秒,值是 pickle 序列化的字节,以 !\\x80\\x05 开头)、lab_app.compute_memver 和一个 memoize 的版本键;FileSystemCache 在目录里每个键一个文件(这里 2 个文件)。", t=tl(S(4)), done=lidx(S(4), 'redis 里的键', '视图缓存键', 'FileSystemCache'), kv=KV([['RedisCache', '键 + TTL + pickle 值'], ['FileSystemCache', '一个键一个文件']], ['RedisCache'])),
    step("3 个 gunicorn worker、12 个相同请求:SimpleCache 是进程内的,各 worker 各算各的,这次响应来自 2 个不同的进程,内容有 2 种(被计算了 2 次);RedisCache 共享,只有 1 种内容(计算 1 次)。", t=tl(S(5)), mark=lidx(S(5), 'SimpleCache'), done=lidx(S(5), 'RedisCache'), kv=KV([['SimpleCache', '每个 worker 一份'], ['RedisCache', '所有 worker 共享']], ['SimpleCache'])),
    step(f"缓存击穿:缓存刚过期时 8 个并发请求同时到达,Flask-Caching 没有锁,慢计算(0.3 秒)被执行了 {st[0]} 次(总耗时 {st[1]} 秒)。热点 key 过期的瞬间,后端会被打 N 次。", t=tl(S(6)), mark=lidx(S(6), '8 个并发'), kv=KV([['并发 8 个请求', f'计算 {st[0]} 次'], ['防护', '需要自己加锁或提前刷新']], ['并发 8 个请求'])),
    step(f"耗时对比(慢计算 50 ms):未命中中位数 {lat[0]:.1f} ms,命中中位数 {lat[1]:.2f} ms,差约 {lat[0] / lat[1]:.0f} 倍(都是 SimpleCache,经 gunicorn 的 HTTP 请求)。", b=bars([['未命中', lat[0], f'{lat[0]:.1f} ms'], ['命中', lat[1], f'{lat[1]:.2f} ms']], 60, mark=[0], done=[1]), t=tl(S(7)), done=lidx(S(7), '命中'), kv=KV([['未命中', f'{lat[0]:.1f} ms'], ['命中', f'{lat[1]:.2f} ms']], ['命中'])),
]
A = mkartf('f75', 75, 'Flask,Flask-Caching,缓存,Redis,真实验证,动画演示',
    f'实测 Flask-Caching:cached 的命中与过期、查询参数默认不参与缓存键、memoize 与 delete_memoized、RedisCache 里的键与 TTL、FileSystemCache 的文件、多 worker 下 SimpleCache 各算各的、缓存击穿时 8 个并发请求计算 {st[0]} 次、命中 {lat[1]:.2f} ms 对未命中 {lat[0]:.1f} ms。',
    'Flask-Caching 的缓存键是怎么来的?查询参数会不会串?多 worker 部署时 SimpleCache 还管用吗?缓存刚过期时并发请求会怎样?这篇用真实的 gunicorn、自己起的 redis 和计时把这些逐项量出来。',
    [(f'{lat[0]:.0f} → {lat[1]:.1f} ms', '未命中与命中的请求耗时(慢计算 50 ms)'), ('2 个进程', '3 个 worker 下 SimpleCache 这次在 2 个进程里各算了一次'), (f'{st[0]} 次', '缓存过期瞬间 8 个并发请求触发的慢计算次数')],
    [('cached 的命中与过期', '<p>上一篇:<a href="flask-flask-migrate-basics.html">Flask-Migrate 基础</a>;下一篇:<a href="flask-flask-limiter.html">Flask-Limiter</a>。</p>'), ('查询参数与缓存键', None), ('memoize', None), ('后端存储', '<p>本篇的 redis 是自己在非默认端口起的临时实例,验证完就关掉了。</p>'), ('多个 worker', None), ('缓存击穿', '<p>实验里响应正文里的 call 编号看起来都一样,是因为我的计数器在慢计算结束后才读取,所以这里只用「计算被执行了几次」这个计数,不用响应内容判断。</p>'), ('命中与未命中的耗时', None)],
    steps, [ENV_F + '。Flask-Caching 2.5.1、redis-py 8.1.0、自己起的 redis(非默认端口)', '没有验证:Memcached 后端、cache.cached 的 unless/make_cache_key 自定义、CACHE_KEY_PREFIX 在多应用共用 redis 时的冲突、缓存雪崩、加锁防击穿的具体方案'], 'Flask-Caching', panels=[('t', 'term', '实验输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')])
