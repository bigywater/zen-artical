import json
from lib import *
txt = out('86').splitlines()
R = json.load(open('out/86.json')); top = R['top']; res = R['res']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
t_def, t_S, t_I = res[0][1], res[1][1], res[2][1]
FL = lambda cur, done=(): {'nodes': [['解析命令行', 'argv / flags'], ['核心初始化', 'importlib · encodings'], ['site', 'site-packages · .pth · sitecustomize'], ['运行主脚本', '__main__']], 'cur': cur, 'done': list(done)}
bars = lambda k, cur: {'items': [[n, c, f'{c} µs'] for n, s, c in top[:k]], 'max': max(c for _, _, c in top), 'cur': cur}
steps = [
    step("命令行 python -I -c '…' 被解析:sys.orig_argv 保留原始参数,sys.argv 只剩 ['-c'];-I 打开了 isolated / no_user_site / ignore_environment 三个标志。", fl=FL([0]), kv={'items': [['sys.argv', "['-c']"], ['sys.flags.isolated', '1'], ['sys.flags.no_user_site', '1']], 'hl': ['sys.flags.isolated']}),
    step(f"核心初始化:先加载 _frozen_importlib_external(把 import 机制装起来)、zipimport,再加载 encodings 和 utf_8(有了它才能读写文本)、_signal。合计约 {sum(c for _,_,c in top[:5])} µs。", fl=FL([1], [0]), b=bars(5, [0, 1, 2, 3, 4])),
    step(f"然后导入 site:它单独就占了 {top[5][2]} µs,是启动最重的一项——它要 import os 等一串标准库、把 site-packages 加进 sys.path、处理 .pth 文件、导入 sitecustomize。", fl=FL([2], [0, 1]), b=bars(6, [5])),
    step("实测:用户 site-packages 里的 demo.pth 那一行 import 语句在主脚本之前就执行了,里面的路径行被加进了 sys.path;PYTHONPATH 里的 sitecustomize 也被自动导入。", fl=FL([2], [0, 1]), kv={'items': [['[.pth] demo.pth', '主脚本之前执行'], ['[sitecustomize]', '主脚本之前导入'], ['extra_path 在 sys.path?', 'True']], 'hl': ['[.pth] demo.pth', '[sitecustomize]']}),
    step("linecache 也被导入了(site 结束后),然后才把控制权交给你的脚本:__main__ 运行。", fl=FL([3], [0, 1, 2]), b=bars(7, [6])),
    step(f"加 -S(不导入 site):启动 {t_S:.1f} ms、sys.modules 只有 21 个;默认是 {t_def:.1f} ms、54 个。差的 6 ms 大部分就是 site。", fl=FL([2]), kv={'items': [['python -c pass', f'{t_def:.1f} ms · 54 个模块'], ['python -S -c pass', f'{t_S:.1f} ms · 21 个模块']], 'hl': ['python -S -c pass']}),
    step(f"加 -I(隔离):{t_I:.1f} ms,和默认几乎一样、模块数也是 54——它没有跳过 site,只是让 site 不再处理用户 site-packages 和环境变量;所以同样的 demo.pth 和 sitecustomize 都没有再执行。", fl=FL([2]), kv={'items': [['-I 下 [.pth] / [sitecustomize]', '都没有执行'], ['-I 下 extra_path', 'False'], ['-S 下 extra_path', 'False']], 'hl': ['-I 下 [.pth] / [sitecustomize]']}),
]
A = dict(
    n=86,
    tags='Python,CPython,解释器,启动,真实验证,动画演示',
    desc=f'本机真实用 -X importtime 记录 python -c pass 启动时最外层导入的 7 个模块(site 一项累计 {top[5][2]} µs);-S 让启动从 {t_def:.1f} ms 降到 {t_S:.1f} ms、模块数 54 → 21;实测用户 site-packages 的 .pth 里的 import 语句和 sitecustomize 会在主脚本之前执行,-I 与 -S 都能关掉它们。',
    lead='<code>python script.py</code> 按下回车到你的第一行代码执行之间,解释器做了什么?这篇不查资料——直接让 Python 自己汇报:用 <code>-X importtime</code> 看导入顺序,用 <code>-S</code>、<code>-I</code> 看开关的作用,再往 site-packages 里放一个 <code>.pth</code> 文件,亲眼看它在你的脚本之前执行。',
    facts=[(f'{top[5][2]} µs', 'site 模块在一次空启动里的累计耗时,最重的一项'), (f'54 → 21', '默认启动与 -S 启动之后 sys.modules 里的模块数'), ('.pth 先于脚本', '放在 site-packages 里的 .pth 中的 import 行,在主脚本之前被执行')],
    body=[
        sec('验证一:启动时导入了什么、按什么顺序', '<code>python -X importtime -c pass</code>', term('', block('== 一', '== 二')),
            f'<p>一次空启动记录了 45 行导入(含被别的模块触发的),其中最外层只有 7 个:先是 <code>_frozen_importlib_external</code>(让 <code>import</code> 自己能工作)和 <code>zipimport</code>,再是 <code>encodings</code>/<code>utf_8</code>(文本编码),<code>_signal</code>,然后是 <b><code>site</code>——它一项就占 {top[5][2]} µs</b>,是最大的开销,最后 <code>linecache</code>。这些都发生在你的脚本之前。</p>'),
        sec('验证二:开关的效果', '', term('', block('== 二', '== 三')),
            f'<p><code>-S</code> 让 site 不再导入:启动从 {t_def:.1f} ms 降到 {t_S:.1f} ms,启动后的 <code>sys.modules</code> 从 54 个降到 21 个。<code>-I</code>(隔离模式)几乎没有变快,模块数也没变——它并没有跳过 <code>site</code>,只是让 site 忽略环境变量和用户目录。<code>-E</code> 只忽略环境变量。想要「最小启动」需要 <code>-S</code>,想要「不受环境影响」用 <code>-I</code>,两者不是一回事。</p>'),
        sec('验证三:site 阶段会执行什么', '.pth 文件与 sitecustomize', term('', block('== 三', '== 四')),
            '<p>我在用户 site-packages 里放了一个 <code>demo.pth</code>:一行以 <code>import</code> 开头(会被当作代码执行),一行是路径(会被加进 <code>sys.path</code>);在 <code>PYTHONPATH</code> 指定的目录里放了 <code>sitecustomize.py</code>。运行结果显示,它们都在「主脚本开始执行」之前打印,路径也确实进了 <code>sys.path</code>。加 <code>-S</code> 或 <code>-I</code> 后两者都没有执行。</p>',
            callout('这是 Python 能在启动时自动加载东西的两个入口(许多工具靠它注入行为),也是排查「为什么我的脚本没运行就有奇怪行为」时该看的地方:<code>site-packages</code> 里的 <code>*.pth</code> 和 <code>sitecustomize</code>/<code>usercustomize</code>。')),
        sec('验证四:sys.argv 与 sys.orig_argv', '', term('', block('== 四', 'zzzz')),
            '<p><code>sys.orig_argv</code> 保留完整的原始命令行(包括给解释器的 <code>-I</code>、<code>-c</code>),<code>sys.argv</code> 只是交给脚本自己的那部分。<code>-I</code> 同时打开了 <code>isolated</code>、<code>no_user_site</code>、<code>ignore_environment</code> 三个标志。</p>'),
        sec('分步演示:从回车到第一行代码', '模块顺序与耗时来自 -X importtime 的实测输出',
            demo('Python 解释器启动的四个阶段', [('fl', 'flow', '启动阶段'), ('kv', 'kv', '观察'), ('b', 'bars', '最外层导入的累计耗时(µs)')], steps, '此刻的阶段 / 数据')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7(Homebrew),每种开关取 30 次中位数;<code>-X importtime</code> 的耗时随机器负载有波动,本次绝对值仅供参考',
          '没有验证:虚拟环境下 site 的处理差异、frozen modules 开关(<code>-X frozen_modules</code>)的影响、Windows 上的启动路径、编译成字节码缓存后的冷启动'],
)
