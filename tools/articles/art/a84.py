import json, re
from lib import *
txt = out('84').splitlines()
R = json.load(open('out/84.json'))['rows']   # (name, refcount, internal, gc_refs)
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
mem = {m.group(1): float(m.group(2)) for l in txt if (m := re.search(r'gc (enabled|disabled)\s*: .*仍占用\s+([\d.]+) MB', l))}
ev = next(l for l in txt if '自动触发了' in l); nrec = re.search(r'触发了 (\d+) 次', ev).group(1)
names = [r[0] for r in R]; rc = {r[0]: r[1] for r in R}; inn = {r[0]: r[2] for r in R}; gr = {r[0]: r[3] for r in R}
graph = ["A → B     B → A   (环,无外部引用)", "C → D     D → C   (环,但全局变量 C 指向 C)", "E → E             (自环,无外部引用)"]
def chips(sub, cur=(), mark=(), done=(), dim=()): return {'values': [[n, sub(n)] for n in names], 'cur': [names.index(x) for x in cur], 'mark': [names.index(x) for x in mark], 'done': [names.index(x) for x in done], 'dim': [names.index(x) for x in dim]}
G = {'lines': graph, 'cur': []}
steps = [
    step("五个对象,引用关系如下。del 之后只剩全局名字 C 还指着 C。引用计数没法直接告诉我们「谁是垃圾」——A、B、E 的计数都是 1,而不是 0。", g=G, c=chips(lambda n: f"引用计数 {rc[n]}")),
    step("第一步:把每个对象的引用计数复制到 gc_refs。", g=G, c=chips(lambda n: f"gc_refs = {rc[n]}", cur=names)),
    step("第二步「试探性删除」:遍历每个对象引用的其它对象,把被引用者的 gc_refs 减 1(只减来自这一批对象内部的引用)。", g={'lines': graph, 'cur': [0, 1, 2]}, c=chips(lambda n: f"{rc[n]} − {inn[n]} = {gr[n]}", cur=names)),
    step("减完之后 gc_refs 仍大于 0 的对象,说明有「图外面」的引用指着它——只有 C(全局变量)。它是根。A、B、D、E 都是 0。", g=G, c=chips(lambda n: f"gc_refs = {gr[n]}", mark=['C'], dim=[n for n in names if n != 'C'])),
    step("第三步:从根出发标记所有可达对象——C 引用 D,所以 D 也活着,尽管 D 自己的 gc_refs 是 0。", g={'lines': graph, 'cur': [1]}, c=chips(lambda n: f"gc_refs = {gr[n]}", mark=['C'], done=['D'], dim=['A', 'B', 'E'])),
    step("剩下不可达的 A、B、E 就是循环垃圾:调用它们的 __del__,再打破环并释放。gc.collect() 实际回收了 3 个,__del__ 通知到的正是 ['A','B','E']。", g={'lines': graph, 'cur': [0, 2]}, c=chips(lambda n: "垃圾 → 回收" if n in 'ABE' else "存活", cur=['A', 'B', 'E'], done=['C', 'D'])),
]
A = dict(
    n=84,
    tags='Python,CPython,垃圾回收,真实验证,动画演示',
    desc=f'本机真实验证:两个对象互相引用后 del,弱引用仍然存活直到 gc.collect() 回收(4 个对象);gc 阈值 (2000, 10, 10);自己用 getrefcount 和 get_referents 实现「试探性删除」,判定的垃圾 [A, B, E] 与 gc.collect() 一致;20 万对环形垃圾在关闭 gc 时占用 {mem["disabled"]:.1f} MB,打开时仅 {mem["enabled"]:.2f} MB。',
    lead='引用计数为 0 就立刻释放——这是 CPython 的主要回收机制。但两个对象互相引用时,计数永远不会归零。这篇把「环」怎么产生、<code>gc</code> 怎么发现它、我自己写一遍这套算法能不能得到同样的答案,都真实跑了一遍。',
    facts=[('4 个对象', 'a、b 及各自的 refs 列表:gc.collect() 之前它们没有被释放'), ('[A, B, E]', '我用 getrefcount + get_referents 手写的算法与 gc.collect() 判定一致'), (f'{mem["disabled"]:.1f} MB vs {mem["enabled"]:.2f} MB', '20 万对环形垃圾后,gc 关闭 / 开启时仍占用的内存')],
    body=[
        sec('验证一:引用计数回收不了环', '', src('实验', '''gc.collect(); gc.disable()
a, b = N("a"), N("b")
a.refs.append(b); b.refs.append(a)     # 互相引用
wa = weakref.ref(a)
del a, b                               # 名字没了, 但它们还互相指着'''),
            term('', block('== 一', '== 二')),
            '<p><code>del a, b</code> 之后没有任何变量指向它们,可弱引用显示对象还在——因为 a 被 b 引用、b 被 a 引用,计数各剩 1,永远不会归零。<code>gc.collect()</code> 之前,它们就泄漏在堆里。回收数是 4:a、b 以及它们各自的 <code>refs</code> 列表(列表也是对象)。</p>'),
        sec('验证二:gc 只追踪「可能成环」的对象', '', term('', block('== 二', '== 三')),
            '<p>gc 阈值是 (2000, 10, 10),共 3 代。整数、字符串这类不能引用别的对象的东西不需要被追踪(<code>is_tracked</code> 为 False);列表、字典、自定义对象、类都是被追踪的。元组比较特殊:<code>(1, 2)</code> 没被追踪,<code>(1, [])</code> 被追踪了——因为它里面有一个可变的、能引用别人的对象。这里只列观察到的结果,具体怎样触发「取消追踪」的规则我没有逐条验证。</p>'),
        sec('验证三:自己实现一遍「试探性删除」', '和 gc.collect() 的结论对比', term('', block('== 三', '== 四')),
            '<p>思路是:每个对象的引用计数里,有一部分是「这一批对象互相引用」产生的。把这一部分减掉,剩下的就是「批外的人对它的引用」。剩余 &gt; 0 的是根(有人从外面抓着),根能到达的都活着,其余就是垃圾。校准部分里我用一个只被全局名字引用的对象 P,来扣掉<code>getrefcount</code>观察本身带来的引用。结果:C 是根,D 被 C 引用所以活着,A、B、E 是垃圾,<code>gc.collect()</code> 实际调用 <code>__del__</code> 的也正好是 A、B、E。</p>'),
        sec('验证四:什么时候会自动触发', '用 gc.callbacks 记录', term('', block('== 四', '== 五')),
            f'<p>创建 20000 对环形垃圾,期间 gc 自己触发了 {nrec} 次回收,绝大多数是第 0 代(新对象),少数升到第 1 代;每次回收都收走了上千个对象。你不需要手动调用 <code>gc.collect()</code>,但如果代码里有大量互相引用的对象,回收发生的时机是由分配数量而不是时间决定的。</p>'),
        sec('验证五:把 gc 关了会怎样', '', term('', block('== 五', 'zzzz')),
            f'<p>同样创建 20 万对环形垃圾:gc 开着,结束时只占 {mem["enabled"]:.2f} MB;关掉 gc,占了 {mem["disabled"]:.1f} MB,直到手动 <code>gc.collect()</code> 才一次性回收了 80 万个对象。关 gc 是有人会做的优化(比如批处理、fork 之前),但代价是循环引用产生的垃圾不会被回收。</p>'),
        sec('分步演示:一次试探性删除', '数字来自验证三里我自己实现的算法(引用计数的基线已校准)',
            demo('gc 如何判定循环垃圾', [('g', 'term', '引用关系'), ('c', 'chips', '每个对象的 gc_refs')], steps, '此刻在处理的对象')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>gc</code>、<code>weakref</code>、<code>tracemalloc</code>、<code>sys.getrefcount</code>',
          '我手写的算法是对「试探性删除」思路的复现,不是 CPython 源码的逐行对应(没有读 C 实现);没有验证:分代升级的具体条件、<code>gc.freeze()</code>、带 <code>__del__</code> 的对象在旧版本 Python 里的行为'],
)
