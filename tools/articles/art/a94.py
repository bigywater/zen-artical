import json
from lib import *
txt = out('94').splitlines()
R = json.load(open('out/94.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
r1, r2, r3 = R['r1'], R['r2'], R['r3']
short = lambda p: 'build-env-…/bin/python(临时隔离环境)' if 'build-env-' in p else p.replace(os.environ.get('HERE', ''), '<scratch>') if False else ('venv/bin/python(当前环境)')
FL = lambda cur, done=(): {'nodes': [['pyproject.toml', '[build-system]'], ['前端', 'build / pip'], ['后端子进程', '每个钩子一个'], ['wheel 文件', 'zip']], 'cur': cur, 'done': list(done)}
steps = [
    step("pyproject.toml 里的 [build-system] 只声明三件事:build 需要的包(requires)、后端是谁(build-backend)、后端代码去哪找(backend-path)。它自己不做任何构建。", fl=FL([0]),
         kv={'items': [['requires', '[]'], ['build-backend', 'mybackend'], ['backend-path', "['backend']"]], 'hl': ['build-backend']}),
    step(f"前端(python -m build)启动,pid={r1[0]['ppid']}。默认「隔离」:先建一个临时虚拟环境,后端将在那个环境的 Python 里运行。", fl=FL([1], [0]),
         kv={'items': [['前端 pid', str(r1[0]['ppid'])], ['后端将使用的 python', 'build-env-…/bin/python(临时隔离环境)']], 'hl': ['后端将使用的 python']}),
    step(f"前端调用第一个钩子 get_requires_for_build_wheel:它没有在自己进程里 import 后端,而是启动了一个新进程(pid={r1[0]['pid']},父进程 {r1[0]['ppid']}),cwd 是项目目录。", fl=FL([2], [0, 1]),
         kv={'items': [['钩子', 'get_requires_for_build_wheel'], ['后端进程 pid / ppid', f"{r1[0]['pid']} / {r1[0]['ppid']}"]], 'hl': ['后端进程 pid / ppid']}),
    step(f"第二个钩子 build_wheel:又是一个新进程(pid={r1[1]['pid']}),父进程还是 {r1[1]['ppid']}——每个钩子调用一个独立子进程,互相不共享内存。", fl=FL([2], [0, 1]),
         kv={'items': [['钩子', 'build_wheel'], ['后端进程 pid / ppid', f"{r1[1]['pid']} / {r1[1]['ppid']}"]], 'hl': ['后端进程 pid / ppid']}),
    step("产物 hello_pkg-0.1.0-py3-none-any.whl 只是一个 zip:包代码 + dist-info(METADATA、WHEEL、RECORD)。", fl=FL([3], [0, 1, 2]),
         kv={'items': [['hello_pkg/__init__.py', '40 字节'], ['…dist-info/METADATA', '72 字节'], ['…dist-info/WHEEL', '80 字节'], ['…dist-info/RECORD', '286 字节']], 'hl': ['…dist-info/METADATA']}),
    step("换 pip 作前端:pip install . 调用了三个钩子——多了 prepare_metadata_for_build_wheel(先只要元数据,用来做依赖解析)。", fl=FL([1, 2], [0]),
         kv={'items': [[f'{i+1}. {x["hook"]}', f'pid={x["pid"]}'] for i, x in enumerate(r3)], 'hl': ['2. prepare_metadata_for_build_wheel']}),
    step("后端里抛异常:前端只看到「Backend subprocess exited when trying to invoke build_wheel」,构建失败、返回码 1。", fl=FL([2]),
         kv={'items': [['返回码', '1'], ['前端报错', 'Backend subprocess exited when trying to invoke build_wheel']], 'hl': ['前端报错']}),
]
A = dict(
    n=94,
    tags='Python,打包,PEP 517,真实验证,动画演示',
    desc='本机真实用一个自己写的最小 build backend(通过 backend-path 放在项目里,requires 为空)验证 pyproject.toml 的构建流程:python -m build 与 pip 作为前端,每个钩子都在一个独立的后端子进程里执行(pid 各不相同,父进程是前端),默认隔离环境使用临时 build-env 的 Python;pip 比 build 多调用 prepare_metadata_for_build_wheel;产出的 wheel 只是含 dist-info 的 zip。',
    lead='<code>pyproject.toml</code> 里那几行 <code>[build-system]</code> 到底是谁读、谁执行?这篇不用任何第三方构建后端,而是自己写了一个最小的 PEP 517 后端,让它在被调用时把 pid、Python 路径都记下来——这样「前端」和「后端」的分工就看得一清二楚。',
    facts=[('每个钩子一个进程', '后端每个钩子都在独立子进程里执行,父进程是前端'), ('3 个钩子', 'pip install . 依次调用 get_requires / prepare_metadata / build_wheel'), ('wheel = zip', '产物只是包代码加 dist-info')],
    body=[
        sec('做的事:自己写一个 build backend', '',
            term('pyproject.toml', block('== 一', '== 二').split('\n',1)[1] if False else '\n'.join(block('== 一', '== 二').splitlines()[0:9])),
            '<p><code>backend-path</code> 让后端就放在项目里;<code>requires</code> 是空列表,没有任何构建工具需要安装。后端只是一个 Python 模块,实现几个约定好的函数(钩子):<code>get_requires_for_build_wheel</code>、<code>prepare_metadata_for_build_wheel</code>、<code>build_wheel</code>。每个钩子被调用时,先往日志里写下自己的 pid、父进程 pid、<code>sys.executable</code> 和当前目录。</p>'),
        sec('验证一:build 作为前端——每个钩子一个子进程', '', term('', block('== 二', '== 三')),
            '<p>看两栏关键数据:<b>pid 每个钩子都不同,ppid 却都相同</b>——前端进程只启动子进程去调用后端,自己不 <code>import</code> 后端。默认(隔离)模式下,后端使用的是 <code>build-env-…/bin/python</code>,一个临时创建的虚拟环境,所以它看不到你当前环境里装的包,只能用 <code>requires</code> 里声明的;加上 <code>--no-isolation</code> 就直接使用当前环境的 Python。构建之前的所有准备工作,都是前端做的。</p>'),
        sec('验证二:pip 也是前端,只是调用得更细', '', term('', block('== 三', '== 四')),
            '<p>pip 装一个源码目录时,先调 <code>get_requires_for_build_wheel</code> 看还需要什么,再调 <code>prepare_metadata_for_build_wheel</code> 只生成元数据(用来做依赖解析,不必真的构建),最后才 <code>build_wheel</code>。装完的目录里只有包本身和 <code>dist-info</code>,<code>import hello_pkg</code> 直接可用。</p>'),
        sec('验证三:wheel 里有什么', '', term('', block('== 四', '== 五')),
            '<p>wheel 就是个 zip:包文件、<code>METADATA</code>(名称、版本、摘要,来自 <code>[project]</code>)、<code>WHEEL</code>(格式说明)、<code>RECORD</code>(每个文件的哈希和大小)。我的后端手写了这几样,pip 完全认账——说明「怎么把源码变成 wheel」这件事,pip 并不关心,它只认接口。</p>'),
        sec('验证四:后端出错', '', term('', block('== 五', 'zzzz')),
            '<p>后端的异常发生在子进程里,前端只报告「Backend subprocess exited when trying to invoke build_wheel」并给出排错提示(<code>--env-dir</code> 保留构建环境)。所以构建失败时,真正的原因要往上翻子进程打印的回溯,而不是看最后这一行。</p>'),
        sec('分步演示:一次 python -m build 的流程', '进程号、路径都取自后端实际写下的日志',
            demo('pyproject.toml 由谁执行', [('fl', 'flow', '谁在做事'), ('kv', 'kv', '观察')], steps, '当前主角 / 数据')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7;<code>build</code> 1.6.1、<code>pip</code> 26.2.1(装在临时虚拟环境);后端是我自己写的最小实现,没有用 setuptools / hatchling',
          '没有验证:setuptools、hatchling 等真实后端的钩子调用差异、sdist 构建、需要联网安装 <code>requires</code> 时的行为、可编辑安装钩子(见第 96 篇)'],
)
