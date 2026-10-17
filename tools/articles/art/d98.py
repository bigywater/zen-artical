from lib import *
R = J('d98'); fl = R['flush']; ev = R['evict']; lt = R['lat']
steps = [
    step(f"cache 会话后端 + Redis:登录后 Redis 里有一个 key {R['keys'][0][:48]}…(格式:缓存前缀 :1: + django.contrib.sessions.cache + session_key);TTL = {R['ttl']} 秒 = 14 天(SESSION_COOKIE_AGE);值是 pickle 序列化的字典(前几个字节 \\x80\\x05\\x95…)。", t=tl([f"Redis key: {R['keys'][0]}", f"TTL = {R['ttl']} 秒", f"值的前 40 字节:{R['val_head']}"]), kv=KV([['key', ':1:django.contrib.sessions.cache<session_key>'], ['TTL', '= SESSION_COOKIE_AGE']], ['key'])),
    step(f"Redis 被清空(FLUSHALL,相当于重启且没有持久化)后:cache(Redis)后端 → {fl['cache(Redis)'].split(': ',1)[-1]}(所有用户被登出);cached_db(Redis + 数据库)→ {fl['cached_db(Redis+DB)'].split(': ',1)[-1]}(缓存没了,回源数据库,仍是登录状态);db 后端 → {fl['db'].split(': ',1)[-1]}。session 只放缓存,缓存的丢失就是登出。", t=tl([f"cache(Redis):{fl['cache(Redis)'].split('之后:')[-1]}", f"cached_db:{fl['cached_db(Redis+DB)'].split('之后:')[-1]}", f"db:{fl['db'].split('之后:')[-1]}"], mark=[0], done=[1, 2]), kv=KV([['cache', 'Redis 丢数据 = 全员登出'], ['cached_db', '不受影响']], ['cache'])),
    step(f"内存淘汰(maxmemory=2mb + allkeys-lru,再写入约 3 MB 的其它 key):cache(Redis)后端的 session 被当作普通缓存淘汰(该会话在 Redis 里: False),再访问 → {ev['cache(Redis)'].split(': ',1)[-1]};cached_db 后端同样被淘汰出 Redis,但回源数据库,仍是登录用户 u。缓存服务器的淘汰策略不区分 session 与普通缓存。", t=tl([f"cache(Redis):{ev['cache(Redis)']}", f"cached_db:{ev['cached_db(Redis+DB)']}"], mark=[0], done=[1]), kv=KV([['allkeys-lru', '会把 session 一起淘汰'], ['解决', 'session 单独一个 Redis / 用 cached_db']], ['allkeys-lru'])),
    step(f"性能:三种后端每个请求的耗时(300 次中位,含测试客户端开销):cache(Redis){lt['cache(Redis)']:.3f} ms、cached_db {lt['cached_db(Redis+DB)']:.3f} ms、db {lt['db']:.3f} ms——差别在噪音之内(本机 SQLite 很快;换成远程数据库,db 后端才会明显变慢)。", b=bars([[k, v, f"{v:.3f}"] for k, v in lt.items()], max(lt.values()) * 1.2, done=[0, 1, 2]), kv=KV([['本机', '三者无明显差异']], ['本机'])),
]
A = dict(
    n=98, series='django', tags='Django,session,Redis,缓存,真实验证,动画演示',
    desc=f'实测用 Redis 缓存 session:key 格式 :1:django.contrib.sessions.cache<key>、TTL 14 天、pickle 值;Redis 被清空后 cache 后端全员登出而 cached_db 不受影响;maxmemory + allkeys-lru 会把 session 一起淘汰;本机三种后端每请求耗时 {lt["cache(Redis)"]:.2f} / {lt["cached_db(Redis+DB)"]:.2f} / {lt["db"]:.2f} ms(无差异)。',
    lead='把 session 放进 Redis 能提速,但代价是什么?Redis 重启或淘汰了 key,用户会不会被登出?这篇在本机 Redis 上直接看 session 的存储形态,并做「清空」和「内存淘汰」两个破坏性实验(用的是本次实验自己起的 Redis,没有碰任何其它实例)。',
    facts=[(f'{R["ttl"]} 秒', 'Redis 里 session key 的 TTL = SESSION_COOKIE_AGE(14 天)'), ('全员登出', 'cache 会话后端 + Redis 被清空或淘汰 key 时,对应用户登出;cached_db 后端回源数据库不受影响'), ('allkeys-lru', 'Redis 的淘汰策略不区分 session 与其它缓存,内存吃紧时 session 一起被淘汰')],
    body=[
        sec('session 在 Redis 里的样子', '', term('', blk('d98', 1)), '<p>本实验用的是 Django 6.1 自带的 <code>RedisCache</code>(需要 <code>redis</code> 客户端库),序列化用 pickle。要在 <code>redis-cli</code> 里找 session,用 <code>KEYS *django.contrib.sessions*</code>(生产环境别用 <code>KEYS</code>,用 <code>SCAN</code>)。</p>'),
        sec('Redis 丢数据时', '', term('', blk('d98', 2)), '<p>选择 <code>cache</code> 后端就等于把「登录状态」当作可丢的缓存。可以接受的场景(登出后重新登录成本低)才用;否则用 <code>cached_db</code>。</p>'),
        sec('内存淘汰', '', term('', blk('d98', 3)), '<p>同一个 Redis 既存页面缓存又存 session 时,页面缓存把内存挤满会淘汰 session。把 session 放到单独的 Redis(或 db),并且给它设 <code>noeviction</code> 之类的策略(本文没有测)。</p>'),
        sec('性能', '', term('', blk('d98', 4)), '<p>本机数字没有区别,不能据此说「Redis 不快」——只说明当 session 表很小、数据库在本机时,数据库后端的开销并不大。</p>'),
        sec('分步演示:Redis 里的 session', '', demo('Redis 缓存 Session', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。Redis 8.10.2 本机临时实例(端口 9463),FLUSHALL 与 maxmemory 只作用在这个实例上', '没有验证:Redis 持久化(AOF / RDB)对 session 的保护、Sentinel / Cluster 下的 session、django-redis 库的行为、session 序列化器选择(JSON)、高并发下的延迟'],
)
