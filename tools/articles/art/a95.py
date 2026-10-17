import json
from lib import *
txt = out('95').splitlines(); R = json.load(open('out/95.json'))['res']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
FL = lambda cur, done=(): {'nodes': [['pyproject.toml', '声明'], ['pip install', '写 entry_points.txt'], ['启动脚本', 'bin/hello-cli'], ['entry_points()', '只读元数据'], ['.load()', '才导入代码']], 'cur': cur, 'done': list(done)}
steps = [
    step("pyproject.toml 里声明了两类入口:[project.scripts] 的 hello-cli(命令行),和 [project.entry-points.\"hello_app.plugins\"] 下的 upper、reverse(插件)。", fl=FL([0]),
         kv={'items': [['scripts', 'hello-cli = hello_app.cli:main'], ['entry-points 组 hello_app.plugins', 'upper = hello_app.plugins:upper · reverse = hello_app.plugins:reverse']], 'hl': ['scripts']}),
    step("构建出的 wheel 里带了一个 entry_points.txt,pip 安装时把它放进 dist-info:一个 INI 风格的文本文件,每个组一节。", fl=FL([1], [0]),
         kv={'items': [['[console_scripts]', 'hello-cli = hello_app.cli:main'], ['[hello_app.plugins]', 'upper = …:upper · reverse = …:reverse']], 'hl': ['[console_scripts]']}),
    step("pip 读 [console_scripts],在 env/bin/ 里生成一个可执行脚本 hello-cli:几行 Python——import 那个函数、调用、退出。命令行入口就是这么来的。", fl=FL([2], [0, 1]),
         kv={'items': [['env/bin/hello-cli', 'from hello_app.cli import main → sys.exit(main())'], ['运行 hello-cli a b', "argv = ['a', 'b']"]], 'hl': ['env/bin/hello-cli']}),
    step("另一个进程里 entry_points(group='hello_app.plugins'):找到 reverse 和 upper——但此时 hello_app 根本没有被导入,只读了元数据文件。", fl=FL([3], [0, 1, 2]),
         kv={'items': [['找到', "['reverse', 'upper']"], ['hello_app 已导入?', 'False']], 'hl': ['hello_app 已导入?']}),
    step("对一个 EntryPoint 调 load():这时才导入 hello_app 和 hello_app.plugins,返回函数 upper;upper('abc') = ABC。", fl=FL([4], [0, 1, 2, 3]),
         kv={'items': [['load() 之后 hello_app 已导入?', 'True'], ["upper('abc')", 'ABC']], 'hl': ['load() 之后 hello_app 已导入?']}),
    step("手工往 site-packages 放一个假的 dist-info(只有 METADATA 和 entry_points.txt):ghost 立刻「被发现」;但 load() 才会发现它指向的 nowhere 模块不存在。", fl=FL([3, 4]),
         kv={'items': [['发现', "['ghost', 'reverse', 'upper']"], ["ghost.load()", "ModuleNotFoundError: No module named 'nowhere'"]], 'hl': ["ghost.load()"]}),
    step("代价:entry_points() 要扫描 sys.path 上所有 dist-info。已安装的包越多越慢。", fl=FL([3]),
         b={'items': [[f'额外 {n} 个包', ms, f'{ms:.1f} ms'] for n, ms in R], 'max': R[-1][1], 'cur': [3]}),
]
A = dict(
    n=95,
    tags='Python,打包,插件,真实验证,动画演示',
    desc=f'本机在全新虚拟环境里真实安装一个项目:pip 把 [project.scripts] 变成 env/bin/hello-cli 几行启动脚本,把 entry-points 写进 dist-info/entry_points.txt;importlib.metadata.entry_points() 只读元数据、不导入代码,load() 才导入;手工放一个假 dist-info 就能「发现」不存在的插件;扫描成本随已安装包数增长(0 → 1600 个:{R[0][1]:.1f} → {R[-1][1]:.0f} ms)。',
    lead='装完一个包,终端里就多了一个命令;装完另一个包,某个程序就多了一个插件——它们靠的是同一个机制:entry points。这篇在一个全新的虚拟环境里真的装一遍,一路看到:命令行脚本长什么样、插件是怎么被「发现」而不导入的、发现的成本有多大。',
    facts=[('6 行', 'pip 生成的命令行启动脚本 hello-cli 的全部内容(含 shebang):import → 调用 → 退出'), ('不导入代码', 'entry_points() 只读 dist-info 里的文本,load() 才导入'), (f'{R[0][1]:.0f} → {R[-1][1]:.0f} ms', '已安装的包从 0 增加到 1600 个时,一次 entry_points 查询的耗时')],
    body=[
        sec('做的事:声明入口,安装,再去发现', '',
            src('pyproject.toml(节选)', '''[project.scripts]
hello-cli = "hello_app.cli:main"

[project.entry-points."hello_app.plugins"]
upper = "hello_app.plugins:upper"
reverse = "hello_app.plugins:reverse"'''),
            '<p>build backend 是第 94 篇里那个手写的最小后端,多加了一步:把这两段写进 wheel 里的 <code>entry_points.txt</code>。安装用的是 pip,装进一个全新的虚拟环境。</p>',
            term('', block('== 一', '== 二'))),
        sec('验证一:命令行脚本只是 pip 生成的几行', '', term('', block('== 二', '== 三')),
            '<p><code>[console_scripts]</code> 里的 <code>hello-cli = hello_app.cli:main</code>,被 pip 变成 <code>env/bin/hello-cli</code>:一个以虚拟环境 Python 为解释器的脚本,<code>from hello_app.cli import main</code> 然后 <code>sys.exit(main())</code>。所以命令行工具其实就是「一个 import + 一次函数调用」。卸载时这个脚本会被 pip 一并删除(见验证五)。</p>'),
        sec('验证二:插件发现只读元数据,不导入代码', '', term('', block('== 三', '== 四')),
            '<p><code>importlib.metadata.entry_points(group=...)</code> 返回的每个 <code>EntryPoint</code> 只包含名字、字符串形式的 <code>value</code>、所属分发包——这个时候 <code>hello_app</code> 完全没有被导入(<code>"hello_app" in sys.modules</code> 是 False)。只有调用 <code>.load()</code> 才会导入模块并返回那个对象。这就是插件系统可以「先列出所有可用插件,用户选了哪个再加载哪个」的原因,也避免了因为某个插件写得差而拖慢整个程序启动。</p>'),
        sec('验证三:「被发现」只取决于元数据文件', '', term('', block('== 四', '== 五')),
            '<p>我没有安装任何包,只是往 site-packages 里手工放了一个只有 <code>METADATA</code> 和 <code>entry_points.txt</code> 的目录,插件 <code>ghost</code> 就出现在列表里;直到 <code>load()</code> 才发现它指向的 <code>nowhere</code> 模块并不存在。所以发现阶段拿到的名字不代表能用——加载时要处理 ImportError。</p>'),
        sec('验证四:卸载之后', '', term('', block('== 五', '== 六')),
            '<p>卸载后启动脚本被删,再查 <code>entry_points</code> 得到空列表——机制的另一面:一切都由 dist-info 文件的存在与否决定。</p>'),
        sec('验证五:发现的成本', '', term('', block('== 六', 'zzzz')),
            f'<p>额外的每个已安装包只带一个 entry point 时,一次 <code>entry_points(group=...)</code> 要遍历所有 <code>dist-info</code>:空环境 {R[0][1]:.1f} ms,1600 个包 {R[3][1]:.0f} ms。所以不要在热路径里反复调用,启动时查一次并缓存。(这个测试的 dist-info 是我批量生成的最小文件,真实包的元数据更大,数字仅作量级参考。)</p>'),
        sec('分步演示:从声明到被发现', '每一步的内容都是上面实验的真实输出',
            demo('entry points 的一生', [('fl', 'flow', '阶段'), ('kv', 'kv', '观察'), ('b', 'bars', '扫描耗时')], steps, '当前阶段 / 数据')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,pip 26.2.1,标准库 <code>importlib.metadata</code>;打包用的是自己写的最小 build backend',
          '没有验证:<code>gui_scripts</code>、Windows 上生成的 .exe 启动器、setuptools / hatchling 对 entry points 的额外处理、多个包声明同名 entry point 时的冲突'],
)
