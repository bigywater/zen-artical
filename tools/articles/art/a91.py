import json
from lib import *
txt = out('91').splitlines()
R = json.load(open('out/91.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
names = list(R.keys()); g, f, g2 = (R[n] for n in names)
sp = lambda r: {n: s / t for n, s, t in r['rows']}
sg, sf, sg2 = sp(g), sp(f), sp(g2)
def bars(sd, cur=()): return {'items': [[f'{n} 个线程', v, f'{v:.2f}x'] for n, v in sd.items()], 'max': 4, 'cur': list(cur), 'done': []}
FL = lambda cur, done=(): {'nodes': [['普通 3.14', 'GIL 开'], ['3.14t', '自由线程'], ['3.14t + PYTHON_GIL=1', '重新开 GIL'], ['竞态', '+= 1']], 'cur': cur, 'done': list(done)}
steps = [
    step("普通 3.14(GIL 开):1、2、4、8 个线程做纯 Python 计算,线程并行与串行几乎一样快——加速比始终约 1.0x。多线程没有让 CPU 密集任务变快。", fl=FL([0]), b=bars(sg)),
    step("3.14t(自由线程,GIL 关闭):2 个线程 2.22x,4 个线程 2.61x,8 个线程 3.66x。线程真的在多个核上同时跑纯 Python 代码了(但远没有线性加速)。", fl=FL([1], [0]), b=bars(sf, [1, 2, 3])),
    step("同一个 3.14t,只是设置环境变量 PYTHON_GIL=1:加速比回到 1.2x 左右。说明加速来自「关掉了 GIL」,而不是别的。", fl=FL([2], [0, 1]), b=bars(sg2)),
    step("代价:4 个线程各做 50 万次 box[0] += 1。有 GIL 时每次都是精确的 2000000;自由线程下 5 次结果是 " + str(f['race']) + "——丢了一大半更新。", fl=FL([3], [0, 1, 2]),
         kv={'items': [['普通 3.14', '2000000 ×5(全部正确)'], ['3.14t', ' / '.join(str(x) for x in f['race'])], ['3.14t + PYTHON_GIL=1', '2000000 ×5(全部正确)']], 'hl': ['3.14t']}),
]
A = dict(
    n=91,
    tags='Python,CPython,并发,GIL,真实验证,动画演示',
    desc=f'本机用 3.14 与自由线程版 3.14t 各跑同一个 CPU 密集任务:4 线程并行时 GIL 版加速比 {sg[4]:.2f}x、自由线程版 {sf[4]:.2f}x(8 线程 {sf[8]:.2f}x),设 PYTHON_GIL=1 后回到 {sg2[4]:.2f}x;4 个线程各做 50 万次 += 1,GIL 版恒为 2000000,自由线程版只得到约 83 万。',
    lead='自由线程(free-threading)是 Python 3.13 起出现的实验性构建:去掉 GIL,让多个线程真正同时运行 Python 字节码。这篇装了官方的 3.14t,拿同样的代码在三种配置下比:有 GIL、无 GIL、以及无 GIL 的构建里再把 GIL 打开。',
    facts=[(f'{sg[4]:.2f}x → {sf[4]:.2f}x', '4 个线程做纯 Python 计算时,GIL 版与自由线程版的加速比'), (f'{f["race"][0]:,}', '自由线程下 4 线程 × 50 万次 += 1 的结果(期望 2,000,000)'), ('PYTHON_GIL=1', '同一个 3.14t,重新打开 GIL 后加速比回到 1.2x 左右')],
    body=[
        sec('做的事:三种解释器配置', '',
            term('', block('== 一', '== 二')),
            '<p>普通 3.14 的 <code>Py_GIL_DISABLED</code> 是 0、GIL 开;3.14t 是 1、GIL 关(<code>sys.abiflags</code> 是 <code>t</code>);同一个 3.14t 用环境变量 <code>PYTHON_GIL=1</code> 还能在运行时把 GIL 重新打开,<code>sys._is_gil_enabled()</code> 就会变回 True。3.14t 是我用 <code>uv python install 3.14t</code> 装在临时目录里的,没有动系统的 Python。</p>'),
        sec('验证一:CPU 密集任务,线程到底能不能加速', '', src('每个线程做的事', '''def work():
    s = 0
    for i in range(3_000_000): s += i * i'''), term('', block('== 二', '== 三')),
            f'<p>有 GIL 的 3.14 里,不论 2、4、8 个线程,并行耗时都和串行几乎一样(加速比约 1.0x)——同一时刻只有一个线程在执行字节码。自由线程版 4 个线程是 {sf[4]:.2f}x、8 个线程 {sf[8]:.2f}x:真的并行了,但没达到线性(本机 10 核,还有线程创建、内存分配、缓存一致性等开销)。设了 <code>PYTHON_GIL=1</code> 之后,同一个 3.14t 也只剩约 1.2x,可见提升来自去掉 GIL。这里的数字是这台机器上这个特定任务的结果,不是通用倍数。</p>'
            '<p>顺带一个和常见说法不太一样的观察:这次单线程的串行耗时,3.14t(约 101 ms)并不比普通 3.14(约 104 ms)慢。这是这个简单循环的结果,别的代码(尤其是大量小对象操作)我没有测,不能推广。</p>'),
        sec('验证二:代价——原来靠 GIL 才「碰巧安全」的代码会出问题', '', term('', block('== 三', 'zzzz')),
            f'<p>4 个线程各对同一个 <code>box[0]</code> 做 50 万次 <code>+= 1</code>,期望 2,000,000。有 GIL 的 3.14 五次都精确;自由线程版五次都只有 83 万上下,丢了一半以上的更新。<code>+= 1</code> 本来就不是原子操作(读、加、写三步),只是在 GIL 下线程切换点很少,恰好没出事。去掉 GIL 之后,这类隐藏的竞态就暴露了——共享的可变状态要自己加锁(<code>threading.Lock</code>)。</p>'
            '<p>另外我在一次单独的试跑里(输出没有放进上面的终端块)测了 4 个线程各 <code>list.append</code> 20 万次,两种构建的最终长度都是 800000,没有丢——单个内置容器的操作本身是安全的,不安全的是「读—改—写」这类组合动作。</p>'),
        sec('分步演示:加速比,以及代价', '数据来自上面的实测',
            demo('GIL 开 / 关 对线程加速的影响', [('fl', 'flow', '三种配置'), ('b', 'bars', '线程数 vs 加速比'), ('kv', 'kv', '竞态结果')], steps, '当前配置')),
    ],
    refs=['本机 macOS 27 / arm64,10 核;Python 3.14.7(Homebrew)与 3.14.7 free-threaded(uv 安装);每项取 3 次最小值,计时用 <code>time.perf_counter</code>',
          '没有验证:C 扩展在自由线程下的兼容(导入未声明支持的扩展会自动重开 GIL,这条我没有实测)、内存占用差异、I/O 密集任务、其他版本的自由线程性能'],
)
