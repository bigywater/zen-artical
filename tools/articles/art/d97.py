from lib import *
import re
R = J('d97')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
sw = L('swr')
def stats(l): 
    m = re.search(r'请求 (\d+) 次;计算 (\d+) 次;p50 ([\d.]+) ms;p99 ([\d.]+) ms;最慢 (\d+) ms', l); return [float(x) for x in m.groups()]
bl = stats(sw[0]); sr = stats(sw[1])
steps = [
    step("get_or_set 不是「并发下只算一次」:20 个线程同时对一个不存在的 key 调用 get_or_set('k', lambda: compute(), 60),compute 被执行了 20 次(每个线程都发现没有、都算了一遍),最后缓存里留下其中一个结果(result-2),所有线程返回的值也相同——因为 get_or_set 的写入用的是 add,先到者赢。", t=tl(L('get_or_set')), kv=KV([['get_or_set', '并发时每个线程都会计算']], ['get_or_set'])),
    step("用 cache.add 做互斥:拿到锁的线程计算并写缓存,其它线程轮询等待;compute 只执行 1 次,20 个线程都拿到同一个值,总耗时约 110 ms(≈一次计算 + 等待)。", t=tl(L('lock')), kv=KV([['add 当互斥锁', '只算一次']], ['add 当互斥锁'])),
    step(f"过期瞬间的等待:计算要 200 ms、TTL 1 秒,4 个线程持续请求 4 秒。阻塞式回源:p99 {bl[3]:.0f} ms(每次过期都有请求要等 200 ms),共计算 {int(bl[1])} 次;stale-while-revalidate(过期后先返回旧值、后台刷新):p99 只有 {sr[3]:.1f} ms,共计算 {int(sr[1])} 次;最慢那次仍是 {sr[4]:.0f} ms(第一次冷启动还是要等)。", b=bars([['阻塞式 p99(ms)', bl[3], f"{bl[3]:.0f}"], ['SWR p99(ms)', sr[3], f"{sr[3]:.1f}"]], bl[3] * 1.1, mark=[0], done=[1]), kv=KV([['p99', f"{bl[3]:.0f} → {sr[3]:.1f} ms"], ['计算次数', f"{int(bl[1])} → {int(sr[1])}"]], ['p99'])),
    step("两个 TTL 相关的细节:每次 set 都会重置过期时间(2 秒的 key,1.2 秒后再 set,又过 1.2 秒——距第一次 2.4 秒——仍在);读-改-写是竞态:线程 A 读到 v0、睡 0.3 秒,期间线程 B 写了 v1-from-other,A 写回 v0+writer,B 的写入被覆盖(lost update)。缓存里做「读-改-写」要用 incr 或加锁。", t=tl(L('ttl')), kv=KV([['set', '重置 TTL'], ['读-改-写', '会丢更新']], ['读-改-写'])),
]
A = dict(
    n=97, series='django', tags='Django,缓存,过期时间,并发,真实验证,动画演示',
    desc=f'实测缓存过期与并发:get_or_set 20 线程并发时 compute 执行 20 次;cache.add 互斥只算 1 次;计算 200 ms、TTL 1 秒时阻塞式回源 p99 {bl[3]:.0f} ms,stale-while-revalidate p99 {sr[3]:.1f} ms;set 重置 TTL;缓存里读-改-写会 lost update。',
    lead='缓存失效瞬间,请求会怎样?get_or_set 能保证只算一次吗?怎么让用户感觉不到回源的等待?这篇用线程并发,把这几个问题都数出来。',
    facts=[('20 次', '20 个线程并发 get_or_set 同一个不存在的 key,compute 被执行 20 次'), (f'{bl[3]:.0f} → {sr[3]:.1f} ms', '阻塞式回源 vs stale-while-revalidate 的 p99(计算 200 ms、TTL 1 秒)'), ('lost update', '缓存里的读-改-写不是原子的:并发写入会被覆盖')],
    body=[
        sec('get_or_set 与并发', '', term('', blk('d97', 1)), '<p>各线程各自 <code>get</code> 不到、各自计算、最后 <code>add</code> 只有第一个成功——所以结果一致,但计算重复了。</p>'),
        sec('用 add 做互斥', '', term('', blk('d97', 2)), '<p>同第 96 篇的击穿防护,锁要带过期时间。</p>'),
        sec('过期瞬间的等待', '', term('', blk('d97', 3)), '<p>stale-while-revalidate 的做法:缓存里的值带一个「软过期时间」,硬 TTL 比它长得多;读到过期(软)的值时先原样返回,同时让一个线程去刷新。本文的实现是单进程内的简化版(用一个标志位防止重复刷新),多进程要用缓存里的锁。</p>'),
        sec('TTL 与竞态', '', term('', blk('d97', 4)), '<p>要原子地累加用 <code>cache.incr</code>;要保证「只有一个人在改」需要锁。</p>'),
        sec('分步演示:失效与并发', '', demo('缓存失效与并发', [('t', 'term', '输出'), ('b', 'bars', 'p99'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。LocMemCache + 线程;compute 用 sleep 模拟耗时', '没有验证:Redis 后端下的 get_or_set、多进程 SWR、cache.incr 在各后端的原子性、Redis 的 SET NX EX 锁的可靠性边界'],
)
