from lib import *
R = J('d94'); rk = R['redis_keys']
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step(f"make_key 的规则是 前缀:版本:key:KEY_PREFIX='shop'(默认版本 1)→ shop:1:user:1;不设前缀 → :1:user:1(前缀为空);再看 Redis 里真实存的 key:db0 {rk['0']},db1 {rk['1']},db2 {rk['2']}。KEY_FUNCTION 可以完全自定义(本例 k|v3|user:1)。", t=tl(L('make') + [f'Redis db{db} 里的 key:{rk[str(db)]}' for db in (0, 1, 2)], cur=[0, 1, 2]), kv=KV([['默认', '前缀:版本:key'], ['KEY_FUNCTION', '可完全自定义']], ['默认'])),
    step("version:同一个 key 名,不同版本互不可见:version=1 与 version=2 各存了 v1、v2,默认版本读到 v1,version=2 读到 v2,version=3 读到 None。incr_version('k') 把 k 从 v1 版本搬到 v2 版本(返回 2),旧的 v2 被覆盖,version=1 之后是 None——整体递增 VERSION 配置项可以「批量作废」一个应用的所有缓存。", t=tl(L('version')), kv=KV([['VERSION', '整体换版本 = 批量作废旧缓存']], ['VERSION'])),
    step("key 的限制:含空格、控制字符或超过 250 字符 → CacheKeyWarning(2 条:含不能用于 memcached 的字符;key 过长)。Redis 后端并不受这些限制,get 仍然读到 1;警告的目的是让你在换到 memcached 之前发现问题。", t=tl(L('limits')[:2]), kv=KV([['CacheKeyWarning', '只是警告,Redis 上照常工作']], ['CacheKeyWarning'])),
    step("隔离:同一个后端、同一个 KEY_PREFIX 下,两个应用写同名 key 会互相覆盖(from-app-A → from-app-B);不同 KEY_PREFIX 的缓存互相隔离(default 读到 from-app-B,custom 读到 None)。多个项目共用一个 Redis 时必须用不同的 KEY_PREFIX(或不同 db)。", t=tl(L('collide')), kv=KV([['共享 Redis', '各项目要有不同的 KEY_PREFIX']], ['共享 Redis'])),
]
A = dict(
    n=94, series='django', tags='Django,缓存,Cache Key,Redis,真实验证,动画演示',
    desc='直接看 Redis 里的 key 实测缓存 key 生成规则:前缀:版本:key(shop:1:user:1);KEY_FUNCTION 自定义;version 与 incr_version;含空格 / 过长 key 触发 CacheKeyWarning(Redis 上照常工作);同前缀同 key 的不同应用会互相覆盖。',
    lead='cache.set("user:1", ...) 在 Redis 里到底存成什么 key?version 有什么用?key 有什么限制?多个项目共用一个 Redis 会不会互相踩?这篇直接看 Redis 里的 key。',
    facts=[('shop:1:user:1', 'KEY_PREFIX=shop、VERSION=1 时,cache.set("user:1") 在 Redis 里的 key'), ('VERSION', '整体递增 VERSION 可以批量作废旧缓存'), ('共用 Redis', '不同项目必须用不同 KEY_PREFIX,否则同名 key 互相覆盖')],
    body=[
        sec('key 的组成', '', term('', blk('d94', 1)), '<p>缓存后端调用 <code>make_key(key, version)</code>。所以在 <code>redis-cli</code> 里排查缓存时,要带上前缀和版本号。</p>'),
        sec('version', '', term('', blk('d94', 2)), '<p>做代码升级时,如果新旧版本缓存的数据结构不兼容,提高 <code>VERSION</code>(或者在 key 里带版本)可以避免读到旧格式。</p>'),
        sec('key 的限制', '', term('', blk('d94', 3)), '<p>用户输入做 key 时要清洗(空格、过长):比如把用户名 <code>md5</code> 一下再放进 key。</p>'),
        sec('隔离', '', term('', blk('d94', 4)), '<p>另外,<code>cache.clear()</code> 在共享 Redis 库上会清空整个数据库(本文没有测),生产里慎用。</p>'),
        sec('分步演示:缓存 key', '', demo('缓存 Key', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。Redis 8.10.2 本机临时实例(端口 9462);key 用 redis-cli 风格的 KEYS 查看', '没有验证:memcached 的 key 限制实际报错、KEY_FUNCTION 在多进程中的稳定性、Redis Cluster 下的 key 分布、cache.clear() 的具体行为'],
)
