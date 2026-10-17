import json, re
from lib import *
R = J('r101'); idle = R['idle'].strip(); sp = R['spike'].strip(); hs = R['history']
I = idle.split(); S = sp.split(); IN = R['intrinsic']; iavg = re.search(r'avg latency: ([\d.]+)', IN[0]).group(1); iw = re.search(r'took (\d+)x', IN[1]).group(1)
KV = lambda items, hl=(): {'items': items, 'hl': list(hl)}
def tm(lines, cur=(), mark=()): return {'lines': lines, 'cur': list(cur), 'mark': list(mark)}
steps = [
    step(f"redis-cli --latency 不停地向服务器发 PING,同时打印:最小 / 最大 / 平均往返毫秒数与样本数。空闲实例上跑 4 秒,最后一行:{idle}(min {I[0]}、max {I[1]}、avg {I[2]} ms,{I[3]} 个样本)。", t=tm(['min max avg samples', idle], cur=[1]), kv=KV([['空闲', f'avg {I[2]} ms']], ['空闲'])),
    step(f"同样的命令,期间我制造 3 次 200 ms 的阻塞(DEBUG SLEEP 0.2):最后一行 {sp}——max 捕获到了 {S[1]} ms 的尖峰,但 avg 只有 {S[2]} ms:平均值几乎看不到问题,最大值才看得到。", t=tm(['min max avg samples', sp], mark=[1]), kv=KV([['max', f'{S[1]} ms'], ['avg', f'{S[2]} ms']], ['max'])),
    step("--latency-history:按窗口(默认 15 秒,这里用 -i 1 改成 1 秒)每个窗口一行。制造一次 150 ms 阻塞,只有它所在的窗口(窗口 2)出现 max = 151 ms,其它窗口 max 都不到 0.6 ms。", t=tm([f'窗口 {i+1}: {l}' for i, l in enumerate(hs)], mark=[1]), kv=KV([['尖峰所在窗口', '窗口 2:max 151 ms']], ['尖峰所在窗口'])),
    step("--latency-dist:延迟分布图。用字符表示占比(. - * # 1-9),下面的图例给出每个字母对应的延迟区间(A–E:10–50 毫秒;F–J:0.1–0.5 秒;K–Q:1–60 秒)。这次空闲测量里所有样本都落在最底层的区间,没有字母。", t=tm(['A,B,C,D,E        10,20,30,40,50  milliseconds', 'F,G,H,I,J        .1,.2,.3,.4,.5       seconds', 'K,L,M,N,O,P,Q,?  1,2,4,8,16,30,60,>60 seconds'], cur=[0, 1, 2]), kv=KV([['分布图', '文本图例;实际使用时是彩色块']], ['分布图'])),
    step(f"--intrinsic-latency 3:不连接服务器,在本机上空转 3 秒,测「这台机器自己」的调度抖动:平均每次约 {iavg} µs,最差的一次比平均慢 {iw} 倍(不同次运行的最差倍数差别很大:我这一台机器上跑过 96 倍和 204 倍)。用来区分「Redis 慢」和「机器/虚拟机本身慢」。", t=tm(IN, cur=[0, 1]), kv=KV([['用途', '排除机器本身的抖动']], ['用途'])),
]
A = dict(
    n=101, series='redis', tags='Redis,redis-cli,延迟,真实验证,动画演示',
    desc=f'实测 redis-cli 的三个延迟工具:--latency 空闲时 avg {I[2]} ms;制造 3 次 200 ms 阻塞后 max {S[1]} ms 而 avg 只有 {S[2]} ms;--latency-history 让 150 ms 的尖峰只出现在它所在的窗口(max 151 ms);--intrinsic-latency 测本机自身调度抖动,不连接服务器。',
    lead='redis-cli 自带三个测延迟的开关:--latency、--latency-history、--latency-dist,再加一个不连服务器的 --intrinsic-latency。它们测的是「客户端到服务器的往返」,不是服务器内部的耗时。这篇在空闲和有阻塞两种情形下各跑一遍,看它们分别能发现什么。',
    facts=[('avg 看不见', f'3 次 200 ms 阻塞:max {S[1]} ms,avg 只有 {S[2]} ms'), ('窗口', '--latency-history 把一次 150 ms 阻塞定位在它所在的那个 1 秒窗口(max 151 ms)'), ('不连服务器', '--intrinsic-latency 只测本机自身的调度抖动')],
    body=[
        sec('--latency:min / max / avg', '', term('', blk('r101', 1)), '<p>不停发 <code>PING</code>,每次往返计一个样本。空闲实例上 avg 约 0.2 ms。</p>', term('', blk('r101', 2)), f'<p>制造 3 次 200 ms 的阻塞:<code>max</code> 抓到了 {S[1]} ms,<code>avg</code> 只有 {S[2]} ms。<b>看平均值几乎发现不了问题,最大值才是要看的。</b></p>'),
        sec('--latency-history', '', term('', blk('r101', 3)), '<p>每个窗口输出一行(默认 15 秒,这里 <code>-i 1</code>)。150 ms 的阻塞只出现在窗口 2(<code>max: 151.485</code>),其它窗口都没有——可以看到「什么时候」出现的尖峰。(输出用了光标控制字符不断刷新同一行,我截取每个窗口结束时的最终一行。)</p>'),
        sec('--latency-dist', '', term('', blk('r101', 4)), '<p>延迟分布。每一行的字符表示各区间的占比,图例里的字母对应从毫秒到分钟的区间。这次空闲测量的样本都落在最低区间。它主要在终端里以彩色显示,文本抓取不能完整还原,所以这里只展示图例。</p>'),
        sec('--intrinsic-latency:排除机器本身', '', term('', blk('r101', 5)), f'<p>不连接任何服务器,在本机紧循环 3 秒,记录最慢的一次比平均慢多少倍。如果这个值本身就大,说明机器(或虚拟机、容器)自己有调度抖动,Redis 再好也快不起来。平均 {iavg} µs;最差比平均慢的倍数每次运行都不同。</p>'),
        sec('分步演示:三个延迟工具', '', demo('redis-cli --latency', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_R + '。--latency 与 --latency-history 用 DEBUG SLEEP 制造阻塞;history 用伪终端捕获输出', '没有验证:--latency-dist 的彩色刷新、--latency 对生产实例的额外负载、虚拟机 / 容器下的 --intrinsic-latency、跨机器网络下的 --latency'],
)
