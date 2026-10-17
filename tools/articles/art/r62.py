import json
from lib import *
R = J('r62'); b = R['base']; f = R['fix']; bad = R['bad']
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
steps = [
    step(f"基线:appendfsync always 写入 1000 个 key(SET k0…k999),正常退出,重启后 DBSIZE = {b['db']}。incr 文件 {b['size']} 字节,全部是完整的 RESP 命令。", a=cells(['k0', 'k1', '…', 'k998', 'k999'], done=[0, 1, 2, 3, 4]), kv=KV([['DBSIZE', str(b['db'])], ['incr', f"{b['size']} B"]], ['DBSIZE'])),
    step(f"情形 A:崩溃时最后一条命令只写了一半(我截掉文件末尾 5 字节)。默认 aof-load-truncated yes:日志「Warning: short read」「Truncating the AOF … at offset 32770」「loaded anyway」,启动成功,DBSIZE = {R['trunc_yes']['db']},只丢了最后一条。", a=cells(['k0', '…', 'k998', 'k999(半条)'], done=[0, 1, 2], mark=[3]), kv=KV([['aof-load-truncated yes', f"启动,DBSIZE = {R['trunc_yes']['db']}"]], ['aof-load-truncated yes'])),
    step(f"同一个文件,aof-load-truncated no:拒绝启动(退出码 {R['trunc_no']['rc']}),日志「Unexpected end of file reading the append only file … use ./redis-check-aof --fix」。", a=cells(['k0', '…', 'k998', 'k999(半条)'], done=[0, 1, 2], mark=[3]), kv=KV([['aof-load-truncated no', f"拒绝启动,退出码 {R['trunc_no']['rc']}"]], ['aof-load-truncated no'])),
    step(f"情形 B:文件中间损坏——把 k500 命令的头 8 字节改成 GARBAGE!。这不是「尾部不完整」,Redis 直接拒绝启动(退出码 {bad['rc']}):「Bad file format reading the append only file … at offset 16303」。", a=cells(['k0…k499', 'k500(损坏)', 'k501…k999'], done=[0], mark=[1], dim=[2]), kv=KV([['offset', '16303'], ['退出码', str(bad['rc'])]], ['offset'])),
    step("redis-check-aof(只检查):base 合法;incr 文件在 0x3fbc 处「Expected prefix '$', got: 'G'」,ok_up_to = 16303,diff = 16500,提示 not valid,请用 --fix。", a=cells(['base ✓', 'incr 到 16303 ✓', '之后 16500 字节 ✗'], done=[0, 1], mark=[2]), kv=KV([['ok_up_to', '16303'], ['diff', '16500']], ['ok_up_to'])),
    step(f"redis-check-aof --fix:确认后把 incr 从 32803 字节截到 {f['size']} 字节,「All AOF files and manifest are valid」。重启成功,DBSIZE = {f['db']}——损坏点 k500 及之后的 {1000 - f['db']} 个 key 全部丢失,--fix 不是「修好」,是「丢掉坏点之后的一切」。", a=cells(['k0…k499 ✓(保留)', 'k500…k999 ✗(丢弃)'], done=[0], mark=[1]), kv=KV([['修复后 DBSIZE', str(f['db'])], ['丢失', f"{1000 - f['db']} 个 key"]], ['丢失'])),
    step(f"Redis 8 的 aof-load-corrupt-tail-max-size:设成 1000 或 16500 仍拒绝启动;设成 20000 才通过——日志「Truncating … at offset 16303 (remaining 16500)」「loaded anyway」,DBSIZE = {R['tail20000']['db']}。注意:错误信息建议的 16500 恰好不够。", a=cells(['1000 ✗', '16500 ✗', '20000 ✓ → 500 个 key'], mark=[0, 1], done=[2]), kv=KV([['1000 / 16500 / 20000', '拒绝 / 拒绝 / 启动']], ['1000 / 16500 / 20000'])),
]
A = dict(
    n=62, series='redis', tags='Redis,AOF,故障恢复,真实验证,动画演示',
    desc=f'亲手弄坏 AOF 文件再恢复:尾部半条命令时默认 aof-load-truncated yes 直接启动(丢 1 个 key),改成 no 就拒绝启动;文件中间损坏必然拒绝启动;redis-check-aof --fix 把文件截到 16303 字节,数据从 1000 个 key 剩 {f["db"]} 个;Redis 8 的 aof-load-corrupt-tail-max-size 需要大于损坏尾部的实际大小(16500 不够、20000 可以)。',
    lead='AOF 是追加写入的文本,崩溃时可能只写了半条命令,磁盘故障还可能让文件中间坏掉。Redis 遇到这两种情况分别怎么反应?redis-check-aof 到底修了什么?这篇故意把 AOF 文件弄坏,一步一步看启动日志、检查工具的输出,以及修复到底丢了多少数据。',
    facts=[('1 个 key', '尾部半条命令、aof-load-truncated yes(默认)时丢失的数据'), (f'{f["db"]} / 1000', '中间损坏后 redis-check-aof --fix 修复完还剩的 key(丢弃损坏点之后的一切)'), ('20000 ✓ 16500 ✗', 'aof-load-corrupt-tail-max-size 试过的值:损坏尾部实际 16500 字节')],
    body=[
        sec('尾部不完整:能自动继续', '1000 个 key、appendfsync always;截掉最后 5 字节', term('', blk('r62', 1)), '', term('', blk('r62', 2)), '<p>崩溃时最后一条命令只写了一半是最常见的情形。默认 <code>aof-load-truncated yes</code>:日志出现 <code>short read</code> 警告,Redis 把文件截到最后一条完整命令(offset 32770)继续启动,DBSIZE = 999。改成 <code>no</code>,同一个文件直接拒绝启动,日志提示用 <code>redis-check-aof --fix</code>。(第一次启动时 Redis 已经把文件截断了,所以我在第二次前重新放回了截断的文件。)</p>'),
        sec('中间损坏:一定拒绝启动', '把 k500 命令的头 8 个字节改成 GARBAGE!', term('', blk('r62', 3)), '<p>这是格式错误,不是尾部不完整:Redis 报 <code>Bad file format reading the append only file … at offset 16303</code>,退出码 1,不会带着一份不完整的数据启动。</p>'),
        sec('redis-check-aof', '', term('', blk('r62', 4)), '<p>只检查不修改:base 合法(RDB 格式,89 字节);incr 在 0x3fbc 处 <code>Expected prefix \'$\', got: \'G\'</code>,<code>ok_up_to=16303</code>,后面 16500 字节都不可信,提示用 <code>--fix</code>。</p>'),
        sec('--fix:丢弃坏点之后的一切', '', term('', blk('r62', 5)), f'<p><code>--fix</code> 要求确认,然后把 incr 文件从 32803 字节截到 {f["size"]} 字节;重启后 DBSIZE = {f["db"]}。<b>修复的意思是「保留损坏点之前的部分」,损坏点之后的 {1000 - f["db"]} 个 key 全部丢失</b>——即使它们本身是完好的。所以动手之前先备份。</p>'),
        sec('Redis 8 的 aof-load-corrupt-tail-max-size', '', term('', blk('r62', 6)), '<p>Redis 8 增加了一个选项:允许丢弃损坏点之后最多这么多字节,然后照常启动。试了三个值:1000、16500 拒绝,20000 才通过。损坏尾部实际是 16500 字节(日志 <code>remaining 16500</code>),错误信息也建议设成 16500,但恰好等于它时我这里仍然拒绝——我没有去查为什么(可能是严格的「小于」比较),只能说:<b>设置时要留出余量</b>。这个选项让「丢弃多少」有了上限,不需要人工跑 --fix。</p>'),
        sec('分步演示:三种损坏与三种恢复方式', '', demo('AOF 损坏与修复', [('a', 'cells', 'AOF 文件里的命令(✓ 完好 ✗ 损坏/丢弃)'), ('kv', 'kv', '结果')], steps, '本步涉及的部分')),
    ],
    refs=[ENV_R + '。损坏是我用脚本直接改 incr 文件造成的;appendfsync always;aof-use-rdb-preamble 使用默认', '没有验证:base 文件损坏时的行为、manifest 损坏、损坏发生在多个 incr 文件之一、真实的磁盘位翻转(这里只模拟了两种典型损坏)、aof-load-corrupt-tail-max-size 恰好等于损坏尾部大小时被拒的原因'],
)
