import json
from lib import *
R = J('r99'); cs = R['cs']; rt = R['rt']; ls = R['ls']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("CONFIG RESETSTAT 之后执行一组已知次数的命令:SET ×1000、GET ×3000、INCR ×500、KEYS ×20、对字符串 key 执行 HGET ×10(类型错误)、EVAL ×5。", t=tm(['SET ×1000 · GET ×3000 · INCR ×500', 'KEYS ×20 · HGET ×10(WRONGTYPE)· EVAL ×5']), kv=KV([['已知次数', '1000 / 3000 / 500 / 20 / 10 / 5']], ['已知次数'])),
    step("INFO commandstats 里的 calls 与我执行的次数完全一致:set 1000、get 3000、incr 500、keys 20、hget 10、eval 5。", t=tm([f"{k.replace('cmdstat_','')}: {v.split(',')[0]}" for k, v in cs.items()], cur=range(6)), kv=KV([['calls', '精确']], ['calls'])),
    step("usec 是累计执行微秒,usec_per_call 是平均:GET 0.20 µs、SET 0.49 µs、INCR 0.26 µs、KEYS 24.10 µs(40 万→ 此时库里 1001 个 key)、EVAL 4.80 µs——这是服务器执行命令本身的时间。", t=tm([f"{k.replace('cmdstat_','')}: {v.split(',')[2]}" for k, v in cs.items()]), kv=KV([['usec_per_call', '执行耗时,不含网络']], ['usec_per_call'])),
    step("失败要分两种:命令执行了但报错(对字符串 key 用 HGET → WRONGTYPE)计入 failed_calls = 10;参数个数不对的 GET / SET(没走到执行)计入 rejected_calls,GET 7 次、SET 3 次——rejected 的不计入 calls。", t=tm(['hget: calls=10, failed_calls=10', 'get: calls=3000, rejected_calls=7', 'set: calls=1000, rejected_calls=3'], mark=[0, 1, 2]), kv=KV([['failed vs rejected', '执行失败 vs 根本没执行']], ['failed vs rejected'])),
    step(f"和客户端测到的往返对比:GET 往返 {rt['get']:.1f} µs、服务器 usec_per_call 只有 {rt['upc_get']:.2f} µs;KEYS 往返 {rt['keys']:.1f} µs、usec_per_call {rt['upc_keys']:.1f} µs。commandstats 不含网络、协议解析与排队。", b=bars([['GET 客户端往返', rt['get'], f"{rt['get']:.1f} µs"], ['GET 服务器执行', max(rt['upc_get'], 0.3), f"{rt['upc_get']:.2f} µs"], ['KEYS 客户端往返', rt['keys'], f"{rt['keys']:.1f} µs"], ['KEYS 服务器执行', rt['upc_keys'], f"{rt['upc_keys']:.1f} µs"]], rt['keys'], mark=[0, 2], done=[1, 3]), kv=KV([['服务器统计', '只含命令执行']], ['服务器统计'])),
    step(f"INFO latencystats 给出每个命令的分位数:set p50={ls['latency_percentiles_usec_set'].split(',')[0][4:]} / p99={ls['latency_percentiles_usec_set'].split(',')[1][4:]} µs,keys p50={ls['latency_percentiles_usec_keys'].split(',')[0][4:]} µs。CONFIG RESETSTAT 会清零所有计数(之后 cmdstat_set 不存在,只剩这条 RESETSTAT 自己)。", t=tm(['set  ' + ls['latency_percentiles_usec_set'], 'get  ' + ls['latency_percentiles_usec_get'], 'keys ' + ls['latency_percentiles_usec_keys']]), kv=KV([['RESETSTAT', '清零']], ['RESETSTAT'])),
]
A = dict(
    n=99, series='redis', tags='Redis,INFO,commandstats,真实验证,动画演示',
    desc=f'用已知次数的命令验证 INFO commandstats:calls 与执行次数完全一致(SET 1000、GET 3000……);usec_per_call 只含命令执行(GET {rt["upc_get"]:.2f} µs,而客户端往返 {rt["get"]:.1f} µs);failed_calls 计入执行失败(WRONGTYPE),rejected_calls 计入参数个数错误等未执行的命令;INFO latencystats 给出每个命令的分位数。',
    lead='INFO commandstats 是「每个命令被调用了多少次、花了多少时间」的账本。它精确吗?各字段是什么意思?failed 和 rejected 有什么区别?它的耗时和客户端看到的一样吗?这篇用已知次数的命令逐项核对。',
    facts=[('calls 精确', '执行 SET 1000 次、GET 3000 次,calls 就是 1000 和 3000'), (f'{rt["upc_get"]:.2f} µs vs {rt["get"]:.1f} µs', 'GET 的服务器 usec_per_call vs 客户端往返:统计不含网络'), ('failed ≠ rejected', '执行报错计 failed_calls;没走到执行(参数错误等)计 rejected_calls')],
    body=[
        sec('calls 与 usec', '', term('', blk('r99', 1)), '<p>每个命令一行:<code>calls</code>(次数)、<code>usec</code>(累计执行微秒)、<code>usec_per_call</code>(平均)、<code>rejected_calls</code>、<code>failed_calls</code>。我执行的次数与 calls 完全一致。KEYS 平均 24 µs(库里只有约 1000 个 key),比 GET 高两个数量级。</p>'),
        sec('failed 与 rejected', '', term('', blk('r99', 2)), '<p>对字符串 key 调 <code>HGET</code> 得到 WRONGTYPE:命令执行了、失败了,<code>calls=10,failed_calls=10</code>。参数个数不对的 <code>GET</code>/<code>SET</code> 在执行前就被拒绝,只增加 <code>rejected_calls</code>,不增加 <code>calls</code>。</p>'),
        sec('分位数', '', term('', blk('r99', 3)), '<p>Redis 7 起 <code>INFO latencystats</code> 给出每个命令的 p50 / p99 / p99.9(微秒;要 <code>latency-tracking yes</code>)。值是服务器内部的直方图估计,精度有限。</p>'),
        sec('和客户端看到的不一样', '', term('', blk('r99', 4)), f'<p>GET 客户端往返 {rt["get"]:.1f} µs,服务器统计只有 {rt["upc_get"]:.2f} µs;KEYS 往返 {rt["keys"]:.1f} µs,服务器 {rt["upc_keys"]:.1f} µs。<code>commandstats</code> 只统计命令执行,不含网络、协议解析、排队(和 SLOWLOG 一样,第 96 篇)。</p>'),
        sec('清零', '', term('', blk('r99', 5)), '<p><code>CONFIG RESETSTAT</code> 清零全部统计;之后 <code>cmdstat_set</code> 不存在,只有 RESETSTAT 命令自己的一行。</p>'),
        sec('分步演示:一份可信的账本', '', demo('INFO commandstats', [('t', 'term', '统计'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。单实例,latency-tracking yes;每个命令用单连接同步执行', '没有验证:多线程 I/O 开启时统计是否仍精确、Lua/事务内部命令的计入方式、分位数直方图的精度、commandstats 自身对性能的开销'],
)
