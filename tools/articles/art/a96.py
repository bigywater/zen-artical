from lib import *
txt = out('96').splitlines()
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
FL = lambda cur, done=(): {'nodes': [['项目源码', 'projA/src'], ['site-packages', '安装到哪'], ['import', 'sys.path'], ['改源码后', '是否生效']], 'cur': cur, 'done': list(done)}
steps = [
    step("普通安装:site-packages 里多了一整份 hello_pkg 的拷贝。import 得到的 __file__ 在 site-packages 里,不在你的项目目录。", fl=FL([1]),
         kv={'items': [['site-packages', "['hello_pkg', 'hello_pkg-0.1.0.dist-info']"], ['hello_pkg.__file__', '…/envA/lib/python3.14/site-packages/hello_pkg/__init__.py']], 'hl': ['hello_pkg.__file__']}),
    step("把项目里的源码改成 v2:新进程里 import 出来的还是 v1——因为读的是那份拷贝。", fl=FL([3], [0, 1]),
         kv={'items': [['项目源码', 'v2'], ['import 得到', 'v1(旧)']], 'hl': ['import 得到']}),
    step("可编辑安装(pip install -e):site-packages 里没有代码,只有一个 __editable__.hello_pkg.pth 和 dist-info。", fl=FL([1]),
         kv={'items': [['site-packages', "['__editable__.hello_pkg.pth', 'hello_pkg-0.1.0.dist-info']"], ['dist-info/direct_url.json', '{"dir_info": {"editable": true}, "url": "file://…/projA"}']], 'hl': ['site-packages']}),
    step(".pth 文件里只有一行:项目 src 目录的路径。解释器启动时(第 86 篇)把它加进 sys.path,所以 import 直接从项目目录里读,__file__ 指向 projA/src。", fl=FL([2], [1]),
         kv={'items': [['__editable__.hello_pkg.pth', '<工作目录>/projA/src'], ['hello_pkg.__file__', '<工作目录>/projA/src/hello_pkg/__init__.py'], ['sys.path 里有 src?', 'True']], 'hl': ['__editable__.hello_pkg.pth']}),
    step("改源码(v1 → v2):新进程里立刻是 v2,不用重新安装。src 下新增一个包 newpkg,也能直接 import。", fl=FL([3], [0, 1, 2]),
         kv={'items': [['import 得到', 'v2 (改过源码)'], ['新增包 newpkg', 'import 成功']], 'hl': ['import 得到']}),
    step("但元数据不会自动更新:往 pyproject.toml 里新增命令行脚本 hello-two,env/bin/ 里仍然只有 hello-one——脚本是 pip 安装时生成的。", fl=FL([3]),
         kv={'items': [['pyproject.toml', '新增 hello-two'], ['env/bin/ 里', "['hello-one']"]], 'hl': ['env/bin/ 里']}),
    step("重新 pip install -e 之后,hello-two 才出现。", fl=FL([1], [3]),
         kv={'items': [['重新 pip install -e 后 env/bin/', "['hello-one', 'hello-two']"]], 'hl': ['重新 pip install -e 后 env/bin/']}),
    step("换成真实的 setuptools 后端:同样是一个 __editable__.hello_pkg-0.1.0.pth,内容是 projS/src;新增的包也能直接 import。卸载后 site-packages 清空,项目源码不受影响。", fl=FL([1, 2]),
         kv={'items': [['setuptools: .pth', '<工作目录>/projS/src'], ['新增包 newpkg', 'import 成功'], ['卸载后', 'site-packages 为空 · 源码仍在']], 'hl': ['setuptools: .pth']}),
]
A = dict(
    n=96,
    tags='Python,打包,pip,真实验证,动画演示',
    desc='本机在全新虚拟环境里对比普通安装与 pip install -e:普通安装拷贝一份代码、改源码不生效;可编辑安装只在 site-packages 放一个 __editable__ .pth(内容是项目 src 路径)和带 editable:true 的 direct_url.json,改源码立即生效、新增包也能 import;但新增命令行脚本必须重新安装;并用真实的 setuptools 后端复验同样结果。',
    lead='<code>pip install -e .</code> 让你改了代码立刻生效,不用每次重装。它到底改变了什么?这篇用两个后端——我自己写的最小 PEP 660 后端,和真实的 setuptools——各装一次,把 site-packages 里发生的事翻出来看。',
    facts=[('一个 .pth 文件', '可编辑安装在 site-packages 里留下的全部「代码」:一行路径'), ('v1 → v2', '改源码后可编辑安装立即生效;普通安装仍是旧版'), ('脚本要重装', '新增命令行入口不会自动出现,需要重新 pip install -e')],
    body=[
        sec('验证一:普通安装是一份拷贝', '', term('', block('== 一', '== 二')),
            '<p>装完之后 <code>hello_pkg</code> 是 site-packages 里的一个目录,<code>__file__</code> 指向它。这时候去改项目里的源码,新进程里 import 到的还是旧代码——需要重新 <code>pip install</code>。</p>'),
        sec('验证二:可编辑安装留下的只有一个 .pth', '', term('', block('== 二', '== 三')),
            '<p>site-packages 里没有任何代码:只有 <code>__editable__.hello_pkg.pth</code> 和一个 <code>dist-info</code>。.pth 里就一行——项目 <code>src</code> 目录的路径,解释器启动处理 site 时(第 86 篇)把它加进 <code>sys.path</code>,于是 <code>import hello_pkg</code> 直接读项目目录里的文件。<code>direct_url.json</code> 里的 <code>"editable": true</code> 是 pip 记下的「这是可编辑安装」标记。改源码后立刻生效,src 下新增的包也能直接 import,因为整个目录都在路径里。</p>'
            '<p>说明:这里的 .pth 做法是<b>我自己的最小后端</b>选择的实现(PEP 660 只规定接口,怎么做由后端决定)。下面用 setuptools 验证它是不是普遍做法。</p>'),
        sec('验证三:哪些东西不会随源码自动更新', '', term('', block('== 三', '== 四')),
            '<p>命令行脚本是 pip 在安装时根据元数据生成的(第 95 篇)。往 <code>pyproject.toml</code> 里新增一个脚本 <code>hello-two</code>,<code>env/bin/</code> 里并没有它,直到再执行一次 <code>pip install -e</code>。同理,依赖、版本号这些元数据变了也需要重装。</p>'),
        sec('验证四:真实的 setuptools 也是这样吗', '', term('', block('== 四', '== 五')),
            '<p>在 <code>src</code> 布局下,setuptools 生成的同样是一个 <code>__editable__.hello_pkg-0.1.0.pth</code>,内容是项目 <code>src</code> 目录,新增的包也能 import。<b>这只是 src 布局下的结果</b>:我没有验证平铺布局或多个顶层包的情形,不同布局下 setuptools 可能采用别的策略,别把这次结果当成所有情况。</p>'),
        sec('验证五:卸载', '', term('', block('== 五', 'zzzz')),
            '<p>卸载可编辑安装只删除 .pth 和 dist-info,项目源码原封不动。</p>'),
        sec('分步演示:同一次改动,普通安装与可编辑安装的差别', '所有内容取自上面的真实输出',
            demo('pip install -e 到底做了什么', [('fl', 'flow', '环节'), ('kv', 'kv', '观察')], steps, '当前观察')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,pip 26.2.1,setuptools(pip 隔离环境按需下载的当前版本);第一个后端是自己写的最小实现',
          '没有验证:setuptools 在平铺布局 / 多包布局下的策略(可能不是 .pth)、hatchling 等其他后端、<code>--config-settings editable_mode=strict</code>、编译型扩展的可编辑安装'],
)
