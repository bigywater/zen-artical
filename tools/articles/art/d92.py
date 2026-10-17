from lib import *
R = J('d92')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("基本 API:set / get(不存在返回 None 或指定的默认值);add 只在 key 不存在时写入(已存在返回 False,值不变);get_or_set 第一次计算并存,第二次直接返回(lambda 不再执行);incr / decr 做原子增减,key 不存在 → ValueError: Key ':1:missing' not found;get_many / set_many 批量;delete 返回是否真删了;touch 重置过期时间(不存在返回 False)。", t=tl(L('api')), kv=KV([['add', '不覆盖'], ['incr', 'key 不存在会 ValueError']], ['incr'])),
    step("timeout 的语义:默认 300 秒(未配置 TIMEOUT 时);timeout=1 秒,1.1 秒后 get = None;timeout=0 立刻 get = None(等于不缓存);timeout=None 永不过期;负数立即过期;touch 可以延长:timeout=2 的 key,1 秒后 touch(5),再过 1.5 秒(总 2.5 秒)仍然在。", t=tl(L('timeout')), kv=KV([['0', '不缓存'], ['None', '永不过期']], ['0'])),
    step("falsy 值:0、''、None、False 都能存;get 拿回 0 / '' / None / False,与「没有这个 key」的 None 容易混淆——has_key 能区分;用哨兵对象作默认值也不行:存了 None 时 get('none', sentinel) 返回 None 而不是哨兵(判断 is sentinel 为 False),所以「值可能就是 None」时要用 has_key。", t=tl(L('falsy')), kv=KV([['值就是 None', 'get 无法区分「没有」'], ['has_key', '能区分']], ['has_key'])),
    step("值存的是序列化(pickle)后的副本(LocMem 也是):set 之后再修改原对象,缓存里的仍是 {'items': [1, 2]};取出后修改它,再次取还是原来的;不能 pickle 的对象直接 TypeError。所以不要指望「改了对象缓存就跟着变」。", t=tl(L('pickle')), kv=KV([['取出的是副本', '改了不影响缓存']], ['取出的是副本'])),
]
A = dict(
    n=92, series='django', tags='Django,缓存,Cache Framework,真实验证,动画演示',
    desc='实测 Django 缓存框架的基本行为:add 不覆盖、get_or_set、incr 对不存在的 key 抛 ValueError、touch 重置过期时间;timeout 的 0 / None / 负数语义;get 无法区分「没有」与「值为 None」(用 has_key);值以 pickle 副本存取。',
    lead='cache.set / get 谁都会用,但 timeout=0 是什么意思?incr 遇到不存在的 key 怎么办?存了 None 怎么区分?改了取出的对象会影响缓存吗?这篇把这些边界一个个试出来。',
    facts=[('timeout=0', '不缓存(立刻 get 得到 None);None 是永不过期;默认 300 秒'), ('incr', '对不存在的 key 抛 ValueError,不会自动创建'), ('副本', '存取都是 pickle 副本,取出后修改不影响缓存')],
    body=[
        sec('基本 API', '', term('', blk('d92', 1)), '<p>本文用 LocMem 后端(本进程内存)演示 API;不同后端在 <code>incr</code> 原子性、序列化格式上可能有差异,见第 93 篇。</p>'),
        sec('过期时间', '', term('', blk('d92', 2)), '<p>timeout 单位是秒。最常见的误用是把「不过期」写成 <code>timeout=0</code>——实际是「不缓存」。</p>'),
        sec('falsy 值', '', term('', blk('d92', 3)), '<p>缓存空结果时常用一个特殊标记值,或者用 <code>has_key</code>(会多一次往返)。</p>'),
        sec('序列化', '', term('', blk('d92', 4)), '<p>放进缓存的对象要能 pickle。放模型实例会连带它的 <code>_state</code> 一起序列化,取出后是「一份旧快照」。</p>'),
        sec('分步演示:缓存 API', '', demo('缓存 API', [('t', 'term', '实测输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。LocMemCache;超时测试用真实 sleep', '没有验证:incr 在各后端上的原子性、get_or_set 的竞态(第 96、97 篇)、cache.clear() 对共享 Redis 库的危险、cache.delete_many / decr 的其它边界、异步缓存 API(aget 等)'],
)
