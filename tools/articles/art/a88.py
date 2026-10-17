import json
from lib import *
txt = out('88').splitlines()
t1, t2 = json.load(open('out/88.json'))['t']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
FL = lambda cur, done=(): {'nodes': [['import cfg', 'VALUE=1'], ['磁盘上改成 v2', 'VALUE=2 + NEW'], ['importlib.reload', '重新执行代码'], ['名字与实例', '谁更新了、谁没有']], 'cur': cur, 'done': list(done)}
steps = [
    step("import cfg,同时 from cfg import VALUE、cfg.K() 各留一份。此时 cfg 是模块对象(记下它的 id),VALUE=1,类 K 是旧类。", fl=FL([0]),
         kv={'items': [['cfg.VALUE', '1'], ['cfg.K', '旧类 K'], ['imported_value(from cfg import VALUE)', '1'], ['k_inst', '旧类的实例']], 'hl': ['cfg.VALUE']}),
    step("把 cfg.py 改成 VALUE = 2,并新增一个 NEW。磁盘上变了,但正在运行的进程里的 cfg 模块没有任何变化。", fl=FL([1], [0]),
         kv={'items': [['磁盘上 cfg.py', 'VALUE = 2 · NEW = ...'], ['内存里 cfg.VALUE', '1(还是旧的)']], 'hl': ['内存里 cfg.VALUE']}),
    step("importlib.reload(cfg):模块对象没换(id 相同),但它的代码被重新执行了一遍,结果写回同一个字典——cfg.VALUE 变成 2,多出了 NEW。", fl=FL([2], [0, 1]),
         kv={'items': [['id(cfg) 相同?', 'True'], ['cfg.VALUE', '2'], ['cfg.NEW', "'only in v2'"]], 'hl': ['cfg.VALUE', 'cfg.NEW']}),
    step("但提前拿走的东西不会跟着更新:from 导入的 VALUE 还是 1;旧类 K 与新类 K 不是同一个对象,旧实例 isinstance(k_inst, cfg.K) 变成 False。", fl=FL([3], [0, 1, 2]),
         kv={'items': [['imported_value', '1(旧值)'], ['old_K is cfg.K', 'False'], ['isinstance(k_inst, cfg.K)', 'False']], 'hl': ['imported_value', 'isinstance(k_inst, cfg.K)']}),
    step("文件里删掉的名字也不会被清理:cfg2.py 删掉 B 之后 reload,hasattr(cfg2, 'B') 仍然是 True。", fl=FL([3], [0, 1, 2]),
         kv={'items': [['cfg2.A', '10(已更新)'], ['hasattr(cfg2, "B")', 'True(残留)']], 'hl': ['hasattr(cfg2, "B")']}),
    step("另一个用途:延迟导入。LazyLoader 让 lazy('heavy') 立刻返回,模块顶层代码(sleep 0.3 秒)还没有执行。", fl=FL([2]),
         b={'items': [['lazy() 返回', t1, f'{t1:.2f} ms']], 'max': t2, 'cur': [0]}),
    step("第一次访问 h.VALUE 时才真正执行模块:这一下花了约 310 ms。", fl=FL([2]),
         b={'items': [['lazy() 返回', t1, f'{t1:.2f} ms'], ['第一次访问属性', t2, f'{t2:.1f} ms']], 'max': t2, 'cur': [1]}),
]
A = dict(
    n=88,
    tags='Python,标准库,导入系统,真实验证,动画演示',
    desc=f'本机真实验证 importlib:reload 之后模块对象 id 不变但 from 导入的旧值不更新、旧类的实例不再是新类的实例、已删除的名字残留;spec_from_file_location 能加载带连字符的文件且不进 sys.modules;find_spec 只查找不导入;LazyLoader 让 lazy() 返回 {t1:.2f} ms,首次访问属性才花 {t2:.0f} ms 执行模块。',
    lead='<code>importlib</code> 是 <code>import</code> 语句背后的那套 API:能按字符串导入、从任意路径加载文件、只查找不执行、重载、延迟加载。它们各自的边界比想象的要多——尤其是 <code>reload</code>。这篇把每个边界都做成了可运行的小实验。',
    facts=[('reload 后 id 不变', '但 from 导入的旧值、旧类的实例都不会自动更新'), ('find_spec', '只查找不执行:colorsys 前后都不在 sys.modules'), (f'{t1:.2f} → {t2:.0f} ms', 'LazyLoader:返回时 vs 第一次访问属性时')],
    body=[
        sec('验证一:按字符串导入', 'import_module 与 __import__', term('', block('== 一', '== 二')),
            '<p><code>importlib.import_module("json.decoder")</code> 直接返回你要的那个子模块;而 <code>__import__("json.decoder")</code> 返回的是顶层包 <code>json</code>,除非传 <code>fromlist</code>。写插件系统、按配置加载类时,请用 <code>import_module</code>。相对导入要带 <code>package=</code>。找不到的模块抛 <code>ModuleNotFoundError</code>,<code>e.name</code> 告诉你缺的是哪个。</p>'),
        sec('验证二:reload 到底更新了什么', '', term('', block('== 二', '== 三')),
            '<p><code>reload</code> 不会创建新模块对象:它把模块的代码在<b>同一个字典</b>里重新执行一遍。所以 <code>cfg.VALUE</code> 变成 2,新增的 <code>NEW</code> 出现了。但是:①之前用 <code>from cfg import VALUE</code> 拿走的名字是「当时的值」,不会跟着变;②类被重新定义了,<code>cfg.K</code> 是一个新的类对象,旧实例不再是新类的实例(<code>isinstance</code> 为 False)——热重载后出现「类型对不上」的诡异 bug,就是这个原因。</p>'),
        sec('验证三:reload 不会清理被删掉的名字', '', term('', block('== 三', '== 四')),
            '<p>文件里已经删掉 <code>B</code>,重新执行只会覆盖 <code>A</code>,字典里旧的 <code>B</code> 依然在。所以热重载之后模块的状态可能是「新代码 + 旧残留」的混合体,不等于重启进程。</p>'),
        sec('验证四:从任意路径加载一个文件', '', term('', block('== 四', '== 五')),
            '<p>三步走:<code>spec_from_file_location</code> 造 spec → <code>module_from_spec</code> 造空模块(此时代码没执行、也不在 <code>sys.modules</code>)→ <code>exec_module</code> 才执行。这种方式不依赖 <code>sys.path</code>,文件名带连字符(<code>my-plugin.py</code>)也可以;而且默认不会把模块放进 <code>sys.modules</code>,需要的话自己放进去。</p>'),
        sec('验证五:只查找,不导入', '', term('', block('== 五', '== 六')),
            '<p><code>find_spec</code> 返回模块的位置(spec),不执行任何模块代码:对还没导入的 <code>colorsys</code>,调用前后都不在 <code>sys.modules</code> 里。找不到时返回 <code>None</code>,可以用来做「可选依赖是否安装」的检查,不会触发模块的副作用。</p>'),
        sec('验证六:reload 会重新执行模块顶层代码', '', term('', block('== 六', '== 七')),
            '<p>模块顶层的每一行——包括打印、注册、计数——都会在每次 <code>reload</code> 时再执行一次:计数器从 1 变成了 3。所以顶层带副作用的模块不适合热重载。</p>'),
        sec('验证七:延迟导入', 'LazyLoader', term('', block('== 七', 'zzzz')),
            f'<p>用 <code>importlib.util.LazyLoader</code> 包装后,<code>lazy("heavy")</code> 只花了 {t1:.2f} ms 就返回,模块里那句 <code>sleep(0.3)</code> 没有执行;第一次访问 <code>h.VALUE</code> 才真正执行了模块,耗时约 {t2:.0f} ms。适合启动时不想为用不到的大依赖付出导入成本的场景。</p>'),
        sec('分步演示:一次 reload 前后,哪些东西变了、哪些没变', '所有值都来自上面的真实输出',
            demo('importlib.reload 与延迟加载', [('fl', 'flow', '阶段'), ('kv', 'kv', '观察'), ('b', 'bars', '延迟加载的耗时')], steps, '此刻变化的名字')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>importlib</code>、<code>importlib.util</code>',
          '没有验证:<code>importlib.metadata</code>、<code>importlib.resources</code>(见第 80 篇里的用法)、自定义 <code>sys.meta_path</code> 查找器、多线程同时导入时的锁行为'],
)
