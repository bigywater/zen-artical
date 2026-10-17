import json
from lib import *
txt = out('80').splitlines()
R = json.load(open('out/80.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
d, zs, zp = R['目录 + __pycache__'], R['zip 里放 .py'], R['zip 里放 .pyc']
FL = lambda cur, done=(): {'nodes': [['import mypkg', ''], ['sys.path 里有 app.zip', ''], ['path_hooks: zipimporter', ''], ['读 zip + 编译', ''], ['执行进 sys.modules', '']], 'cur': cur, 'done': list(done)}
steps = [
    step("import mypkg:import 系统遍历 sys.path。我们把 app.zip 放在了最前面。", fl=FL([0]), kv={'items': [['sys.path[0]', '…/app.zip']], 'hl': ['sys.path[0]']}),
    step("对每个 sys.path 条目,依次问 sys.path_hooks:第一个 hook 是 zipimporter,它认得 zip 文件,于是这个条目的 finder 就是 zipimporter。", fl=FL([1, 2], [0]),
         kv={'items': [['sys.path_hooks', "['zipimporter', 'path_hook_for_FileFinder']"], ['path_importer_cache[app.zip]', "<class 'zipimport.zipimporter'>"]], 'hl': ['path_importer_cache[app.zip]']}),
    step("zipimporter 在 zip 的目录里找到 mypkg/__init__.py,给出 spec:origin 指向 app.zip/mypkg/__init__.py(路径里把 zip 当成了目录)。", fl=FL([2], [0, 1]),
         kv={'items': [['__spec__.origin', '<临时目录>/app.zip/mypkg/__init__.py'], ['__loader__', "<class 'zipimport.zipimporter'>"]], 'hl': ['__spec__.origin']}),
    step("加载器读出源码、解压、编译成代码对象,exec 进新模块。zip 里没有写入任何 .pyc;zip 内容和旁边目录都没变。", fl=FL([3], [0, 1, 2]),
         kv={'items': [['import 之后 zip 内容变化?', 'False'], ['出现 __pycache__?', 'False']], 'hl': ['import 之后 zip 内容变化?']}),
    step("所以每个新进程 import zip 里的 .py 都要重新编译:同一份 9000 行模块,这里测得——", fl=FL([4], [0, 1, 2, 3]),
         kv={'items': [['结论', '每次都要编译']], 'hl': ['结论']},
         b={'items': [['目录+__pycache__', d, f'{d:.2f} ms']], 'max': zs, 'cur': [0]}),
    step("zip 里放 .py:50 ms 左右——比目录里有缓存的 pyc 慢了几十倍。", fl=FL([4], [0, 1, 2, 3]),
         kv={'items': [['结论', '编译成本被每次启动重复支付']], 'hl': ['结论']},
         b={'items': [['目录+__pycache__', d, f'{d:.2f} ms'], ['zip 里放 .py', zs, f'{zs:.2f} ms']], 'max': zs, 'cur': [1]}),
    step("zip 里放预编译好的 .pyc:恢复到几毫秒,略高于目录(要解压)。", fl=FL([4], [0, 1, 2, 3]),
         kv={'items': [['结论', '要快,就把 .pyc 打进 zip']], 'hl': ['结论']},
         b={'items': [['目录+__pycache__', d, f'{d:.2f} ms'], ['zip 里放 .py', zs, f'{zs:.2f} ms'], ['zip 里放 .pyc', zp, f'{zp:.2f} ms']], 'max': zs, 'cur': [2]}),
]
A = dict(
    n=80,
    tags='Python,标准库,导入系统,真实验证,动画演示',
    desc=f'本机真实建 zip 包放进 sys.path 导入:加载器是 zipimport.zipimporter,导入过程不会往 zip 里写 .pyc;相对 __file__ 打开包内数据文件抛 NotADirectoryError,pkgutil / importlib.resources 可以;zip 里的 .so 被忽略;同一 9000 行模块导入用时:目录 {d:.2f} ms、zip 里放 .py {zs:.1f} ms、zip 里放 .pyc {zp:.2f} ms。',
    lead='Python 能直接 <code>import</code> 一个 zip 里的代码,<code>.pyz</code> 可执行文件和很多打包工具都靠它。但 zip 不是目录:哪些事情能做、哪些不能、快不快,这篇都拿真实的 zip 包测了一遍。',
    facts=[('zipimporter', '导入 zip 里的模块时,__loader__ 的类型'), (f'{zs:.0f} ms vs {d:.1f} ms', '9000 行模块:zip 里放 .py 与目录(有 pyc 缓存)'), ('NotADirectoryError', '相对 __file__ 读 zip 里的数据文件的结果')],
    body=[
        sec('做的事:造一个 zip 包再导入', '',
            src('实验脚本(节选)', '''# src/mypkg/{__init__.py, mod.py, data.txt} 压成 app.zip
sys.path.insert(0, os.path.abspath("app.zip"))
import mypkg, mypkg.mod
print(mypkg.mod.__file__, type(mypkg.__loader__))'''),
            term('', block('== 一', '== 二'))),
        sec('验证一:zip 在导入系统里就是一个「目录」', '',
            '<p>路径里的 <code>app.zip/mypkg/mod.py</code> 把 zip 当成了目录。<code>sys.path_hooks</code> 里有两个 hook:<code>zipimporter</code> 认得 zip 文件,<code>path_hook_for_FileFinder</code> 认得普通目录;<code>sys.path_importer_cache</code> 里 app.zip 对应的就是 <code>zipimporter</code> 对象。</p>'
            '<p>还有一处值得注意:import 之后 zip 文件的内容没变,zip 旁边也没有出现 <code>__pycache__</code>——zipimport 从不往 zip 里写字节码缓存。</p>'),
        sec('验证二:包里的数据文件不能相对 __file__ 找', '', term('', block('== 二', '== 三')),
            '<p>因为 <code>__file__</code> 指向的是「zip 里的一个虚拟路径」,操作系统不认识,直接 <code>open</code> 得到 <code>NotADirectoryError</code>。走 <code>pkgutil.get_data</code> 或 <code>importlib.resources.files</code> 就没问题,这两个接口会通过 loader 读。写包时如果要兼容 zip 分发,数据文件一律用这两个接口读。</p>'),
        sec('验证三:扩展模块(.so)不能从 zip 里加载', '', term('', block('== 三', '== 四')),
            '<p>第一个实验里,zip 里放了真实的 <code>array.cpython-314-darwin.so</code> 并排在路径最前,<code>import array</code> 依然来自标准库自带的目录——zip 里的那份被静默忽略。第二个实验把 .so 改名为 <code>myext</code>,只有 zip 里有它,结果是 <code>ModuleNotFoundError</code>——zipimporter 根本不把 .so 当作可导入的模块。带 C 扩展的包(numpy 之类)不能整个塞进 zip 运行。</p>'),
        sec('验证四:python app.pyz', '', term('', block('== 四', '== 五')),
            '<p><code>python -m zipapp</code> 只是把目录打包成 zip,并在开头加一行 <code>#!</code> 解释器行(输出里能看到它在 <code>PK</code> 头之前)。之所以能直接执行,是因为 Python 遇到 zip 文件名会把它当成 sys.path 条目,并运行其中的 <code>__main__.py</code>。</p>'),
        sec('验证五:zip 里放 .py 导入更慢', '每次进程启动都要重新编译', term('', block('== 五', 'zzzz')),
            f'<p>同一份 8999 行的模块,在三种放法下导入耗时(各 9 次取中位数):目录里已有 <code>__pycache__</code> 只要 {d:.2f} ms;zip 里放 <code>.py</code> 要 {zs:.1f} ms,因为每个新进程都要重新编译一遍;zip 里放预先编译好的 <code>.pyc</code> 是 {zp:.2f} ms。所以对启动速度有要求的 zip 分发,应该把 <code>.pyc</code> 打进去(本实验里的 .pyc 是用 <code>py_compile</code> 生成的)。</p>'),
        sec('分步演示:一次 zip 导入,和三种放法的速度', '数据是上面实验的实测结果',
            demo('zipimport 的导入路径', [('fl', 'flow', '导入流程'), ('kv', 'kv', '真实观察'), ('b', 'bars', '导入 9000 行模块的耗时')], steps, '此刻的阶段 / 数据')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>zipimport</code>、<code>zipapp</code>、<code>pkgutil</code>、<code>importlib.resources</code>',
          '没有验证:zip64、有密码的 zip、zip 里同时有 .py 和 .pyc 时的优先级、Windows 上的路径分隔符差异'],
)
