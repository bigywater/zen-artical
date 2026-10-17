import json
from lib import *
R = J('r54'); ev = R['events']; rdb = R['rdb']; db = R['db']
E = {}
for t, w, l in ev:
    for k in ('asks for', 'Starting BGSAVE', 'terminated with success', 'receiving', 'Loading DB', 'Flushing', 'Done loading', 'Finished'):
        if k in l: E[k] = t
tot = E['Finished']; bg = E['terminated with success']; load = E['Done loading'] - E['Loading DB']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def flow(cur, done=()): return {'nodes': [['握手', '+0.00 s'], ['主库 BGSAVE', f'→ +{bg:.2f} s'], ['传输 RDB', f'+{bg:.2f} → +{ev[5][0]:.2f} s'], ['从库加载', f'→ +{tot:.2f} s'], ['追增量', 'link up']], 'cur': list(cur), 'done': list(done)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step("主库有 100 万个 key(used_memory 约 159 MB)。从库执行 REPLICAOF:从库日志「MASTER <-> REPLICA sync started」,几乎同时主库日志「asks for synchronization」。此时 master_link_status 是 down,master_sync_in_progress 是 1,总量还是 -1(不知道要传多少)。", f=flow([0]), kv=KV([['t', '0.00 s'], ['sync_in_progress', '1'], ['sync_total_bytes', '-1']], ['sync_total_bytes'])),
    step(f"主库 fork 出子进程做 BGSAVE(这是磁盘方式,repl-diskless-sync no):日志「Starting BGSAVE for SYNC with target: disk」。在子进程写完 RDB 之前,从库采样一直看不到已接收字节。这一阶段耗时约 {bg:.2f} s。", f=flow([1], [0]), kv=KV([['BGSAVE', f'约 {bg:.2f} s'], ['RDB 文件', f'{rdb/1e6:.1f} MB']], ['BGSAVE'])),
    step(f"BGSAVE 完成(+{bg:.2f} s),主库把 dump.rdb 发给从库:从库日志「receiving {rdb} bytes」,{rdb/1e6:.1f} MB 在本机回环上不到 30 ms 就传完(主库日志 +{ev[5][0]:.3f} s「Synchronization … succeeded」)。", f=flow([2], [0, 1]), kv=KV([['传输的 RDB', f'{rdb} 字节'], ['本机回环', '< 30 ms']], ['传输的 RDB'])),
    step(f"从库开始加载:日志「Flushing old data」「Loading DB in memory」;采样里 loading = 1、loading_loaded_bytes 从 1 MB 涨到 14 MB。加载 100 万个 key 花了 {load:.2f} s——与 BGSAVE 那一段(约 {bg:.2f} s)是全量同步里两个最耗时的阶段,加载期间从库不能服务客户端(我没有在这次实验里另外验证「不能服务」,这是加载期间 loading=1 的含义)。", f=flow([3], [0, 1, 2]), kv=KV([['加载耗时', f'{load:.2f} s'], ['loading_loaded_bytes', '1 MB → 14 MB → …']], ['加载耗时'])),
    step(f"同步期间主库仍在被写(我的写线程写了 {db[2]} 个 live:* key)。这些增量命令先缓冲在主库给该从库的输出缓冲区(client_recent_max_output_buffer = {R['maxbuf']} 字节),RDB 加载完之后发给从库。最终 dbsize 主/从 = {db[0]} / {db[1]}。", f=flow([4], [0, 1, 2, 3]), kv=KV([['同步期间写入', f'{db[2]} 个 key'], ['dbsize 主/从', f'{db[0]} / {db[1]}']], ['dbsize 主/从'])),
    step(f"总耗时 {tot:.2f} s:BGSAVE {bg:.2f} s + 传输 <0.03 s + 加载 {load:.2f} s。RDB 只有 {rdb/1e6:.1f} MB 远小于内存的 159 MB,是因为我的 value 是重复的 'v'*100,能被压缩得很好——所以这个 MB 数不能代表你的数据。", b=bars([['BGSAVE', bg, f'{bg:.2f} s'], ['传输', 0.03, '<0.03 s'], ['从库加载', load, f'{load:.2f} s']], max(bg, load) * 1.1, mark=[2]), kv=KV([['总计', f'{tot:.2f} s']], ['总计'])),
]
A = dict(
    n=54, series='redis', tags='Redis,复制,RDB,全量同步,真实验证,动画演示',
    desc=f'100 万个 key 的主库,磁盘方式全量同步的实测时间线:BGSAVE {bg:.2f} s → 传输 {rdb/1e6:.1f} MB RDB 不到 0.03 s → 从库加载 {load:.2f} s,共 {tot:.2f} s;同步期间主库写入 {db[2]} 个 key 被缓冲后补发(最大输出缓冲 {R["maxbuf"]} 字节),最终两边 dbsize 都是 {db[0]}。',
    lead='新从库第一次连主库,或者补不上差量时,要做一次全量同步:主库把当前的数据集做成 RDB 传过去,从库加载。这几步各花多久、期间主库的新写入去哪了?这篇在 100 万个 key 的数据集上,把同步过程的日志、采样和最终数据对账都记下来(这里用磁盘方式;无盘方式见第 58 篇)。',
    facts=[(f'{tot:.2f} s', f'100 万 key 全量同步总耗时(BGSAVE {bg:.2f} s + 加载 {load:.2f} s)'), (f'{rdb/1e6:.1f} MB', 'RDB 文件大小(内存 159 MB;value 高度可压缩)'), (f'{R["maxbuf"]} B', f'同步期间为从库缓冲的增量命令峰值(期间写入 {db[2]} 条)')],
    body=[
        sec('采样:从库在每个阶段的样子', '每 50 ms 读一次从库的 INFO', term('', blk('r54', 1)), '<p>第一列是相对 <code>REPLICAOF</code> 的时间。BGSAVE 阶段,<code>master_sync_in_progress</code> 是 1 而总量是 -1;RDB 传完之后 <code>master_sync_read_bytes</code> 等于总量,同时 <code>loading</code> 变成 1,<code>loading_loaded_bytes</code> 往上涨;加载完成 <code>master_link_status</code> 才变成 <code>up</code>。</p>'),
        sec('日志:各阶段的时间点', '主库与从库的日志合并、按时间排序', term('', blk('r54', 2)), f'<p>主库在 +{E["Starting BGSAVE"]:.3f} s 开始 BGSAVE,{bg:.2f} s 后结束;RDB 的传输几乎瞬间;从库在 {E["Loading DB"]:.3f} s 开始加载,{E["Done loading"]:.2f} s 完成。其中最耗时的两段:主库 BGSAVE({bg:.2f} s)和从库加载({load:.2f} s)。本机回环上传输不是瓶颈;跨机器的网络带宽会让「传输」这一段变长——这里没有测。</p>'),
        sec('对账:同步期间的写入没有丢', '', term('', blk('r54', 3)), f'<p>同步开始后我用另一个线程持续往主库写 <code>live:*</code> key({db[2]} 个)。这些命令在 RDB 生成之后,先缓冲在主库给该从库的输出缓冲区,RDB 加载完成后再发给从库。最终 dbsize 主 {db[0]}、从 {db[1]},一致,等于 100 万加 {db[2]}。从库日志里 keys loaded = 1000001:RDB 装的是 fork 那一刻的数据(其中已含 1 个 live key),其余 {db[2]-1} 个是缓冲的增量命令补上的。</p>'),
        sec('分步演示:全量同步的五个阶段', '', demo('全量同步中的 RDB 传输', [('f', 'flow', '阶段'), ('b', 'bars', '各阶段耗时'), ('kv', 'kv', '观察')], steps, '当前阶段')),
    ],
    refs=[ENV_R + '。主库 repl-diskless-sync no(磁盘方式),100 万个 key,每个 value 是 100 个 v;从库在同一台机器', '没有验证:跨机器网络下的传输耗时、value 不可压缩(如随机数据)时的 RDB 大小、repl-timeout 与 client-output-buffer-limit replica 在同步过久时触发断开的情形(本次没有触发)'],
)
