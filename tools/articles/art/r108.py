import json
from lib import *
R = J('r108'); d = R['del']; f = R['flush']; e = R['exp']
dd, uu, dl = d['DEL(默认 lazyfree-lazy-user-del no)'], d['UNLINK'], d['DEL + lazyfree-lazy-user-del yes']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("Lazy free 的意思是:把「释放一个大对象的内存」这件耗时的事交给后台线程,主线程只做「摘下」这个 key。本机 Redis 8.10.2 里所有 lazyfree 配置默认都是 no:lazyfree-lazy-user-del、-eviction、-expire、-server-del、-user-flush 以及 replica-lazy-flush。", t=tm(['lazyfree-lazy-user-del      no', 'lazyfree-lazy-eviction       no', 'lazyfree-lazy-expire         no', 'lazyfree-lazy-server-del      no', 'lazyfree-lazy-user-flush     no', 'replica-lazy-flush           no'], mark=range(6)), kv=KV([['默认', '全部 no(本机实测)']], ['默认'])),
    step(f"释放一个 200 万成员的集合:DEL(默认)用了 {dd[0]:.0f} ms,同时另一个连接的 PING 最大停顿 {dd[1]:.0f} ms——主线程整段被占。UNLINK 只要 {uu[0]:.1f} ms、PING 停顿 {uu[1]:.1f} ms;INFO 里 lazyfreed_objects 增加 1。", b=bars([['DEL 命令耗时', dd[0], f'{dd[0]:.0f} ms'], ['DEL 时 PING 最大停顿', dd[1], f'{dd[1]:.0f} ms'], ['UNLINK 命令耗时', max(uu[0], 0.5), f'{uu[0]:.1f} ms']], dd[0], mark=[0, 1], done=[2]), kv=KV([['DEL vs UNLINK', f'{dd[0]:.0f} ms vs {uu[0]:.1f} ms']], ['DEL vs UNLINK'])),
    step(f"把 lazyfree-lazy-user-del 改成 yes,普通 DEL 的行为就等同 UNLINK:{dl[0]:.1f} ms、PING 停顿 {dl[1]:.1f} ms,lazyfreed_objects 计数继续增加。", b=bars([['DEL(默认)', dd[0], f'{dd[0]:.0f} ms'], ['DEL(lazy-user-del yes)', max(dl[0], 0.5), f'{dl[0]:.1f} ms']], dd[0], mark=[0], done=[1]), kv=KV([['lazy-user-del yes', 'DEL 变异步']], ['lazy-user-del yes'])),
    step(f"清库:FLUSHALL(300 万个小 key)命令耗时 {f['FLUSHALL'][0]:.0f} ms,FLUSHALL ASYNC 只要 {f['FLUSHALL ASYNC'][0]:.1f} ms。奇怪的是同步 FLUSHALL 期间另一个连接的 PING 最大停顿也只有 {f['FLUSHALL'][1]:.1f} ms——它在清空过程中仍然处理了别的连接的请求(原因我没有深究,推测是分批清空时会处理事件)。", b=bars([['FLUSHALL 耗时', f['FLUSHALL'][0], f"{f['FLUSHALL'][0]:.0f} ms"], ['FLUSHALL ASYNC 耗时', max(f['FLUSHALL ASYNC'][0], 0.5), f"{f['FLUSHALL ASYNC'][0]:.1f} ms"]], f['FLUSHALL'][0], mark=[0], done=[1]), kv=KV([['清库', f"{f['FLUSHALL'][0]:.0f} → {f['FLUSHALL ASYNC'][0]:.1f} ms"]], ['清库'])),
    step(f"过期:给 200 万成员的集合设 500 ms 过期。lazyfree-lazy-expire no 时,到期删除在主线程完成,另一个连接观察到 PING 最大停顿 {e['no']:.0f} ms;改成 yes 后最大停顿 {e['yes']:.1f} ms。key 都在到期后被删除。", b=bars([['lazy-expire no', e['no'], f"{e['no']:.0f} ms"], ['lazy-expire yes', max(e['yes'], 0.5), f"{e['yes']:.1f} ms"]], e['no'], mark=[0], done=[1]), kv=KV([['大 key 过期', f"{e['no']:.0f} → {e['yes']:.1f} ms 停顿"]], ['大 key 过期'])),
]
A = dict(
    n=108, series='redis', tags='Redis,Lazy Free,阻塞,真实验证,动画演示',
    desc=f'实测 Redis 8.10.2 的 Lazy Free:所有 lazyfree 配置默认 no;释放 200 万成员的集合,DEL {dd[0]:.0f} ms(另一个连接 PING 停顿 {dd[1]:.0f} ms),UNLINK {uu[0]:.1f} ms;lazyfree-lazy-user-del yes 让 DEL 变异步;FLUSHALL {f["FLUSHALL"][0]:.0f} ms vs ASYNC {f["FLUSHALL ASYNC"][0]:.1f} ms;大 key 过期时 lazyfree-lazy-expire no 造成 {e["no"]:.0f} ms 停顿,yes 只有 {e["yes"]:.1f} ms。',
    lead='大对象的内存释放是一个会阻塞主线程的操作:删掉一个大集合,别的客户端就得等。Lazy Free 把释放挪到后台线程。这篇不重复 DEL 与 UNLINK 的区别(第 19 篇),而是量各个 lazyfree 开关到底改变了什么,包括默认值(在这个版本上出乎意料)和「过期删除」这条容易被忽略的路径。',
    facts=[('默认全是 no', '本机 8.10.2 上所有 lazyfree-* 配置默认 no'), (f'{dd[0]:.0f} → {uu[0]:.1f} ms', '释放 200 万成员的集合:DEL(默认)→ UNLINK'), (f'{e["no"]:.0f} → {e["yes"]:.1f} ms', '大 key 过期时另一个连接 PING 的最大停顿:lazy-expire no → yes')],
    body=[
        sec('默认值', '', term('', blk('r108', 1)), '<p>这个版本(8.10.2)上,所有相关的开关默认都是 <code>no</code>。也就是说不做任何配置时,<code>DEL</code>、过期删除、淘汰、清库都在主线程里同步释放内存。(不同版本的默认值可能不同,以 <code>CONFIG GET</code> 为准。)</p>'),
        sec('DEL、UNLINK 与 lazy-user-del', '', term('', blk('r108', 2)), f'<p>200 万成员的集合(<code>used_memory</code> 约 61 MB)。默认 <code>DEL</code>:{dd[0]:.0f} ms,另一个连接的 PING 停顿 {dd[1]:.0f} ms;<code>UNLINK</code> 或者开了 <code>lazyfree-lazy-user-del yes</code> 的 <code>DEL</code>:不到 1 ms。<code>INFO memory</code> 里的 <code>lazyfreed_objects</code> 记录被后台释放的对象数。</p>'),
        sec('FLUSHALL', '', term('', blk('r108', 3)), f'<p>300 万个小 key:<code>FLUSHALL</code> 命令本身 {f["FLUSHALL"][0]:.0f} ms,<code>FLUSHALL ASYNC</code> {f["FLUSHALL ASYNC"][0]:.1f} ms。有意思的是,同步 FLUSHALL 期间另一个连接的 PING 停顿也只有 {f["FLUSHALL"][1]:.1f} ms——说明清库不是一次性阻塞到底(我没有查是不是分批清空时处理了事件)。所以清库和删单个大 key 的阻塞形态不同。</p>'),
        sec('过期:被忽略的一条路径', '', term('', blk('r108', 4)), f'<p>给大集合设 500 ms 过期。<code>lazyfree-lazy-expire no</code>:到期时主线程同步释放,观察到另一个连接 PING 最大停顿 {e["no"]:.0f} ms;<code>yes</code>:{e["yes"]:.1f} ms。这就是「大 key 过期造成周期性抖动」的来源(第 20、27 篇)。</p>'),
        sec('分步演示:哪些操作会被异步化', '', demo('Redis Lazy Free', [('t', 'term', '配置'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。集合 200 万成员;PING 每 0.5 ms 一次;每个配置一次测量(差别是几十倍,不需要重复)', '没有验证:lazyfree-lazy-eviction / lazyfree-lazy-server-del 的效果、replica-lazy-flush、后台释放线程本身占用 CPU 的代价、更大对象(GB 级)下的行为'],
)
