from lib import *
R = J('d93'); pf = R['perf']; sh = R['share']; rs = R['restart']
ks = list(pf)
steps = [
    step("五种读写的耗时(1000 次中位数,进程内直接调用,值 200 字节):" + ';'.join(f"{k} set {pf[k]['set']:.0f} / get {pf[k]['hit']:.0f} µs" for k in ks) + "。LocMem 最快(同进程内存);file、db 的读很快(本机文件 / SQLite),写慢一个数量级;redis 每次都要一次本机网络往返(≈90 µs)。这是本机回环、无网络延迟的数字。", b=bars([[f'{k} get(µs)', pf[k]['hit'], f"{pf[k]['hit']:.1f}"] for k in ks], max(pf[k]['hit'] for k in ks) * 1.1, done=[0], mark=[3]), kv=KV([['读', f"locmem {pf['locmem']['hit']:.1f} µs … redis {pf['redis']['hit']:.0f} µs"], ['写', f"db {pf['db']['set']:.0f} µs / file {pf['file']['set']:.0f} µs"]], ['读'])),
    step(f"多个 worker 进程是否共享:gunicorn 2 个 worker,一个请求 set,再 20 次读:locmem 只有 {sh['locmem']['seen']}/20 次读到(每个 worker 有自己的一份内存,读到哪个 worker 全看运气);db、file、redis 都是 20/20。多进程部署下 LocMem 会造成「有时命中有时不命中」,而且各 worker 的缓存互不知道对方的失效。", b=bars([[f'{k} 命中(共 20 次)', sh[k]['seen'], f"{sh[k]['seen']}/20"] for k in ks], 20, mark=[0], done=[1, 2, 3]), kv=KV([['LocMem', f"{sh['locmem']['seen']}/20(每个进程一份)"], ['db / file / redis', '20/20']], ['LocMem'])),
    step("重启后是否保留:写入后停服务再起:locmem 丢失;db、file、redis 保留(本次 Redis 没有开持久化也保留了,因为没有重启 Redis 进程,重启的只是 Django——Redis 自己重启时是否丢数据取决于它的持久化配置,没有测)。", t=tl([f"{k}:{'保留' if rs[k] else '丢失'}" for k in ks], mark=[0], done=[1, 2, 3]), kv=KV([['Django 重启', 'locmem 丢,其它保留']], ['Django 重启'])),
    step("LocMem 的容量:MAX_ENTRIES 默认 300,写入 500 个 key 后只剩 300 个;最早写入的 k0 已被淘汰(None),最新的 k499 还在。超过上限按 CULL_FREQUENCY 淘汰一部分,不是严格的 LRU。", t=tl(R['locmem_cap'].splitlines()), kv=KV([['LocMem 上限', '默认 300 条']], ['LocMem 上限'])),
]
A = dict(
    n=93, series='django', tags='Django,缓存,LocMem,Redis,gunicorn,真实验证,动画演示',
    desc=f'对比四种缓存后端:读写耗时(locmem get {pf["locmem"]["hit"]:.1f} µs、redis get {pf["redis"]["hit"]:.0f} µs、db set {pf["db"]["set"]:.0f} µs);gunicorn 两个 worker 下 LocMem 只命中 {sh["locmem"]["seen"]}/20,其它后端 20/20;Django 重启后 LocMem 丢失;LocMem 默认最多 300 条。',
    lead='LocMem、数据库、文件、Redis 四种缓存后端到底差在哪?多进程下能共享吗?重启后还在吗?这篇在本机把它们并排跑一遍,包括真实的 gunicorn 双 worker 场景。',
    facts=[(f'{sh["locmem"]["seen"]}/20', 'gunicorn 2 个 worker 下 LocMem 的命中(每个 worker 一份缓存);其它后端 20/20'), (f'{pf["locmem"]["hit"]:.1f} vs {pf["redis"]["hit"]:.0f} µs', 'LocMem 与 Redis 一次 get 命中的耗时(本机回环)'), ('300', 'LocMem 默认 MAX_ENTRIES:写 500 个只剩 300 个')],
    body=[
        sec('速度', '', term('', blk('d93', 1)), '<p>只是一次调用的延迟。Redis 的价值不在单次快,而在「多进程共享、可以独立扩容、支持过期与内存上限」。</p>'),
        sec('进程间共享', '', term('', blk('d93', 2)), '<p>这是 LocMem 最大的坑:开发时单进程一切正常,上线用 gunicorn 多 worker 后缓存表现「不稳定」。缓存失效只发生在当前 worker,别的 worker 继续返回旧值。</p>'),
        sec('重启', '', term('', blk('d93', 3)), '<p>持久性只对「缓存后端本身」有意义:Django 进程重启,共享后端里的缓存仍在。</p>'),
        sec('LocMem 的容量', '', term('', blk('d93', 4)), '<p>可以用 <code>OPTIONS: {MAX_ENTRIES: ..., CULL_FREQUENCY: ...}</code> 调整(本文没有测调整后的结果)。</p>'),
        sec('分步演示:四种后端', '', demo('缓存后端对比', [('b', 'bars', '数据'), ('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。Redis 8.10.2 本机临时实例(端口 9460);gunicorn 26.2,2 worker;耗时为 1000 次中位数', '没有验证:Memcached 后端、跨机器网络下的 Redis 延迟、Redis 缓存的内存上限与淘汰策略(第 98 篇部分涉及)、django-redis 等第三方后端、db 缓存表的清理'],
)
