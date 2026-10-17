import json
from lib import *
txt = out('92').splitlines()
R = json.load(open('out/92.json')); seq = R['seq']; res = R['res']; ts = R['ts']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
th, ip, pp = res['ThreadPoolExecutor'], res['InterpreterPoolExecutor'], res['ProcessPoolExecutor']
ct, cp, cpr = ts['创建并等待一个线程'], ts['create+call+close 一个子解释器'], ts['spawn 一个进程(macOS 默认)']
FL = lambda cur, done=(): {'nodes': [['主解释器', 'Interpreter(0)'], ['子解释器', 'create()'], ['传参 / 返回', '可共享 or 可 pickle'], ['CPU 密集任务', '4 个 worker'], ['启动成本', '']], 'cur': cur, 'done': list(done)}
steps = [
    step("interpreters.create() 在同一个进程里新建一个解释器。它有自己的全局命名空间、自己的 sys 和 sys.modules。", fl=FL([0, 1]),
         kv={'items': [['子解释器里定义的 Y,主解释器看得到?', 'False'], ['子解释器给 sys 加的属性,主解释器有?', 'False'], ['sys.modules 大小', '主 135 / 子 52(各自独立)']], 'hl': ['sys.modules 大小']}),
    step("跨解释器传参:int/str/bytes/tuple/None 是「可共享」的;list、dict 虽然 is_shareable 为 False,call 里也能传(被复制);Lock、打开的文件传不过去。", fl=FL([2], [0, 1]),
         kv={'items': [['int / str / bytes / tuple / None', '成功,is_shareable=True'], ['list / dict / object()', '成功,is_shareable=False'], ['threading.Lock() / 打开的文件', 'NotShareableError']], 'hl': ['threading.Lock() / 打开的文件']}),
    step("类的实例要能在对方解释器里被重建:定义在模块里的 Bar() 传得过去;定义在主脚本里的 Foo() 传不过去(对方解释器的 __main__ 里没有这个类)。", fl=FL([2], [0, 1]),
         kv={'items': [['w92mod.Bar()', '成功'], ['主脚本里的 Foo()', 'NotShareableError']], 'hl': ['主脚本里的 Foo()']}),
    step(f"4 份 CPU 密集任务:线程池 {th*1000:.0f} ms,和串行 {seq*1000:.0f} ms 一样——每个线程仍在同一个 GIL 下。", fl=FL([3], [0, 1, 2]),
         b={'items': [['串行', seq * 1000, f'{seq*1000:.0f} ms'], ['ThreadPool', th * 1000, f'{th*1000:.0f} ms']], 'max': seq * 1000, 'cur': [1]}),
    step(f"子解释器池:{ip*1000:.0f} ms,加速 {seq/ip:.2f}x——每个子解释器有自己的 GIL,真的并行了。进程池是 {pp*1000:.0f} ms({seq/pp:.2f}x)。", fl=FL([3], [0, 1, 2]),
         b={'items': [['串行', seq * 1000, f'{seq*1000:.0f} ms'], ['ThreadPool', th * 1000, f'{th*1000:.0f} ms'], ['InterpreterPool', ip * 1000, f'{ip*1000:.0f} ms'], ['ProcessPool', pp * 1000, f'{pp*1000:.0f} ms']], 'max': seq * 1000, 'cur': [2, 3]}),
    step(f"启动成本:线程 {ct:.2f} ms、子解释器 {cp:.1f} ms、spawn 进程 {cpr:.0f} ms——子解释器在中间。", fl=FL([4], [0, 1, 2, 3]),
         b={'items': [['线程', ct, f'{ct:.2f} ms'], ['子解释器', cp, f'{cp:.1f} ms'], ['spawn 进程', cpr, f'{cpr:.0f} ms']], 'max': cpr, 'cur': [1]}),
]
A = dict(
    n=92,
    tags='Python,CPython,并发,子解释器,真实验证,动画演示',
    desc=f'本机 Python 3.14 的 concurrent.interpreters 真实实验:子解释器的全局变量和 sys.modules 相互独立;Lock、文件不能跨解释器传,主脚本里定义的类也传不过去;4 份 CPU 密集任务下 InterpreterPoolExecutor 加速 {seq/ip:.2f}x、线程池 {seq/th:.2f}x、进程池 {seq/pp:.2f}x;创建一个子解释器 {cp:.1f} ms,spawn 一个进程 {cpr:.0f} ms。',
    lead='想让 Python 代码真正并行,除了多进程,3.14 又多了一条路:同一个进程里跑多个相互隔离的解释器,每个有自己的 GIL。这篇用标准库的 <code>concurrent.interpreters</code> 和 <code>InterpreterPoolExecutor</code> 实际跑一遍:隔离到什么程度、能传什么、快多少、启动贵不贵。',
    facts=[(f'{seq/ip:.2f}x', '4 个子解释器并行做 CPU 密集任务的加速比(线程池只有 %.2fx)' % (seq/th)), (f'{cp:.1f} ms', '创建并调用、关闭一个子解释器的耗时(spawn 进程约 %.0f ms)' % cpr), ('NotShareableError', 'Lock、打开的文件、主脚本里定义的类,都传不进子解释器')],
    body=[
        sec('验证一:子解释器之间相互隔离', '', term('', block('== 一', '== 二')),
            '<p>子解释器里定义的变量、给 <code>sys</code> 加的属性,主解释器都看不到,反过来主解释器的全局变量它也看不到;<code>sys.modules</code> 是各自独立的一份(主 135 个模块,子解释器刚创建只有 52 个)。它们在同一个进程、同一个地址空间里,但语言层面互不可见——比线程隔离得多,又比进程轻得多。<code>exec</code> 出错时抛 <code>ExecutionFailed</code>,而且出错之后那个子解释器仍然能继续用。</p>'),
        sec('验证二:能传什么、不能传什么', '<code>Interpreter.call(func, arg)</code> 的参数与返回值',
            term('', block('== 二', '== 二·补')),
            '<p>基本类型(int、str、bytes、tuple、None)是「可共享」的;list、dict 这类虽然 <code>is_shareable</code> 是 False,通过 <code>call</code> 也能传过去(按值复制)。真正传不了的是:线程锁、打开的文件——它们绑定着解释器/系统资源。有意思的是<b>类的实例</b>:定义在可导入模块里的 <code>Bar()</code> 能传过去,而<b>定义在主脚本里的 <code>Foo()</code> 传不过去</b>——因为对方解释器要重新构造它,而它的 <code>__main__</code> 里根本没有这个类。这和第 89 篇里 pickle 的问题是同一件事。</p>'),
        sec('验证三:函数要能被对方找到', '', term('', block('== 二·补', '== 三')),
            '<p>子解释器的 <code>__main__</code> 是一个空的命名空间——主脚本里定义的 <code>work</code>,在子解释器里 <code>exec("print(work)")</code> 是 <code>NameError</code> 级别的失败。让子解释器执行你的函数,函数要放在它能 import 的模块里(我这里放进 <code>w92mod.py</code>)。我一开始把 <code>work</code> 定义在主脚本里再交给 <code>InterpreterPoolExecutor</code>,就是因为这个原因失败的。另外 <code>ProcessPoolExecutor</code>(macOS 默认 spawn)会重新导入主脚本,所以入口必须有 <code>if __name__ == "__main__":</code>——我第一次没写,结果整个脚本被重复执行了一遍。</p>'),
        sec('验证四:CPU 密集任务的并行效果', '', term('', block('== 四', '== 五')),
            f'<p>串行做 4 份要 {seq*1000:.0f} ms。线程池 {th*1000:.0f} ms,几乎没有加速——它们共享一个 GIL。<b>子解释器池 {ip*1000:.0f} ms,加速 {seq/ip:.2f}x</b>:每个子解释器有自己独立的 GIL,所以可以同时在多个核上跑纯 Python 字节码,而且不需要 3.14t 那样的自由线程构建。进程池 {pp*1000:.0f} ms({seq/pp:.2f}x),这次比子解释器慢(spawn 一个进程的成本见验证五)。加速比不是线性的,这是本机 4 个 worker、这个特定任务下的结果。</p>'),
        sec('验证五:启动成本', '', term('', block('== 五', 'zzzz')),
            f'<p>线程创建约 {ct:.2f} ms,子解释器约 {cp:.1f} ms,spawn 一个进程约 {cpr:.0f} ms。子解释器介于两者之间:比进程便宜得多,又比线程贵两百倍左右。所以它适合「少量、长期存在的 worker」,而不是「每个任务临时创建一个」。</p>'),
        sec('分步演示:子解释器的隔离、传参和并行', '数据取自上面的真实实验',
            demo('concurrent.interpreters', [('fl', 'flow', '主题'), ('kv', 'kv', '观察'), ('b', 'bars', '耗时(ms)')], steps, '当前主题 / 数据')),
    ],
    refs=['本机 macOS 27 / arm64,Python 3.14.7(Homebrew),标准库 <code>concurrent.interpreters</code>、<code>concurrent.futures.InterpreterPoolExecutor</code>;每项取 3 次最小值',
          '没有验证:C 扩展模块在子解释器里的兼容性、子解释器之间共享内存(memoryview 等)、在自由线程构建(3.14t)里的表现、Windows / Linux 上的数字。函数对象被传入子解释器时的具体机制,我只观察到「可以传、返回的是另一个对象」,没有深究原因'],
)
