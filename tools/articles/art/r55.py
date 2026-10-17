import json
from lib import *
R = J('r55'); f = R['full']; st = R['stats']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def term_(lines, cur=(), mark=(), done=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step("我用一个手写的「假从库」直接连主库(纯 TCP,没有 Redis 从库进程):完成握手后发送 PSYNC ? -1——不知道 replid,offset 用 -1。", w=term_(['> PING / REPLCONF listening-port / REPLCONF capa eof psync2', '> PSYNC ? -1'], cur=[1]), kv=KV([['假从库', '手写握手 + PSYNC']], [])),
    step(f"主库回 +FULLRESYNC <replid> 0,接着是一段 RDB 负载(长度行 ${f['rdb']},5 个 key 的数据集,开头 9 字节是 REDIS0015)。这是全量同步。", w=term_(['< +FULLRESYNC 510b37…  0', f'< ${f["rdb"]} ⏎ REDIS0015…(RDB)'], mark=[0, 1]), kv=KV([['RDB 负载', f'{f["rdb"]} 字节']], ['RDB 负载'])),
    step(f"全量之后主库把每条写命令原样(RESP 编码)推给从库:先 SELECT 0,再 SET a 1、INCR n、LPUSH l x y。共 {R['stream1']} 字节,假从库的 offset = 0 + {R['stream1']} = {R['stream1']},与主库 master_repl_offset 一致。", w=term_(['*2 $6 SELECT $1 0', '*3 $3 SET $1 a $1 1', '*2 $4 INCR $1 n', '*4 $5 LPUSH $1 l $1 x $1 y'], cur=[1, 2, 3]), kv=KV([['流长度', f'{R["stream1"]} 字节'], ['offset', str(R['stream1'])]], ['offset'])),
    step("假从库断开;主库又执行了 SET x 1、LPUSH l a b、DEL a——offset 从 107 走到 190。", w=term_(['(假从库断开)', 'SET x 1', 'LPUSH l a b', 'DEL a'], mark=[1, 2, 3]), kv=KV([['master_repl_offset', '190']], ['master_repl_offset'])),
    step(f"重连,发 PSYNC <replid> 108(下一个想要的字节 = 107 + 1)。主库回 +CONTINUE <replid>,然后补发的正是断开期间的 3 条命令,共 {R['cont']} 字节(= 190 − 107)。", w=term_(['> PSYNC 510b37… 108', '< +CONTINUE 510b37…', '*3 SET x 1', '*4 LPUSH l a b', '*2 DEL a'], cur=[1], mark=[2, 3, 4]), kv=KV([['补发', f'{R["cont"]} 字节'], ['无 RDB', '只补差量']], ['补发'])),
    step("三种不能部分重同步的请求:replid 主库不认识、offset 比主库还大、offset 早于 backlog 起点——主库全部回 +FULLRESYNC。", w=term_(['replid 不认识 → FULLRESYNC', 'offset 比主库还大 → FULLRESYNC', 'offset 早于 backlog 起点 → FULLRESYNC'], mark=[0, 1, 2]), kv=KV([['主库 stats', f'sync_full={st["sync_full"]} sync_partial_ok={st["sync_partial_ok"]} sync_partial_err={st["sync_partial_err"]}']], ['主库 stats'])),
]
A = dict(
    n=55, series='redis', tags='Redis,复制,PSYNC,真实验证,动画演示',
    desc=f'用手写的假从库直接对主库说 PSYNC 协议:PSYNC ? -1 得到 +FULLRESYNC 和一段 RDB({f["rdb"]} 字节,REDIS0015);之后主库按 RESP 原样推送写命令({R["stream1"]} 字节);断线后带 replid 和 offset+1 重连得到 +CONTINUE,补发的正是断线期间的 {R["cont"]} 字节;replid 不对、offset 太大或太旧都会回 +FULLRESYNC。',
    lead='部分重同步是复制里最值钱的优化:从库断线重连后,只补它缺的那一段命令。这篇不看 INFO 里的计数,而是自己写一个假从库,直接用 TCP 和主库说 PSYNC,把主库回的每一段字节原样打印出来,看部分重同步到底传了什么。',
    facts=[(f'{R["cont"]} 字节', '部分重同步补发的全部内容:断线期间的 3 条写命令(RESP 原文)'), ('+CONTINUE', '主库同意部分重同步的回复;+FULLRESYNC 是退回全量'), ('offset + 1', 'PSYNC 第二个参数:从库「下一个想要的」字节位置')],
    body=[
        sec('第一次:PSYNC ? -1', '', term('', blk('r55', 1)), f'<p>假从库先发 <code>PING</code>、<code>REPLCONF listening-port</code>、<code>REPLCONF capa eof capa psync2</code> 完成握手,再发 <code>PSYNC ? -1</code>。主库回 <code>+FULLRESYNC &lt;replid&gt; 0</code>,随后是 <code>${f["rdb"]}</code> 字节的 RDB 数据(这里为了方便解析,主库设置 <code>repl-diskless-sync no</code>,走磁盘文件方式;无盘方式的格式不同,见第 58 篇)。开头 9 字节是 <code>REDIS0015</code>,即 RDB 魔数加版本。</p>'),
        sec('之后:命令流', '', term('', blk('r55', 2)), f'<p>全量同步完成之后,主库把每条写命令按原样、用 RESP 编码发过来。第一条是 <code>SELECT 0</code>(先指明数据库),然后是 SET、INCR、LPUSH,合计 {R["stream1"]} 字节,<code>⏎</code> 表示 <code>\\r\\n</code>。从库的 offset 就是这些字节数的累计,与主库的 <code>master_repl_offset</code> 对上。</p>'),
        sec('断线之后:PSYNC replid offset+1', '', term('', blk('r55', 3)), '', term('', blk('r55', 4)), f'<p>主库回 <code>+CONTINUE &lt;replid&gt;</code>,紧跟着的就是断线期间的 3 条命令原文,{R["cont"]} 字节。没有 RDB,没有多余的东西。请求里的 offset 是「已收到的字节数 + 1」,即下一个想要的字节位置。</p>'),
        sec('什么时候只能全量', '', term('', blk('r55', 5)), f'<p>三种情况主库都回 <code>+FULLRESYNC</code>:replid 不认识;offset 比主库当前的还大;offset 早于 backlog 的起点(这里把 backlog 设成 16 KB、先写入约 100 KB 之后,请求一个很早的 offset)。主库 stats 里 <code>sync_partial_err</code> 累计到 {st["sync_partial_err"]},<code>sync_partial_ok</code> {st["sync_partial_ok"]}。</p>'),
        sec('分步演示:一次 PSYNC 的字节', '', demo('部分重同步', [('w', 'term', '线路上的内容(> 假从库发,< 主库发)'), ('kv', 'kv', '观察')], steps, '本步的报文')),
    ],
    refs=[ENV_R + '。假从库是我手写的 Python 套接字程序,只做握手与 PSYNC,不解析 RDB、不回复 REPLCONF ACK', '没有验证:假从库长时间不发 REPLCONF ACK 时主库的行为(超时断开等)、diskless 传输格式(第 58 篇)、replid2 与级联复制下的 PSYNC(第 52 篇部分覆盖)'],
)
