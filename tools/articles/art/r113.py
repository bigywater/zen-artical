import json
from lib import *
R = J('r113'); hard, soft, slow = R['hard'], R['soft'], R['slow']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("client-output-buffer-limit <类别> <硬限制> <软限制> <软限制秒数>:一个客户端的输出缓冲超过硬限制立刻断开;超过软限制并持续了软限制秒数也断开。类别有 normal(普通客户端)、replica(从库)、pubsub(订阅者)。本实验把 normal 设成 10mb 硬限 / 5mb 软限 / 3 秒。", t=tm(['normal  10485760  5242880  3', 'slave   268435456  67108864  60', 'pubsub  33554432   8388608  60'], cur=[0]), kv=KV([['格式', '类别 硬限 软限 软限秒数']], ['格式'])),
    step(f"硬限制:一个不读取的客户端连续发 GET(每个回复 1 MB),发到第 {hard} 个时被服务器断开(client_output_buffer_limit_disconnections 0 → 1)——缓冲累计到约 10 MB 就断。", b=bars([['被断开时已发 GET 数', int(str(hard).split('(')[0]) if str(hard).split('(')[0].isdigit() else 10, str(hard)], ['硬限制(MB)', 10, '10']], 12, mark=[0]), kv=KV([['硬限制 10 MB', f'第 {hard} 个 GET 时断开']], ['硬限制 10 MB'])),
    step(f"软限制:发 7 个 GET(约 7 MB,介于 5 MB 软限与 10 MB 硬限之间):不会立刻断开,持续约 {soft:.1f} 秒(软限制的 3 秒)后被断开(disconnections 1 → 2)。", b=bars([['被断开的时间(秒)', soft, f'{soft:.1f} s'], ['软限制秒数', 3, '3 s']], 4, mark=[0], done=[1]), kv=KV([['软限制', f'持续 {soft:.1f} 秒后断开']], ['软限制'])),
    step(f"读得慢但没有超限的客户端:发 3 个 GET,每 0.2 秒读一点,服务器上它的 omem 一直是 {slow[0]} 字节(约 2 MB,低于软限 5 MB),没有被断开。", b=bars([[f'第 {i+1} 次采样 omem(MB)', o / 1e6, f'{o/1e6:.1f} MB'] for i, o in enumerate(slow)], 6, done=range(len(slow))), kv=KV([['未超限', '不断开']], ['未超限'])),
    step("含义:normal 类客户端的默认限制是「不限制」(0 0 0)——一个不读回复的客户端可以无限占内存(第 112 篇量到 100 个 1 MB 回复占 105 MB);replica 与 pubsub 类有默认上限(第 49 篇里订阅者被断开就是 pubsub 上限)。给 normal 设限制要权衡:太小会误杀正常的大回复(如 KEYS、大 HGETALL)。", t=tm(['normal:默认 0 0 0(无限)', 'replica / pubsub:默认有限制'], mark=[0]), kv=KV([['生产建议', '给 normal 设一个足够大的限制']], ['生产建议'])),
]
A = dict(
    n=113, series='redis', tags='Redis,客户端输出缓冲区,真实验证,动画演示',
    desc=f'实测 client-output-buffer-limit(normal 设为 10mb 5mb 3):不读取的客户端发到第 {hard} 个 1 MB 回复时触发硬限制被断开;缓冲在 5–10 MB 之间的客户端持续约 {soft:.1f} 秒(软限制 3 秒)后被断开;读得慢但未超限的客户端不受影响;normal 类默认不限制。',
    lead='上一篇看到输出缓冲可以无限涨。client-output-buffer-limit 就是给它加的保险:硬限制一超立刻断开,软限制超过并持续一段时间也断开。这篇把两种限制各触发一次,量断开发生的确切位置与时间。',
    facts=[(f'第 {hard} 个', '硬限制 10 MB:不读取的客户端发到第几个 1 MB 回复时被断开'), (f'{soft:.1f} 秒', '软限制 5 MB / 3 秒:输出缓冲在 5–10 MB 之间的客户端被断开所用的时间'), ('normal 默认 0 0 0', '普通客户端默认没有输出缓冲上限')],
    body=[
        sec('配置格式', '', term('', blk('r113', 1)), '<p><code>client-output-buffer-limit 类别 硬限制 软限制 软限制秒数</code>。<code>normal</code> 是普通客户端(默认 0 0 0,不限制),<code>replica</code> 是从库(默认 256mb 64mb 60),<code>pubsub</code> 是订阅者(默认 32mb 8mb 60)。</p>'),
        sec('硬限制', '', term('', blk('r113', 2)), f'<p>一个不读取的客户端连续发 GET,每个回复 1 MB。发到第 {hard} 个(累计约 10 MB)时被服务器断开,<code>INFO stats</code> 的 <code>client_output_buffer_limit_disconnections</code> 从 0 变 1,日志里记录了被关闭的客户端详情(<code>scheduled to be closed ASAP for overcoming of output buffer limits</code>)。</p>'),
        sec('软限制', '', term('', blk('r113', 3)), f'<p>缓冲在 5 MB(软限)到 10 MB(硬限)之间:发 7 个 GET 不会立刻断开,持续约 {soft:.1f} 秒(配置的 3 秒)后被断开。用来容忍「短暂的突发」而不误杀。</p>'),
        sec('读得慢但没超限', '', term('', blk('r113', 4)), f'<p>发 3 个 GET、每 0.2 秒只读一点:服务器上 <code>omem</code> 一直是 {slow[0]} 字节(约 2 MB,低于软限),没有被断开。慢客户端只要不超限就不受影响。(这一节数据不多,只说明「没超限不会断」。)</p>'),
        sec('分步演示:两种限制', '', demo('Redis 客户端输出缓冲区', [('t', 'term', '配置'), ('b', 'bars', '数据'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。不读取的客户端是接收缓冲 4 KB 的原始 socket;normal 类被临时设为 10mb 5mb 3 便于演示,默认值是 0 0 0', '没有验证:replica 类限制被触发时对复制的影响(第 58 篇提到过)、pubsub 类(第 49 篇已触发过)、软限制计时的精度、多个客户端同时超限时的顺序'],
)
