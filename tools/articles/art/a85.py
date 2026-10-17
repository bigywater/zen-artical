import json, re
from lib import *
txt = out('85').splitlines()
R = json.load(open('out/85.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
res = R['res']; fb, fa = R['freeze']; r0, r1, r2, r3, r4 = R['rss']
FL = lambda cur, done=(): {'nodes': [['引用还在?', 'cache / 全局'], ['gc 能看到?', '被追踪的对象'], ['内存还给系统?', 'RSS'], ['collect 的成本', '随存活对象数']], 'cur': cur, 'done': list(done)}
steps = [
    step("第一类情况:20000 个对象放在全局 cache 字典里。gc.collect() 回收 0 个——它们不是垃圾,有人还抓着。", fl=FL([0]),
         kv={'items': [['cache 占用', '24.3 MB'], ['gc.collect() 回收', '0 个'], ['gc.get_referrers 找到持有者', "dict (长度 20000)"]], 'hl': ['gc.collect() 回收']}),
    step("del cache(释放的是引用)之后,占用立刻归零——是引用计数释放的,不是 gc。", fl=FL([0]),
         kv={'items': [['del cache 之后', '0.0 MB'], ['gc.collect() 回收', '0 个']], 'hl': ['del cache 之后']}),
    step("第二类:gc.get_objects() 的直方图只能看到被追踪的对象。5000 个 Blob 里各有 1000 字节的 bytearray,它们占了大部分内存,却不出现在直方图里。", fl=FL([1], [0]),
         kv={'items': [['直方图里增加的类型', "{'Blob': 5000}"], ['没出现的', 'bytearray(每个 1000 字节)']], 'hl': ['直方图里增加的类型']}),
    step(f"第三类:创建 20 万个自引用对象,RSS 从 {r0:.0f} MB 涨到 {r1:.0f} MB;gc.collect() 回收了 199999 个对象,RSS 只回到 {r2:.0f} MB。", fl=FL([2], [0, 1]),
         kv={'items': [['基线 RSS', f'{r0:.1f} MB'], ['创建之后', f'{r1:.1f} MB'], ['gc.collect() 之后', f'{r2:.1f} MB']], 'hl': ['gc.collect() 之后']}),
    step(f"对照:一块 300 MB 的 bytearray,del 之后 ps 看到的 RSS 也没有变化({r3:.0f} → {r4:.0f} MB)——RSS 不是「Python 有没有释放」的可靠指标。", fl=FL([2], [0, 1]),
         kv={'items': [['写满 300 MB 后', f'{r3:.1f} MB'], ['del 之后', f'{r4:.1f} MB']], 'hl': ['del 之后']}),
    step("第四类:gc.collect() 自己也要花时间,跟存活的被追踪对象数成正比。", fl=FL([3], [0, 1, 2]),
         b={'items': [[f'{n:,} 个', ms, f'{ms:.2f} ms'] for n, ms in res], 'max': res[-1][1], 'cur': [2]}),
    step(f"gc.freeze() 把当前所有存活对象移出回收范围:100 万个对象时 collect 从 {fb:.2f} ms 降到 {fa:.3f} ms。适合 fork 前、长期不变的大缓存。", fl=FL([3], [0, 1, 2]),
         b={'items': [['freeze 前', fb, f'{fb:.2f} ms'], ['freeze 后', max(fa, 0.02), f'{fa:.3f} ms']], 'max': fb, 'cur': [1]}),
]
A = dict(
    n=85,
    tags='Python,CPython,垃圾回收,内存,真实验证,动画演示',
    desc=f'本机真实验证 gc.collect() 解决不了的四类内存问题:全局 cache 持有引用时回收 0 个(gc.get_referrers 直接找到持有者);gc.get_objects() 直方图看不到未追踪的 bytearray;回收 199999 个对象后 RSS 只从 {r1:.0f} MB 降到 {r2:.0f} MB;完整回收在 100 万个存活对象时要 {res[-1][1]:.1f} ms,gc.freeze() 后降到 {fa:.3f} ms。',
    lead='内存涨上去了,很多人第一反应是「手动 <code>gc.collect()</code> 一下」。但它只处理一种问题:不可达的循环垃圾。这篇拆开四种「gc 帮不上忙」的情形,每种都是真实测量。',
    facts=[('回收 0 个', '全局 cache 持有 20000 个对象时 gc.collect() 的成果'), (f'{r1:.0f} → {r2:.0f} MB', '回收 199999 个对象后,进程 RSS 的变化'), (f'{res[-1][1]:.0f} ms → {fa:.3f} ms', '100 万个存活对象时,gc.collect() 在 gc.freeze() 前后的耗时')],
    body=[
        sec('验证一:「泄漏」大多不是环,是还有人抓着', '', term('', block('== 一', '== 二')),
            '<p>全局字典里放了 20000 个对象,占 24.3 MB。<code>gc.collect()</code> 回收 0 个——这些对象是「可达」的,gc 无权动它们。<code>gc.get_referrers(某个对象)</code> 直接指出持有者是一个长度 20000 的 dict。<code>del cache</code> 之后内存立刻归零,靠的是引用计数,不是 gc。所以排查内存涨的第一步是问「谁还引用着它」,而不是「gc 为什么没回收」。</p>'),
        sec('验证二:gc.get_objects() 只看得到被追踪的对象', '', term('', block('== 二', '== 三')),
            '<p>创建 5000 个 Blob,每个带一个 1000 字节的 <code>bytearray</code>。类型直方图里只增加了 <code>Blob: 5000</code>,占了大部分内存的 <code>bytearray</code> 根本没出现——它不会引用别的对象,所以不被 gc 追踪,<code>gc.get_objects()</code> 里没有它。用这个方法排查,会漏掉「不可能成环但很大」的东西;需要结合 <code>tracemalloc</code> 看真实分配。</p>'),
        sec('验证三:回收了对象,RSS 不一定降', '', term('', block('== 三', '== 四')),
            f'<p>创建 20 万个对象(每个带 1000 字节 payload),RSS 从 {r0:.0f} MB 涨到 {r1:.0f} MB;<code>gc.collect()</code> 回收了 199999 个对象,RSS 只回到 {r2:.0f} MB。对照实验里,一块 300 MB 的 bytearray <code>del</code> 之后,<code>ps</code> 看到的 RSS 也没有下降({r3:.0f} → {r4:.0f} MB)。这是在 macOS 上的结果——底层内存是否立即归还给操作系统取决于分配器和系统策略。所以「监控里内存没降」不能推出「Python 没释放」;要看的是 Python 层的占用(<code>tracemalloc</code>)。</p>'),
        sec('验证四:collect 本身的成本', '', term('', block('== 四', '== 五')),
            f'<p>完整回收要遍历所有被追踪的存活对象:1 万个时 {res[0][1]:.2f} ms,100 万个时 {res[2][1]:.1f} ms。如果在循环里频繁手动调用 <code>gc.collect()</code>,程序里存活对象越多,每次的暂停就越长。</p>'),
        sec('验证五:gc.freeze()', '', term('', block('== 五', 'zzzz')),
            f'<p><code>gc.freeze()</code> 把当前所有对象放进永久代,之后的回收不再遍历它们:100 万个存活对象,回收从 {fb:.2f} ms 降到 {fa:.3f} ms;<code>unfreeze</code> 后数量归零。适合长期不变的大缓存、或者 <code>fork</code> 之前。冻结的对象里如果后来产生了垃圾,它们也不会被回收——这条我没有单独验证,仅从「移出回收范围」的定义推出。</p>'),
        sec('分步演示:gc 帮得上忙和帮不上忙的地方', '数据取自上面的真实实验',
            demo('四类「手动 gc 不管用」的情形', [('fl', 'flow', '排查顺序'), ('kv', 'kv', '实测数据'), ('b', 'bars', '耗时')], steps, '当前情形')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>gc</code>、<code>tracemalloc</code>;RSS 用 <code>ps -o rss=</code> 测得',
          '没有验证:Linux 上 RSS 归还的行为(macOS 与 glibc 不同)、<code>gc.set_debug</code> 与 <code>gc.garbage</code>、多进程 fork 后写时复制的实际节省量'],
)
