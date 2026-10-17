import json, statistics
from lib import *
R = J('r63'); g = R['good']; sv = R['save']
my, mn = statistics.median(sv['yes']), statistics.median(sv['no'])
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def cells(vals, cur=(), mark=(), done=(), dim=()): return {'values': vals, 'cur': list(cur), 'mark': list(mark), 'done': list(done), 'dim': list(dim)}
def bars(items, mx, cur=(), mark=(), done=()): return {'items': items, 'max': mx, 'cur': list(cur), 'mark': list(mark), 'done': list(done)}
steps = [
    step(f"健康的 dump.rdb:20 万个 key,{g['size']} 字节,末尾 8 字节是整个文件的 CRC64({g['crc']})。redis-check-rdb 输出「Checksum OK」「RDB looks OK」「200000 keys read」。", r=cells(['头部', '20 万个 key', 'CRC64 ✓'], done=[0, 1, 2]), kv=KV([['redis-check-rdb', 'Checksum OK,退出码 0']], ['redis-check-rdb'])),
    step("把某个 value 里的一个字节改掉(value-00100000 → value-00100X00),让 Redis 启动:读完整个文件后对不上校验和——「Wrong RDB checksum expected … but got … Aborting now」,进程退出码 1,拒绝启动。redis-check-rdb 同样报「RDB CRC error」,位置在文件末尾。", r=cells(['头部', '某个 value 被改 1 字节', 'CRC64 ✗'], mark=[1, 2]), kv=KV([['Redis 启动', '拒绝(退出码 1)'], ['错误', 'RDB CRC error']], ['Redis 启动'])),
    step("同样的改动,但这份 RDB 是在 rdbchecksum no 下生成的:末尾 8 字节全是 0,表示没有计算校验和。Redis 没有任何可比较的东西,正常启动、DBSIZE = 200000。", r=cells(['头部', '某个 value 被改 1 字节', 'CRC64 = 0(未计算)'], mark=[1], dim=[2]), kv=KV([['Redis 启动', '成功,DBSIZE = 200000']], ['Redis 启动'])),
    step("但数据已经坏了:GET user:100000 返回 value-00100X00,原值是 value-00100000。没有校验和,静默损坏。", r=cells(['user:100000', 'value-00100X00(应为 value-00100000)'], mark=[1]), kv=KV([['GET user:100000', 'value-00100X00']], ['GET user:100000'])),
    step("文件被截断(只剩一半):Redis 报「Unexpected EOF reading RDB file」,退出码 1;redis-check-rdb 指出出错位置、正在读的 key(user:196149)和类型,这类损坏不依赖校验和就能发现。", r=cells(['头部', '一半的 key ✓', '(文件到此结束)'], done=[0, 1], mark=[2]), kv=KV([['Redis 启动', '拒绝(Unexpected EOF)']], ['Redis 启动'])),
    step(f"校验和的代价:100 万个 key 的 SAVE,5 次取中位,rdbchecksum yes {my:.3f} s、no {mn:.3f} s,多约 {(my/mn-1)*100:.0f}%(约 {(my-mn)*1000:.0f} ms)。", b=bars([['rdbchecksum yes', my, f'{my:.3f} s'], ['rdbchecksum no', mn, f'{mn:.3f} s']], my, done=[0], mark=[1]), kv=KV([['SAVE 耗时差', f'{(my-mn)*1000:.0f} ms(约 {(my/mn-1)*100:.0f}%)']], ['SAVE 耗时差'])),
]
A = dict(
    n=63, series='redis', tags='Redis,RDB,校验和,真实验证,动画演示',
    desc=f'实测 RDB 文件校验:redis-check-rdb 在健康文件上报 Checksum OK;改掉一个 value 字节后 Redis 读完文件对不上 CRC64,拒绝启动;若 rdbchecksum no(末尾 8 字节全 0),同样的改动无人察觉,GET 返回被改坏的值;截断文件报 Unexpected EOF;100 万个 key 的 SAVE 中位 {my:.3f} s(有校验和)vs {mn:.3f} s(无)。',
    lead='RDB 文件被磁盘、拷贝或网络传输弄坏一个字节,Redis 能发现吗?靠的是文件末尾那个 8 字节的 CRC64 校验和,以及 redis-check-rdb 这个工具。这篇故意弄坏 RDB 文件三种方式,看 Redis 与检查工具各自的反应,并量一下打开校验和要多花多少时间。',
    facts=[('CRC64', '文件末尾 8 字节,整个 RDB 的校验和(rdbchecksum yes 时)'), ('静默损坏', 'rdbchecksum no 时改一个字节:Redis 正常启动,GET 返回被改坏的值'), (f'约 {(my/mn-1)*100:.0f}%', f'100 万个 key 的 SAVE:{my:.3f} s(yes)vs {mn:.3f} s(no)')],
    body=[
        sec('健康的文件', '', term('', blk('r63', 1)), f'<p>20 万个 key 的 dump.rdb 有 {g["size"]} 字节,末尾 8 字节是校验和。<code>redis-check-rdb</code> 依次读完整个文件,报告 <code>Checksum OK</code> 和读到的 key 数。</p>'),
        sec('改一个字节:被校验和拦下', '', term('', blk('r63', 2)), '<p>我用脚本找到 <code>value-00100000</code> 并把其中一个字符改成 <code>X</code>,再启动 Redis:它读完整个文件才发现校验和对不上(<code>Wrong RDB checksum expected … but got … Aborting now</code>),退出码 1,拒绝启动。redis-check-rdb 的诊断更直白:<code>RDB CRC error</code>,位置 5488988 就是文件末尾——校验和是在读完之后才比较的,所以它能告诉你「文件坏了」,不能告诉你「坏在哪一个 key」。</p>'),
        sec('关掉校验和:静默损坏', '', term('', blk('r63', 3)), '<p><code>rdbchecksum no</code> 生成的文件末尾 8 字节是 0。同样改一个字节,Redis 正常启动,<code>DBSIZE</code> = 200000,<code>GET user:100000</code> 返回被改坏的 <code>value-00100X00</code>。<b>这就是 rdbchecksum no 的风险:磁盘或传输中的位翻转不会被发现</b>——它省下的只是校验和计算的时间(见下面)。</p>'),
        sec('截断:不需要校验和也能发现', '', term('', blk('r63', 4)), '<p>只剩前一半的文件:Redis 报 <code>Unexpected EOF reading RDB file</code>;redis-check-rdb 指出出错位置、正在读的 key 和类型。结构性损坏(截断、格式错误)不依赖校验和。</p>'),
        sec('校验和的代价', '', term('', blk('r63', 5)), f'<p>100 万个 key、关闭压缩的 SAVE,每种配置连续 5 次取中位:有校验和 {my:.3f} s,无校验和 {mn:.3f} s,差约 {(my-mn)*1000:.0f} ms(约 {(my/mn-1)*100:.0f}%)。这是本机一份小数据集(key 与 value 都很短)上的数字,数据集里 value 更大时占比会不同。为这点时间关掉校验和,通常不划算。</p>'),
        sec('分步演示:三种损坏', '', demo('RDB 文件校验', [('r', 'cells', 'RDB 文件的结构'), ('b', 'bars', 'SAVE 耗时'), ('kv', 'kv', '结果')], steps, '本步涉及的部分')),
    ],
    refs=[ENV_R + '。实验里关掉了 rdbcompression,这样 value 在文件中是明文,方便定位并修改一个字节', '没有验证:压缩(LZF)开启时的损坏表现、diskless 复制传输中的校验、RDB 版本兼容、redis-check-rdb 对 8.x 新数据类型的支持范围、数据集更大时校验和的时间占比'],
)
