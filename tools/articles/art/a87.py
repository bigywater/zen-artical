import json
from lib import *
txt = out('87').splitlines()
R = json.load(open('out/87.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
def scenario(title, rows, tag):
    steps = []
    lines = [f"{i}  {e}" for i, (e, o) in enumerate(rows)]
    for i, (e, o) in enumerate(rows):
        shown = [f"{k}  {rows[k][0]}" + ("  ✗ 没有" if rows[k][1] is None else f"  ✓ {rows[k][1].split('/')[-1]}") if k <= i else f"{k}  {rows[k][0]}" for k in range(len(rows))]
        note = f"{tag}第 {i} 项 {e}:" + (f"找到了 random —— {o}。搜索到此为止,后面的条目不再看。" if o else "没有 random。继续下一项。")
        steps.append(dict(note=note, s={'p': {'lines': shown, 'cur': [i] if o is None else [], 'mark': [i] if o else []}, 'r': {'items': [['import random 得到', o if o else '(还在找)']], 'hl': ['import random 得到'] if o else []}}))
        if o: break
    return steps
steps = scenario('normal', R['normal'], "【正常】") + scenario('shadow', R['shadow'], "【脚本目录里有自己写的 random.py】")
A = dict(
    n=87,
    tags='Python,CPython,导入系统,真实验证,动画演示',
    desc='本机真实验证 sys.path[0] 在 python 脚本 / -c / -m / 符号链接 / -P 下分别是什么;列出完整 sys.path 每一项来源;脚本目录里的 random.py 会遮蔽标准库(randint(1,100) 返回 4),json.py 里 import json 得到带改名建议的 AttributeError,os.py 因为已导入而无法遮蔽;300 次「先失败再创建再导入」在本机 0 次未找到。',
    lead='<code>import x</code> 找不到、或者找到的不是你想要的那个 <code>x</code>,几乎总是 <code>sys.path</code> 的问题。这篇不背规则,而是用不同的启动方式、一个故意同名的文件,把 <code>sys.path</code> 的来源和搜索顺序真实跑出来。',
    facts=[('sys.path[0]', '脚本运行时是脚本目录(符号链接会被解析),-c 时是空字符串'), ('randint(1, 100) = 4', '同目录下的 random.py 遮蔽了标准库'), ('os 不受影响', '启动时已导入的模块不会被同名文件遮蔽')],
    body=[
        sec('验证一:sys.path[0] 取决于怎么启动', '', term('', block('== 一', '== 二')),
            '<p>运行 <code>python proj/show.py</code>,<code>sys.path[0]</code> 是脚本所在的目录(不是当前工作目录);<code>-c</code> 时是空字符串(表示当前目录);<code>-m pkg.m</code> 是当前目录;通过符号链接启动时,取的是<b>符号链接指向的真实文件所在目录</b>。加 <code>-P</code>(或环境变量 <code>PYTHONSAFEPATH=1</code>)后,不再自动加入这一项,<code>sys.path[0]</code> 就变成了标准库的 zip 条目。</p>'),
        sec('验证二:完整的 sys.path 从哪来', '', term('', block('== 二', '== 三')),
            '<p>顺序是:脚本目录 → <code>PYTHONPATH</code> 的各项 → 标准库(<code>python314.zip</code>、<code>lib/python3.14</code>、<code>lib-dynload</code>)→ 用户 site-packages → 系统 site-packages。<b>越靠前优先级越高</b>,同名模块先命中的赢。第五节的 <code>sysconfig</code> 输出可以对上标准库和 site-packages 的具体位置。</p>'),
        sec('验证三:同名文件会遮蔽标准库', '', term('', block('== 三', '== 四')),
            '<p>脚本目录里放了一个自己写的 <code>random.py</code>,脚本 <code>import random</code> 拿到的是它——<code>randint(1, 100)</code> 永远返回 4;换成 <code>-P</code>,脚本目录不进 <code>sys.path</code>,才回到标准库的 <code>random</code>。文件叫 <code>json.py</code>、里面又 <code>import json</code> 时,得到 <code>AttributeError</code>,而且 3.14 的报错直接提示「可能因为同名遮蔽了标准库」。<b><code>os</code> 不会被遮蔽</b>:因为它在启动时就已经被导入进 <code>sys.modules</code>,后面的 import 直接命中缓存,根本不会去搜索 <code>sys.path</code>。所以给自己的文件起名之前,别用标准库的名字。</p>'),
        sec('验证四:运行时改 sys.path 与目录缓存', '', term('', block('== 四', '== 五')),
            '<p>运行时 <code>sys.path.insert</code> 一个目录就能从那里 import。路径查找器会缓存目录内容(<code>sys.path_importer_cache</code> 里对应 <code>FileFinder</code>),因此「先 import 失败、随后创建文件」理论上可能读到过期的目录列表,这时需要 <code>importlib.invalidate_caches()</code>。<b>但我在这台机器上没能复现</b>:连做 300 次都成功了——是否出问题取决于文件系统的时间戳精度,所以要不要调用它,别拿这一次实验当保证。</p>'),
        sec('分步演示:同一个 import random,搜索路径上谁先命中', '每一项的结果都来自对该条目单独调用 PathFinder.find_spec',
            demo('sys.path 的搜索与遮蔽', [('p', 'term', 'sys.path 各项(按顺序搜索)'), ('r', 'kv', '结果')], steps, '当前检查的条目 / 命中的条目')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7(Homebrew),路径里的 &lt;PREFIX&gt; 表示解释器安装前缀,&lt;工作目录&gt; 是临时目录',
          '没有验证:虚拟环境里的 sys.path 差异、<code>.pth</code> 与 <code>sys.path</code> 的交互(见第 86 篇)、命名空间包、Windows 上的行为'],
)
