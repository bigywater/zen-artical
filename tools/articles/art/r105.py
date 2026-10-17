import json
from lib import *
R = J('r105'); rows = {r[0]: r for r in R['rows']}; big = R['big']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
def ln(k): return f'{k}  →  {rows[k][2]}'
steps = [
    step("请求有两种格式:标准的 multibulk(*1⏎$4⏎PING⏎)和 inline(直接写 PING⏎,telnet 风格)。两者回复都是 +PONG;inline 还支持带引号的参数(SET k \"hello world\" → +OK,GET 返回 11 字节的 hello world)。", t=tm([ln('multibulk PING'), ln('inline PING'), ln('inline SET / GET(引号)')], cur=[0, 1, 2]), kv=KV([['格式', 'multibulk / inline']], ['格式'])),
    step("协议错误时,服务器回一条 -ERR Protocol error: … 然后关闭连接:*abc → invalid multibulk length;$x → invalid bulk length;元素前缀不是 $ → expected '$', got ':';inline 引号未闭合 → unbalanced quotes in request;bulk 长度超过 proto-max-bulk-len → invalid bulk length。", t=tm([ln(k) for k in ('multibulk 长度不是数字', 'bulk 长度不是数字', 'multibulk 元素前缀不是 $', 'bulk 长度超过 proto-max-bulk-len', 'inline 引号未闭合')], mark=[0, 1, 2, 3, 4]), kv=KV([['协议错误', '回 -ERR 后断开']], ['协议错误'])),
    step("有几种「畸形」并不报错:*-5(负的 multibulk 长度)被当作空请求忽略;$10 但只给了 abc(数据没到齐)、*2000000(元素数很大)都没有回复——服务器在等后续数据,不当作错误。", t=tm([ln('multibulk 长度为负'), ln('bulk 长度声明 10 实际 3 + 结尾错'), ln('multibulk 元素数超过 1024*1024')], cur=[0, 1, 2]), kv=KV([['这些情形', '无回复(等待数据)']], ['这些情形'])),
    step("不完整的请求:SET k he 发到一半(bulk 声明 5 字节只给了 2 个),0.5 秒内服务器没有任何回复;补上 llo⏎ 后立刻回 +OK。服务器按 TCP 字节流增量解析,一条命令可以跨多个包。", t=tm(['*3⏎$3⏎SET⏎$1⏎k⏎$5⏎he', '(0.5 秒内没有任何回复)', '补上 llo⏎', '+OK⏎'], cur=[1, 3]), kv=KV([['增量解析', '半条命令一直等']], ['增量解析'])),
    step("client-query-buffer-limit(这里设成 2 MB):把 proto-max-bulk-len 临时放宽到 100 MB 后,发一个 5 MB 的 bulk,还没收完,服务器就在约 3.6 MB 时以「Closing client that reached max query buffer length」关闭连接。所以一个大 value 要同时满足 proto-max-bulk-len 与 client-query-buffer-limit。", t=tm(['*3⏎$3⏎SET⏎$1⏎k⏎$5000000⏎ + 5 MB 数据', '发送约 3600000 字节后连接被重置', '日志:Closing client that reached max query buffer length'], mark=[1, 2]), kv=KV([['两个上限', 'proto-max-bulk-len 与 client-query-buffer-limit']], ['两个上限'])),
    step(f"大 bulk 的解析速度:一条 SET 带 1 / 10 / 100 / 500 MB 的 value,往返耗时 {big[0][1]:.0f} / {big[1][1]:.0f} / {big[2][1]:.0f} / {big[3][1]:.0f} ms,约 1 GB/s(本机回环)。解析本身很快,大 value 的代价主要在它占用主线程的时间(与第 81 篇 MIGRATE 一致)。", b=bars([[f'{mb} MB', ms, f'{ms:.0f} ms'] for mb, ms in big], big[3][1], done=[0, 1, 2, 3]), kv=KV([['吞吐', '≈ 1 GB/s']], ['吞吐'])),
]
A = dict(
    n=105, series='redis', tags='Redis,协议,RESP,真实验证,动画演示',
    desc=f'用原始 socket 逐条验证 Redis 协议解析:multibulk 与 inline 两种请求格式;各种畸形请求的响应(invalid multibulk length、invalid bulk length、expected \'$\'、unbalanced quotes,回错误后断开;负长度与不完整请求则无回复、继续等待);client-query-buffer-limit 在 bulk 未收完时关闭连接;一条带 500 MB value 的 SET 往返 {big[3][1]:.0f} ms。',
    lead='Redis 的协议简单到可以用 telnet 手敲。但服务器如何处理不规矩的输入?半条命令会怎样?多大的请求会被拒绝?这篇用原始 socket 发送各种正确与畸形的请求,把服务器的每一种回应记下来。',
    facts=[('2 种格式', 'multibulk(标准)与 inline(telnet 风格,支持引号)'), ('回错误后断开', 'Protocol error 一类的畸形请求,服务器发 -ERR 后关闭连接'), ('两个上限', '大 bulk 同时受 proto-max-bulk-len 与 client-query-buffer-limit 约束')],
    body=[
        sec('两种请求格式', '', term('', blk('r105', 1)), '<p>标准的 multibulk 请求以 <code>*&lt;参数个数&gt;</code> 开头,每个参数 <code>$&lt;长度&gt;</code> + 内容。Inline 格式是直接的一行文本,以空白分隔参数,支持双引号和单引号,方便 telnet 调试。</p>'),
        sec('协议错误', '', term('', blk('r105', 2)), '<p>服务器对畸形输入的处理不是忽略,而是回一条 <code>-ERR Protocol error: …</code> 并关闭连接(因为字节流已经失去同步,无法继续解析)。其中<b>没有回复</b>的几种情形(负的 multibulk 长度、bulk 数据没到齐、元素数很大)不是错误——服务器在等更多数据,或把负长度当作空请求跳过。</p>'),
        sec('不完整请求', '', term('', blk('r105', 3)), '<p>半条命令不会触发任何回复;补全后才执行。这是 TCP 字节流上的增量解析:一条命令可以被拆成多个包,服务器把未解析的部分放在客户端的查询缓冲里。</p>'),
        sec('查询缓冲上限', '', term('', blk('r105', 4)), '<p><code>client-query-buffer-limit</code> 限制单个客户端未处理的输入缓冲。我把它设成 2 MB、把 <code>proto-max-bulk-len</code> 放宽到 100 MB,发一个 5 MB 的 bulk:在约 3.6 MB 时连接被关闭,服务器日志是 <code>Closing client that reached max query buffer length</code>。要存大 value,两个参数都要调。</p>'),
        sec('大 bulk 的解析速度', '', term('', blk('r105', 5)), f'<p>SET 一个 1 / 10 / 100 / 500 MB 的 value,往返 {big[0][1]:.0f} / {big[1][1]:.0f} / {big[2][1]:.0f} / {big[3][1]:.0f} ms,约每秒 1 GB(本机回环,客户端一次发送)。协议解析本身不是瓶颈;大 value 的问题在于它占用主线程的时间。</p>'),
        sec('分步演示:服务器如何读一条请求', '', demo('Redis 协议解析', [('t', 'term', '请求与回复'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。原始 socket;proto-max-bulk-len 与 client-query-buffer-limit 为演示临时调小,「⏎」表示 \\r\\n', '没有验证:未认证连接的参数个数限制、inline 请求的长度上限(64 KB 一说没有测)、TLS 下的解析、RESP3 下的差异(第 104 篇)'],
)
