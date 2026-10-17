import json
from lib import *
R = J('r115'); fq = R['freq']; sh_ = {int(k): v for k, v in R['shard'].items()}; tot = sum(sh_.values())
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
hot = R['hot']
steps = [
    step("构造负载:10 万个普通 key + 两个热 key;50 万次 GET,hot:1 占 30%、hot:2 占 10%,其余 60% 均匀落在 10 万个普通 key 上(每个约 3 次)。maxmemory-policy 设成 allkeys-lfu,让 Redis 记录访问频率。", t=tm(['hot:1  30%(约 15 万次)', 'hot:2  10%(约 5 万次)', '其余 10 万个 key 均匀,各约 3 次']), kv=KV([['策略', 'allkeys-lfu']], ['策略'])),
    step(f"OBJECT FREQ 是 LFU 的对数访问频率计数器(0–255):hot:1 = {fq['hot:1'][0]}(真实访问 {fq['hot:1'][1]} 次),hot:2 = {fq['hot:2'][0]}({fq['hot:2'][1]} 次),普通 key 约 {fq['k:1'][0]}(约 {fq['k:1'][1]} 次)。计数器是对数的:hot:1 与 k:1 的访问次数相差约 {int(fq['hot:1'][1]/max(fq['k:1'][1],1)/1000)} 千倍,计数只差 {float(fq['hot:1'][0])/float(fq['k:1'][0]):.0f} 倍。", b=bars([['hot:1', float(fq['hot:1'][0]), f"FREQ {fq['hot:1'][0]}({fq['hot:1'][1]} 次)"], ['hot:2', float(fq['hot:2'][0]), f"FREQ {fq['hot:2'][0]}({fq['hot:2'][1]} 次)"], ['k:1', float(fq['k:1'][0]), f"FREQ {fq['k:1'][0]}({fq['k:1'][1]} 次)"]], 255, mark=[0, 1]), kv=KV([['OBJECT FREQ', f"{fq['hot:1'][0]} / {fq['hot:2'][0]} / {fq['k:1'][0]}"]], ['OBJECT FREQ'])),
    step("redis-cli --hotkeys 扫全库读每个 key 的 OBJECT FREQ,按计数从高到低列出:hot:1 counter 194、hot:2 counter 105,然后是一大批 counter 9 的普通 key。约 2.4 s 扫完 10 万个 key(-i 0.01)。热 key 在计数上立刻与普通 key 拉开。", t=tm([l.strip() for l in hot if 'hot key found' in l][:5]), kv=KV([['hotkeys', 'hot:1 194 > hot:2 105 > 其余 9']], ['hotkeys'])),
    step("--hotkeys 依赖 LFU 计数:把 maxmemory-policy 改成 noeviction 后,redis-cli --hotkeys 直接报错「ERR An LFU maxmemory policy is not selected, access frequency not tracked」,OBJECT FREQ 也是同样的错误。要用这个工具,得先启用 LFU 策略,并且切换策略后计数需要一段时间才准确(报错里也这么说)。", t=tm(["> redis-cli --hotkeys", "Error: ERR An LFU maxmemory policy is not selected, access frequency not tracked.", "> OBJECT FREQ hot:1", "(error) ERR An LFU maxmemory policy is not selected …"], mark=[1, 3]), kv=KV([['前提', 'maxmemory-policy = *lfu']], ['前提'])),
    step(f"热 key 的危害在集群里更明显:按 CRC16 把这 50 万次请求分到 3 个分片(这是计算,不是真实集群):分片 0 {sh_[0]/tot*100:.0f}%,分片 1 {sh_[1]/tot*100:.0f}%,分片 2 {sh_[2]/tot*100:.0f}%——hot:1 所在的分片 1 承担了一半的请求。分片再多,也分不掉一个 key 的流量。", b=bars([[f'分片 {i}', sh_[i] / 1000, f'{sh_[i]/tot*100:.0f}%'] for i in (0, 1, 2)], max(sh_.values()) / 1000, mark=[1]), kv=KV([['分片请求占比', ' / '.join(f'{sh_[i]/tot*100:.0f}%' for i in (0, 1, 2))]], ['分片请求占比'])),
]
A = dict(
    n=115, series='redis', tags='Redis,热Key,LFU,真实验证,动画演示',
    desc=f'构造 hot:1 占 30%、hot:2 占 10% 的 50 万次 GET 负载:allkeys-lfu 下 OBJECT FREQ 是 {fq["hot:1"][0]} / {fq["hot:2"][0]} / 普通 key 约 {fq["k:1"][0]};redis-cli --hotkeys 约 2.4 s 排出 hot:1、hot:2;非 LFU 策略下 --hotkeys 与 OBJECT FREQ 报错;按 CRC16 计算 3 个分片的请求占比为 {sh_[0]/tot*100:.0f}% / {sh_[1]/tot*100:.0f}% / {sh_[2]/tot*100:.0f}%(热 key 分片承担一半)。',
    lead='热 key 是「一个 key 的访问量占了整个实例流量的一大块」。它不占内存,但会让单个分片、单个线程先到极限。怎么发现它?这篇构造一个 30% 流量落在同一个 key 上的负载,用 OBJECT FREQ 和 redis-cli --hotkeys 把它找出来,并看它在分片场景下的后果。',
    facts=[(f'{fq["hot:1"][0]} vs {fq["k:1"][0]}', 'hot:1(30% 流量)与普通 key 的 OBJECT FREQ 计数(对数计数,0–255)'), ('约 2.4 s', 'redis-cli --hotkeys 扫 10 万个 key 的耗时'), (f'{sh_[1]/tot*100:.0f}%', '按 CRC16 计算,热 key 所在分片承担的请求占比(3 分片)')],
    body=[
        sec('负载', '', term('', blk('r115', 1)), '<p>50 万次 GET:30% 打 <code>hot:1</code>,10% 打 <code>hot:2</code>,其余均匀分到 10 万个普通 key 上。实例设成 <code>allkeys-lfu</code>(LFU 淘汰策略会记录每个 key 的访问频率)。</p>'),
        sec('OBJECT FREQ', '', term('', blk('r115', 2)), f'<p>LFU 的计数器是对数的、概率性递增,范围 0–255:hot:1 是 {fq["hot:1"][0]},hot:2 是 {fq["hot:2"][0]},普通 key 约 {fq["k:1"][0]}。访问次数相差数万倍,计数只差三十倍左右——所以它适合「找出明显更热的」,不适合精确计数。</p>'),
        sec('redis-cli --hotkeys', '', term('', blk('r115', 3)), '<p>扫全库读每个 key 的 <code>OBJECT FREQ</code>,按计数从高到低打印(默认最多 16 个)。第一名是 hot:1(194),第二是 hot:2(105),后面全是计数 9 的普通 key。约 2.4 s 扫完 10 万个 key(<code>-i 0.01</code>)。</p>'),
        sec('前提:LFU 策略', '', term('', blk('r115', 4)), '<p>没有启用 LFU 策略时,<code>--hotkeys</code> 和 <code>OBJECT FREQ</code> 都返回 <code>ERR An LFU maxmemory policy is not selected, access frequency not tracked</code>;错误里还提醒:运行中切换策略后,LRU/LFU 数据需要一段时间才会调整。所以要用这个工具,通常要事先就用 LFU 策略,或者临时切过去等一会儿(临时切换对淘汰行为的影响本文没有测)。</p>'),
        sec('热 key 与分片', '', term('', blk('r115', 5)), f'<p>把这 50 万次请求按 CRC16 分到 3 个分片(<b>这是我用槽位公式算的,不是在真实集群上跑的</b>):{sh_[0]/tot*100:.0f}% / {sh_[1]/tot*100:.0f}% / {sh_[2]/tot*100:.0f}%。hot:1 所在的分片承担了约一半的请求。增加分片数不会分摊一个 key 的流量;常见办法是在客户端做本地缓存,或把热 key 拆成多份(带后缀)分散读——这两条是通用做法,本文没有实测。</p>'),
        sec('分步演示:找出热 key', '', demo('Redis 热 Key', [('t', 'term', '说明'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。单实例 allkeys-lfu;负载由 random.Random(2) 生成;分片占比是公式计算', '没有验证:真实集群上的热 key 表现、MONITOR 采样方式、LFU 计数器的衰减参数(lfu-decay-time、lfu-log-factor)、客户端本地缓存(CLIENT TRACKING)的实际收益'],
)
