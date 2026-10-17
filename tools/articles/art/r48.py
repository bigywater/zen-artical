import json
from lib import *
R = J('r48'); ml, ms = R['mem']; tp = R['tp']; lat = R['lat']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
steps = [
    step(f"内存:10 万条 64 字节的消息。List(quicklist)占 {ml} 字节,{ml/100000:.1f} B/条;Stream(每条一个字段)占 {ms} 字节,{ms/100000:.1f} B/条。Stream 略高,差 {(ms-ml)/ml*100:.0f}%。", b=bars([['List', ml, f'{ml/100000:.1f} B/条'], ['Stream', ms, f'{ms/100000:.1f} B/条']], ms, cur=[0], mark=[1]), kv=KV([['结论', 'Stream 每条多约 %.1f 字节' % ((ms-ml)/100000)]], ['结论'])),
    step(f"入队吞吐(管道,20 万条,三次取中位):LPUSH {tp['LPUSH']/1000:.0f}k 条/秒,XADD {tp['XADD']/1000:.0f}k 条/秒。XADD 慢约 {(1-tp['XADD']/tp['LPUSH'])*100:.0f}%(要生成 ID、写字段)。", b=bars([['LPUSH', tp['LPUSH']/1000, f"{tp['LPUSH']/1000:.0f}k/s"], ['XADD', tp['XADD']/1000, f"{tp['XADD']/1000:.0f}k/s"]], tp['LPUSH']/1000, cur=[0], mark=[1]), kv=KV([['LPUSH', f"{tp['LPUSH']/1000:.0f}k/s"], ['XADD', f"{tp['XADD']/1000:.0f}k/s"]], ['XADD'])),
    step(f"阻塞等待延迟(500 次):LPUSH→BRPOP p50 {lat['l'][0]:.3f} ms、p99 {lat['l'][1]:.3f} ms;XADD→XREADGROUP BLOCK p50 {lat['x'][0]:.3f} ms、p99 {lat['x'][1]:.3f} ms(不含 XACK)。两者差别很小。", b=bars([['BRPOP p50', lat['l'][0], f"{lat['l'][0]:.3f} ms"], ['BRPOP p99', lat['l'][1], f"{lat['l'][1]:.3f} ms"], ['XREADGROUP p50', lat['x'][0], f"{lat['x'][0]:.3f} ms"], ['XREADGROUP p99', lat['x'][1], f"{lat['x'][1]:.3f} ms"]], 1, cur=[0, 1], mark=[2, 3]), kv=KV([['结论', '延迟量级相同']], ['结论'])),
    step("可靠性:10 条消息,消费者取出 5 条后崩溃。List:RPOP 取出的 5 条已经离开 Redis,LLEN 只剩 5——那 5 条丢了。", mL=cells(['j1 ✗', 'j2 ✗', 'j3 ✗', 'j4 ✗', 'j5 ✗', 'j6', 'j7', 'j8', 'j9', 'j10'], mark=[0, 1, 2, 3, 4]), kv=KV([['List 崩溃后', 'LLEN = 5,取出的 5 条无处可查']], ['List 崩溃后'])),
    step("Stream:XREADGROUP 取出的 5 条在 PEL 里:XPENDING 显示 5 条属于消费者 A,ID 1-0 … 5-0。可以被别的消费者 XCLAIM 认领(第 44 篇)。", mL=cells(['1 PEL', '2 PEL', '3 PEL', '4 PEL', '5 PEL', '6', '7', '8', '9', '10'], done=[0, 1, 2, 3, 4]), kv=KV([['Stream 崩溃后', 'XPENDING = 5(A),可认领']], ['Stream 崩溃后'])),
    step("List 也能做可靠:LMOVE 到「处理中」列表,处理完再 LREM。崩溃后 L:proc 里留着取出的 3 条。但超时检测、谁在处理、重试次数都得自己实现。", mL=cells(['j1 proc', 'j2 proc', 'j3 proc', 'j4', 'j5'], done=[0, 1, 2]), kv=KV([['LMOVE 崩溃后', "L:proc = ['j3','j2','j1']"]], ['LMOVE 崩溃后'])),
    step("多个消费方各读一份:两个组 billing、audit 各读到 1-0 … 5-0 全部 5 条;还能 XRANGE 回看 2-0 到 3-0。List 弹出就没了,只能被一个消费者拿到,读过不能回看。", mL=cells(['billing ✓ audit ✓'] * 5, done=range(5)), kv=KV([['Stream', '每个组各一份,可 XRANGE 回看'], ['List', '弹出即消失']], ['Stream'])),
]
A = dict(
    n=48, series='redis', tags='Redis,Stream,List,消息队列,真实验证,动画演示',
    desc=f'用同一台本机 Redis 对比 Stream 与 List 做消息队列:10 万条 64 字节消息 List {ml/100000:.1f} B/条、Stream {ms/100000:.1f} B/条;管道入队 LPUSH {tp["LPUSH"]/1000:.0f}k/s、XADD {tp["XADD"]/1000:.0f}k/s;阻塞等待延迟量级相同(p50 约 0.2 ms);消费者崩溃时 List 的 5 条取出消息无处可查,Stream 在 PEL 里可认领;Stream 支持多消费组扇出与回看。',
    lead='Redis 里做消息队列,最常见的两个选择是 List(LPUSH + BRPOP)和 Stream。它们常被拿来比较,但比较要有数据。这篇在同一台实例上量它们的内存、吞吐、延迟,再把两个最本质的差别摆出来:消费者崩溃时消息去哪了、能不能有多个消费方各读一份。',
    facts=[(f'{ml/100000:.1f} vs {ms/100000:.1f} B', '每条 64 字节消息的内存:List vs Stream'), (f'{tp["LPUSH"]/1000:.0f}k vs {tp["XADD"]/1000:.0f}k /s', '管道入队吞吐:LPUSH vs XADD'), (f'{lat["l"][0]:.2f} vs {lat["x"][0]:.2f} ms', '阻塞等待到收到的 p50:BRPOP vs XREADGROUP BLOCK')],
    body=[
        sec('内存', '10 万条,64 字节负载', term('', blk('r48', 1)), f'<p>List 用 quicklist 编码,{ml/100000:.1f} 字节/条;Stream 每条带一个字段名 p,{ms/100000:.1f} 字节/条,多约 {(ms-ml)/100000:.1f} 字节。差别不大;消息更小或字段更多时会不同(见第 39 篇关于字段名的对比)。</p>'),
        sec('入队吞吐', '', term('', blk('r48', 2)), f'<p>管道 2000 条一批、写 20 万条,三次取中位:LPUSH {tp["LPUSH"]/1000:.0f}k/s,XADD {tp["XADD"]/1000:.0f}k/s,XADD 慢约 {(1-tp["XADD"]/tp["LPUSH"])*100:.0f}%。这是单连接管道的上限,不代表真实业务里的差距(真实业务通常受网络和处理逻辑限制)。</p>'),
        sec('消费者崩溃', '', term('', blk('r48', 3)), '<p>List 的 <code>RPOP</code> 是「取出即删除」:取走 5 条、消费者崩溃,LLEN 只剩没取的 5 条,取走的 5 条在 Redis 里再也查不到。Stream 的 XREADGROUP 把这 5 条放进 PEL,崩溃后 XPENDING 立刻能看到 5 条属于 A,可以认领重试。</p>', term('', blk('r48', 4)), '<p>List 想做到可靠,要用 <code>LMOVE</code>(取出时同时放进「处理中」列表),处理完再 <code>LREM</code>。可行,但超时检测、认领、重试次数、谁在处理都得自己实现;Stream 的 PEL 已经记录了消费者、空闲时间、投递次数。</p>'),
        sec('多消费方与回看', '', term('', blk('r48', 5)), '<p>两个组 billing 和 audit 各自读到全部 5 条,读过的消息还能用 <code>XRANGE</code> 回看;List 的消息一旦被弹出就消失,同一条消息只能被一个消费者拿到。</p>'),
        sec('阻塞等待的延迟', '', term('', blk('r48', 6)), f'<p>消费者阻塞在 BRPOP / XREADGROUP BLOCK,生产者发 500 条各间隔 4 ms,量「发出 → 收到」:BRPOP p50 {lat["l"][0]:.3f} ms、p99 {lat["l"][1]:.3f} ms;XREADGROUP p50 {lat["x"][0]:.3f} ms、p99 {lat["x"][1]:.3f} ms。<b>我先前第一次测的时候把 XACK 的往返也算了进去,得到 XREADGROUP 慢一倍的结论;拆开之后两者相近</b>——这里的数字只计到「收到消息」为止,XACK 是额外的一次往返。</p>'),
        sec('分步演示:五个维度的对比', '', demo('List vs Stream', [('b', 'bars', '内存 / 吞吐 / 延迟'), ('mL', 'cells', '崩溃与扇出'), ('kv', 'kv', '结论')], steps, '本步的数据')),
    ],
    refs=[ENV_R + '。单机回环,生产者与消费者各一个连接;延迟含本机线程调度抖动', '没有验证:多消费者并发下的吞吐、消息很大时的差异、List 用 BLMOVE 做可靠队列的完整实现、集群下两者的行为差异、持久化(AOF)开启后的吞吐差别'],
)
