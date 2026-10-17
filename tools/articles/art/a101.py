import json
from lib import *
txt = out('101').splitlines(); J = json.load(open('out/101.json')); t1, t2, t3, tn = J['t']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
FL = lambda cur, done=(): {'nodes': [['tox.ini / noxfile.py', '声明解释器矩阵'], ['创建虚拟环境', '每个版本一个'], ['运行命令', '在各自环境里'], ['汇总', '哪个版本挂了']], 'cur': cur, 'done': list(done)}
steps = [
    step("tox.ini 里只写两个环境名:py312 和 py314。tox 会去找对应版本的解释器。项目里的 check.py 要求 3.14 的 t-string 语法。", fl=FL([0]),
         kv={'items': [['envlist', 'py312, py314'], ['commands', 'python check.py']], 'hl': ['envlist']}),
    step("py312:tox 在 .tox/py312 建了一个虚拟环境,用的是 Homebrew 的 3.12.14。在里面运行:annotationlib 不存在、t-string 语法不存在 → 断言失败,退出码 1。", fl=FL([1, 2], [0]),
         m={'values': [['环境', '解释器', 'annotationlib', 't-string', '结果'], ['py312', '3.12.14', 'False', 'False', 'FAIL']], 'cur': [[1, 4]], 'mark': [[1, 2], [1, 3]], 'done': []}),
    step("py314:.tox/py314 里的 3.14.7:两项都是 True,通过。同一份命令,在两个版本上的结果不同——这正是多版本测试要发现的事。", fl=FL([1, 2], [0]),
         m={'values': [['环境', '解释器', 'annotationlib', 't-string', '结果'], ['py312', '3.12.14', 'False', 'False', 'FAIL'], ['py314', '3.14.7', 'True', 'True', 'OK']], 'cur': [[2, 4]], 'mark': [[1, 2], [1, 3]], 'done': [[2, 2], [2, 3]]}),
    step("汇总:py312: FAIL code 1;py314: OK;整体 evaluation failed。任何一个环境失败,tox 的退出码就是非零。", fl=FL([3], [0, 1, 2]),
         kv={'items': [['py312', 'FAIL code 1 (0.44 s)'], ['py314', 'OK (0.21 s)'], ['整体', 'evaluation failed :(']], 'hl': ['整体']}),
    step("速度:首次运行(要创建环境)约 %.1f s;第二次直接复用 .tox 里的环境只要 %.1f s;tox -r 强制重建 %.1f s。这里的环境很轻(没有装任何依赖),装了依赖后差距会大得多。" % (t1, t2, t3), fl=FL([1]),
         b={'items': [['第一次(创建环境)', t1, f'{t1:.1f} s'], ['第二次(复用)', t2, f'{t2:.1f} s'], ['tox -r(重建)', t3, f'{t3:.1f} s']], 'max': max(t1, t3), 'cur': [1]}),
    step("nox:同样的事用 Python 写。@nox.session(python=[\"3.12\", \"3.14\"]) 展开成 tests-3.12 和 tests-3.14 两个 session,再加一个 only_new。", fl=FL([0]),
         kv={'items': [['nox -l', 'tests-3.12 · tests-3.14 · only_new']], 'hl': ['nox -l']}),
    step("运行 nox -s tests:环境放在 .nox/tests-3-12 与 .nox/tests-3-14;结果和 tox 一致——3.12 失败、3.14 成功;日志里能看到每个 session 用了哪个解释器创建虚拟环境。", fl=FL([2, 3], [0, 1]),
         kv={'items': [['tests-3.12', 'failed'], ['tests-3.14', 'success'], ['环境目录', '.nox/tests-3-12 · .nox/tests-3-14']], 'hl': ['tests-3.12']}),
    step("nox 的优势:session 是普通 Python 函数,可以写 if。only_new 里根据 session.python 决定是否输出这一句——tox.ini 里要做类似的事得靠条件因子/ini 语法。", fl=FL([0]),
         kv={'items': [['nox -s only_new', "session.log('这一步只在 3.14 上做')"]], 'hl': ['nox -s only_new']}),
]
A = dict(
    n=101,
    tags='Python,测试,tox,nox,真实验证,动画演示',
    desc=f'本机用 tox 4.64.4 和 nox 2026.8.17 在 Python 3.12.14 与 3.14.7 上跑同一份检查:py312 因为没有 annotationlib 和 t-string 语法失败、py314 通过,两者都各自建了虚拟环境(.tox/py312、.nox/tests-3-12 等);tox 首次 {t1:.1f} s、复用 {t2:.1f} s、-r 重建 {t3:.1f} s;nox 的 session 是 Python 函数,可以按 session.python 写条件。',
    lead='一个库声称支持 Python 3.10 到 3.14,谁来保证?靠 tox 或 nox:它们为每个版本建一个干净的虚拟环境,在里面跑同一套命令。这篇用同一份「3.14 才通得过」的检查,分别用两个工具跑一遍,对比它们的配置方式、产物和速度。',
    facts=[('py312 FAIL / py314 OK', '同一条命令在两个解释器版本上的结果'), (f'{t1:.1f} → {t2:.1f} s', 'tox 首次(创建环境)与再次运行(复用)的耗时'), ('ini vs Python', 'tox 用声明式配置,nox 用普通 Python 函数')],
    body=[
        sec('做的事:一份只有 3.14 通得过的检查', '', src('feat.py(检查内容)', '''def features():
    out = {"python": ".".join(map(str, sys.version_info[:3]))}
    try: import annotationlib; out["annotationlib"] = True    # 3.14 才有
    except ImportError: out["annotationlib"] = False
    try: compile('t"hello {1}"', "<t>", "eval"); out["t_strings"] = True   # 3.14 才有的语法
    except SyntaxError: out["t_strings"] = False
    return out'''),
            '<p><code>check.py</code> 调用 <code>features()</code> 并断言 t-string 可用。本机有 Homebrew 装的 3.12.14 和 3.14.7,两个版本正好用来对照。为了让实验可重复,我把 virtualenv 的缓存目录指到了临时目录,没有动系统上的配置。</p>'),
        sec('验证一:tox——一份 ini,多个解释器', '', term('', block('== 一', '== 二')),
            '<p><code>tox.ini</code> 里只写了 <code>envlist = py312, py314</code>,tox 按环境名找解释器,在 <code>.tox/py312</code>、<code>.tox/py314</code> 各建一个虚拟环境(<code>py312</code> 里的 <code>python</code> 最终指向 Homebrew 的 3.12.14)。同样的 <code>python check.py</code>,在 3.12 上因为 <code>annotationlib</code> 不存在、t-string 语法也不支持而断言失败(退出码 1),在 3.14 上通过。汇总行里 <code>py312: FAIL code 1</code>、<code>py314: OK</code>,整体 <code>evaluation failed</code>——任何一个环境失败,进程退出码非零,CI 就会变红。</p>'
            f'<p>速度上:首次 {t1:.1f} s,第二次复用环境 {t2:.1f} s,<code>tox -r</code> 强制重建 {t3:.1f} s。这里环境里什么都没装(<code>skip_install = true</code>),所以创建很快;真实项目里装依赖会让「首次」慢得多,这也是 tox 默认复用环境的原因。</p>'),
        sec('验证二:nox——同样的事,用 Python 写', '', term('', block('== 二、', 'zzzz')),
            '<p><code>@nox.session(python=["3.12", "3.14"])</code> 会展开成 <code>tests-3.12</code>、<code>tests-3.14</code> 两个 session(<code>nox -l</code> 列出它们);每个 session 在 <code>.nox/</code> 下建自己的环境(目录名里的点被换成短横线)。结果与 tox 一致:3.12 失败、3.14 成功。日志里每个 session 会写明「用 python3.12 / python3 / python3.14 创建虚拟环境」——注意 3.14 那个 session 用的是 <code>python3</code>,它恰好指向 3.14,所以是否找到了预期的版本,要靠 <code>sys.version</code> 自己确认,这也是上面 <code>check.py</code> 要把版本打印出来的原因。</p>'
            '<p>nox 最大的区别是 session 就是普通 Python 函数:<code>only_new</code> 里用 <code>if session.python == "3.14"</code> 决定要不要执行某一步。tox 想做类似的条件逻辑,得靠 ini 里的条件因子和替换语法。选哪个更多是风格问题:配置简单、大部分项目只需要「矩阵 + 命令」时 tox 很省事;流程需要逻辑判断时 nox 更自然。</p>'),
        sec('分步演示:同一份检查,在两个版本上分别发生了什么', '所有结果与耗时都来自上面的真实运行',
            demo('tox / nox 多版本测试', [('fl', 'flow', '阶段'), ('kv', 'kv', '观察'), ('m', 'matrix', '结果矩阵'), ('b', 'bars', '耗时')], steps, '当前阶段')),
    ],
    refs=['本机 macOS 27 / arm64;Python 3.12.14 与 3.14.7(Homebrew);tox 4.64.4、nox 2026.8.17(装在临时虚拟环境,virtualenv 缓存指向临时目录);两个工具都只跑了不装依赖的最简配置',
          '没有验证:多个环境并行(<code>tox -p</code>)、依赖安装与缓存、tox 与 uv 的集成、free-threaded 版本作为矩阵成员、Windows 上的解释器发现'],
)
