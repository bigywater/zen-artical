from lib import *
txt = out('89').splitlines()
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
def part(text, a, b=None):
    i = text.index(a); j = text.index(b, i + len(a)) if b else len(text); return text[i:j].strip()
one = block('== 一', '== 二')
FL = lambda cur, done=(): {'nodes': [['python pkg/tool.py', '当成脚本'], ['python -m pkg.tool', '当成模块'], ['import pkg.tool', '被导入'], ['a.py ↔ b.py', '互相导入'], ['pickle / spawn', '依赖 __main__']], 'cur': cur, 'done': list(done)}
steps = [
    step("当成脚本运行:__name__ 是 '__main__',__package__ 是 None,没有 __spec__,sys.path[0] 是脚本所在目录 pkg/。相对导入直接失败:no known parent package。", fl=FL([0]),
         kv={'items': [['__name__', "'__main__'"], ['__package__', 'None'], ['__spec__', 'None'], ['sys.path[0]', '<工作目录>/pkg'], ['from .util import hi', 'ImportError'] ], 'hl': ['from .util import hi']}),
    step("当成模块运行:__name__ 仍是 '__main__',但 __package__ = 'pkg'、有 ModuleSpec(name='pkg.tool'),sys.path[0] 是工作目录。相对导入成功。", fl=FL([1], [0]),
         kv={'items': [['__name__', "'__main__'"], ['__package__', "'pkg'"], ['__spec__', "ModuleSpec(name='pkg.tool')"], ['sys.path[0]', '<工作目录>'], ['from .util import hi', "util.hi"]], 'hl': ['__package__', 'from .util import hi']}),
    step("被 import 时:__name__ 才是真正的模块名 'pkg.tool'——这就是 if __name__ == '__main__' 能区分「直接运行」和「被导入」的原因。", fl=FL([2], [0, 1]),
         kv={'items': [['__name__', "'pkg.tool'"], ['__package__', "'pkg'"], ['sys.path[0]', "''(-c 的情形)"]], 'hl': ['__name__']}),
    step("陷阱:a.py 当脚本运行(__name__='__main__')时 import b,b 又 import a——Python 找不到名叫 a 的模块,于是把 a.py 再执行一遍(这次 __name__='a')。同一个文件的顶层代码被执行了两次,得到两份不同的模块对象。", fl=FL([3], [0, 1, 2]),
         kv={'items': [['[a.py] 开始', "__name__ = '__main__'"], ['[b.py] import a', '再次执行 a.py'], ['[a.py] 开始', "__name__ = 'a'"], ['结果', '两份模块对象']], 'hl': ['结果']}),
    step("pickle:类 Point 定义在 __main__ 里,pickle 里记录的类路径就是 __main__.Point。换一个脚本去 load,那个脚本的 __main__ 里没有 Point → AttributeError。", fl=FL([4], [0, 1, 2, 3]),
         kv={'items': [['save.py 写入的类路径', '__main__.Point'], ['load.py 读取', "AttributeError: module '__main__' has no attribute 'Point'"]], 'hl': ['load.py 读取']}),
    step("multiprocessing 在 macOS 上默认 spawn:子进程会重新导入主脚本。没有 if __name__ == '__main__' 保护,就会在子进程里再次启动新进程——Python 直接拒绝并报 RuntimeError。加了保护就正常。", fl=FL([4], [0, 1, 2, 3]),
         kv={'items': [['mp_bad.py(无保护)', 'RuntimeError: …before the current process has finished its bootstrapping phase'], ['mp_ok.py(有保护)', "正常;默认启动方式 = spawn"]], 'hl': ['mp_bad.py(无保护)']}),
]
A = dict(
    n=89,
    tags='Python,CPython,模块,真实验证,动画演示',
    desc='本机真实对同一个文件分别用 python 文件 / python -m / import 三种方式运行:__name__、__package__、__spec__、sys.path[0] 和相对导入是否可用各不相同;a.py 与 b.py 互相导入会让 a.py 的顶层代码执行两次;定义在 __main__ 里的类 pickle 后在别处读取报 AttributeError;macOS 默认 spawn 下缺少 __main__ 保护会报 RuntimeError。',
    lead='<code>if __name__ == "__main__":</code> 几乎每个 Python 文件里都有,但它背后的含义远不止「防止导入时执行」。这篇用同一个文件的三种运行方式,把 <code>__name__</code>、<code>__package__</code>、<code>sys.path[0]</code> 的差异一项项摊开,再看 <code>__main__</code> 引起的三个典型问题。',
    facts=[('__name__ 都是 "__main__"', '脚本和 -m 运行时相同,区别在 __package__ 与相对导入'), ('执行两次', 'a.py 当脚本运行、又被 b.py 导入时,顶层代码跑了两遍'), ('RuntimeError', 'macOS(spawn)下缺少 __main__ 保护时,multiprocessing 的结果')],
    body=[
        sec('验证一:同一个文件,三种运行方式', '', src('pkg/tool.py', '''import sys
print("__name__      =", repr(__name__))
print("__package__   =", repr(__package__))
print("__spec__      =", None if __spec__ is None else "ModuleSpec(name=%r)" % __spec__.name)
print("sys.path[0]   =", repr(sys.path[0]))
try:
    from .util import hi; print("相对导入 from .util import hi →", hi())
except ImportError as e: print("相对导入 →", type(e).__name__ + ":", e)'''), term('', one),
            '<p><code>python pkg/tool.py</code> 是「脚本」方式:没有所属的包,相对导入直接失败,<code>sys.path[0]</code> 是 <code>pkg/</code> 目录本身。<code>python -m pkg.tool</code> 是「模块」方式:Python 先按包结构找到它,<code>__package__</code> 是 <code>pkg</code>、有完整的 <code>__spec__</code>,相对导入才能工作,<code>sys.path[0]</code> 是当前工作目录。<b>两种方式下 <code>__name__</code> 都是 <code>"__main__"</code></b>,只有被 import 时才是模块的真名。包内的文件要用相对导入,就用 <code>-m</code> 启动。</p>'),
        sec('验证二:同一个文件被执行两次', '', term('', block('== 二', '== 三')),
            '<p>a.py 作为脚本运行时,它在 <code>sys.modules</code> 里的名字是 <code>__main__</code>,不是 <code>a</code>。当 b.py 里 <code>import a</code> 时,Python 找不到名叫 <code>a</code> 的已导入模块,只好把 a.py 重新执行一遍(这次 <code>__name__</code> 是 <code>"a"</code>)——顶层代码执行了两次,而且得到两个互不相干的模块对象,里面的类、全局变量也各有一份。</p>'),
        sec('验证三:pickle 记住的是 __main__.Point', '', term('', block('== 三', '== 四')),
            '<p>类定义在被当作脚本运行的文件里,它的模块名就是 <code>__main__</code>,pickle 也就把 <code>__main__.Point</code> 写进了字节流。换一个脚本去 <code>load</code>,新脚本的 <code>__main__</code> 里没有 <code>Point</code>,得到 <code>AttributeError</code>。需要持久化的类,要放在可以 import 的模块里,别定义在入口脚本里。</p>'),
        sec('验证四:spawn 与 __main__ 保护', '', term('', block('== 四', '== 五')),
            '<p>本机 macOS 上 <code>multiprocessing</code> 默认的启动方式是 <code>spawn</code>:子进程是一个全新的解释器,它会把主脚本重新导入一遍来找到 <code>target</code>。如果主脚本顶层没有 <code>if __name__ == "__main__":</code> 保护,子进程导入它时又会去启动新进程——Python 检测到这种情况,直接抛出 <code>RuntimeError</code>,而不是无限套娃。(默认启动方式在别的系统上不同,这里只在 macOS 上验证。)</p>'),
        sec('验证五:目录、zip 也能作为程序,runpy 可以在代码里模拟', '', term('', block('== 五', 'zzzz')),
            '<p>只要目录或 zip 里有 <code>__main__.py</code>,就能用 <code>python 目录/</code> 或 <code>python -m 包名</code> 运行,里面的 <code>__name__</code> 也是 <code>"__main__"</code>。<code>runpy.run_path</code> 默认把 <code>__name__</code> 设成 <code>"&lt;run_path&gt;"</code>,要模拟「直接运行」得显式传 <code>run_name="__main__"</code>。</p>'),
        sec('分步演示:同一份代码,几种运行方式下的差别', '每一项都是上面的实际输出',
            demo('__main__ 的几种面貌', [('fl', 'flow', '场景'), ('kv', 'kv', '观察')], steps, '关键差异')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>multiprocessing</code>、<code>pickle</code>、<code>runpy</code>',
          '没有验证:Linux 上 fork 启动方式下缺少保护的表现、<code>python -m</code> 运行子包/命名空间包的其他规则、Windows'],
)
