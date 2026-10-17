import json
from lib import *
R = J('r49'); g = R['gap']; sl = R['slow']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
steps = [
    step("没有订阅者时 PUBLISH ch m0 返回 0——消息发给了 0 个订阅者,立刻消失,Redis 不保存。", m=cells(['m0 → 0 个订阅者'], mark=[0]), kv=KV([['PUBLISH 返回', '收到消息的订阅者数']], ['PUBLISH 返回'])),
    step("订阅者在线时 PUBLISH 返回 1 且订阅者收到 m1。订阅者断开后再发布 m2,返回 0;重新订阅后 0.3 秒内什么都收不到,m2 不会补发。", m=cells(['m1 ✓', 'm2 ✗(断开中)'], done=[0], mark=[1]), kv=KV([['重新订阅后', '不补发 m2']], ['重新订阅后'])),
    step(f"掉线窗口:每 10 ms 发一条,共 {g['sent']} 条。订阅者收到第 100 条后断开 0.5 秒再重连:共收到 {g['got']} 条,缺失 {g['miss']} 条,恰好是连续的 {g['lo']}–{g['hi']}。", m=cells(['1…100 ✓', f'{g["lo"]}…{g["hi"]} ✗', f'{g["hi"]+1}…300 ✓'], done=[0, 2], mark=[1]), kv=KV([['发布', str(g['sent'])], ['收到', str(g['got'])], ['缺失', f'{g["miss"]}(连续)']], ['缺失'])),
    step(f"订阅者太慢:服务器把它的 output buffer 上限设成 pubsub 100kb 50kb 5。订阅者不读,发 1000 字节的消息,发到第 {sl['sent']} 条时超过硬上限 100 KB,服务器直接断开这个订阅者;stats 里 client_output_buffer_limit_disconnections 从 {sl['before']} 变成 {sl['after']}。", m=cells(['订阅者不读', f'发到第 {sl["sent"]} 条', '缓冲区 > 100kb', '被断开'], cur=[1], mark=[3]), kv=KV([['disconnections', f"{sl['before']} → {sl['after']}"], ['最后一次 PUBLISH 返回', '0(订阅者已被断开)']], ['disconnections'])),
    step("服务器重启:订阅关系和消息都不会保留。原来的订阅连接读到 EOF;重启后 PUBSUB NUMSUB 为 0,PUBLISH 返回 0。", m=cells(['重启前 1 个订阅', '重启后 0 个订阅'], mark=[1]), kv=KV([['订阅者要自己重连并重新 SUBSCRIBE', '']], [])),
]
A = dict(
    n=49, series='redis', tags='Redis,Pub/Sub,可靠性,真实验证,动画演示',
    desc=f'在本机 Redis 上复现 Pub/Sub 丢消息的三种情形:没有订阅者时消息直接消失;订阅者掉线 0.5 秒,300 条里丢了连续的 {g["miss"]} 条({g["lo"]}–{g["hi"]});订阅者读得慢超过 client-output-buffer-limit pubsub 会被服务器断开(发到第 {sl["sent"]} 条时);服务器重启后订阅关系不保留。',
    lead='Pub/Sub 是「发后即忘」:消息不落盘、没有确认、也没有重发。这句话人人会背,但丢消息具体是怎么发生的,丢多少?这篇在真实实例上复现四种情形:没人订阅、订阅者掉线、订阅者太慢被踢、服务器重启。',
    facts=[(f'{g["miss"]} / {g["sent"]}', '订阅者掉线约 0.5 秒时丢失的消息数(每 10 ms 一条,连续丢失)'), (f'第 {sl["sent"]} 条', '订阅者不读时,发到这一条(1000 字节)触发 100kb 硬上限被断开'), ('0', '没有订阅者时 PUBLISH 的返回值,消息不保存')],
    body=[
        sec('没有订阅者:消息立刻消失', '', term('', blk('r49', 1)), '<p><code>PUBLISH</code> 返回的是「这条消息被发给了几个订阅者」。没人订阅返回 0,消息就没了;订阅者断开后再发布,同样返回 0;重新订阅,0.3 秒内什么都收不到,不会补发。</p>'),
        sec('订阅者掉线期间的缺口', '', term('', blk('r49', 2)), f'<p>每 10 ms 发布一条,共 {g["sent"]} 条;订阅者收到第 100 条后主动断开,0.5 秒后重连。结果收到 {g["got"]} 条、缺 {g["miss"]} 条,缺的是连续的 {g["lo"]}–{g["hi"]}——正好是断开期间的那段。缺口长度 ≈ 掉线时间 ÷ 发布间隔(0.5 s ÷ 10 ms ≈ 50,实测 {g["miss"]},因为断开与重连本身也有耗时)。</p>'),
        sec('订阅者太慢:被服务器断开', '', term('', blk('r49', 3)), f'<p>为了快速触发,我把 <code>client-output-buffer-limit pubsub</code> 调成 <code>100kb 50kb 5</code>(默认是 32mb 8mb 60),并让订阅者只订阅、完全不读。发了 {sl["sent"]} 条 1000 字节的消息后,输出缓冲区超过 100 KB 硬上限,服务器日志出现 <code>scheduled to be closed ASAP for overcoming of output buffer limits</code>,<code>INFO stats</code> 里的 <code>client_output_buffer_limit_disconnections</code> 从 {sl["before"]} 变成 {sl["after"]},此后 PUBLISH 返回 0。前面那些还在缓冲区里、没发给订阅者的消息也就没了。<b>默认值大得多,但只是把「被踢」推迟到缓冲区涨到 32 MB(或 8 MB 持续 60 秒),并没有消除。</b>(本机 <code>CONFIG GET client-output-buffer-limit</code> 返回的默认值是 <code>pubsub 33554432 8388608 60</code>,即 32 MB / 8 MB / 60 秒。)</p>'),
        sec('服务器重启', '', term('', blk('r49', 4)), '<p>重启后 <code>PUBSUB NUMSUB</code> 是 0,原订阅连接读到 EOF。订阅关系存在连接上,不会持久化,重连后必须重新 SUBSCRIBE。</p>'),
        sec('分步演示:四种丢消息', '', demo('Pub/Sub 丢消息', [('m', 'cells', '消息 / 状态'), ('kv', 'kv', '观察')], steps, '本步涉及的对象')),
    ],
    refs=[ENV_R + '。为触发缓冲区上限,该实例的 client-output-buffer-limit pubsub 被显式设为 100kb 50kb 5', '没有验证:默认的 32mb 8mb 60 实际何时触发、集群和分片 Pub/Sub(SSUBSCRIBE)下的行为、客户端库的自动重连与重新订阅、RESP3 下的推送行为'],
)
