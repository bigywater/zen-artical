import json
from lib import *
txt = out('102').splitlines(); R = json.load(open('out/102.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
bl, rf, isr, ri = R['black'], R['ruff format'], R['isort --profile black'], R['ruff check --select I --fix']
ver = txt[0]
mess = ["import sys, os", "from typing import List,Dict, Optional", "import requests_not_installed", "from collections import (OrderedDict,", "    defaultdict, Counter, deque, namedtuple, ChainMap, UserDict)", "import json", "import re"]
isort_default = ["import json", "import os", "import re", "import sys", "from collections import (ChainMap, Counter, OrderedDict, UserDict, defaultdict,", "                         deque, namedtuple)", "from typing import Dict, List, Optional", "", "import requests_not_installed"]
black_style = ["from collections import (", "    ChainMap,", "    Counter,", "    OrderedDict,", "    UserDict,", "    defaultdict,", "    deque,", "    namedtuple,", ")"]
FL = lambda cur, done=(): {'nodes': [['import 排序', 'isort / ruff I'], ['代码格式', 'black / ruff format'], ['lint', 'ruff check'], ['组合', '谁在最后']], 'cur': cur, 'done': list(done)}
M = [['流水线', 'black --check', 'isort --check(默认)', 'isort --check(black profile)'],
     ['isort(默认) → black', '通过', '失败', '通过'], ['black → isort(默认)', '失败', '通过', '失败'], ['isort --profile black → black', '通过', '失败', '通过'], ['black → isort --profile black', '通过', '失败', '通过']]
steps = [
    step("原始代码:import 乱序、写法不统一,还有没用到的 import。三个不同的问题,通常由三类工具分别处理。", fl=FL([0, 1, 2]), t={'lines': mess, 'cur': []}),
    step("isort(或 ruff check --select I)只管 import 的顺序和分组:标准库在前、第三方在后,各组内字母序。它不会去动函数体里的代码。", fl=FL([0]), t={'lines': isort_default, 'cur': [0, 1, 2, 3], 'done': []}),
    step("black(或 ruff format)只管代码的排版:引号、空格、换行。对 import,它只重排版,不改顺序,也不会删除没用到的 import——删除是 ruff check 的 F401 的事。", fl=FL([1, 2]), t={'lines': ["import sys, os  → F401 `sys` imported but unused", "import requests_not_installed → F401 unused", "collections.OrderedDict → F401 unused", "……(共 10 个未使用的名字)", "black / isort 都不会删除它们"], 'cur': [0, 1, 2]}),
    step("冲突:isort 默认配置把长 import 排成「网格」风格(续行缩进对齐括号);而 black 的风格是「一行一个名字 + 尾逗号」。先跑 isort 再 black --check,black 说「我还想改」,返回码 1。", fl=FL([3]), t={'lines': isort_default[4:6] + ['', '↓ black 想改成 ↓'] + black_style, 'cur': [0, 1], 'mark': list(range(4, 13))}),
    step("解决:isort --profile black,让 isort 直接生成 black 风格的 import。此后 black --check 返回码 0,两者一致。", fl=FL([3], [0, 1]), t={'lines': black_style, 'done': list(range(9))}),
    step("四种流水线 × 三种检查的实测结果:黄色是失败的检查。isort 用默认配置时,不论先后,black 与 isort 两个检查总有一个失败;isort 用 black profile 时,两种顺序都能同时通过 black 检查和 isort(black profile)检查。", fl=FL([3]), m={'values': M, 'cur': [], 'mark': [[1, 2], [2, 1], [2, 3], [3, 2], [4, 2]], 'done': [[1, 1], [1, 3], [2, 2], [3, 1], [3, 3], [4, 1], [4, 3]]}),
    step("ruff 一个工具就能同时做「排序 import」和「格式化」。在这份样例上,ruff(I)+ruff format 的结果与 isort(black profile)+black 逐字符相同。", fl=FL([0, 1], [2]), t={'lines': ['isort(--profile black) + black  ==  ruff check --select I --fix + ruff format', '比较结果:完全相同 (True)'], 'cur': [1]}),
    step(f"速度(300 个文件、约 1 万行):black {bl*1000:.0f} ms、ruff format {rf*1000:.0f} ms(约 {bl/rf:.0f}x);isort {isr*1000:.0f} ms、ruff 排序 import {ri*1000:.0f} ms(约 {isr/ri:.0f}x)。", fl=FL([3]), b={'items': [['black', bl * 1000, f'{bl*1000:.0f} ms'], ['ruff format', rf * 1000, f'{rf*1000:.0f} ms'], ['isort', isr * 1000, f'{isr*1000:.0f} ms'], ['ruff -I', ri * 1000, f'{ri*1000:.0f} ms']], 'max': bl * 1000, 'cur': [0, 1, 2, 3]}),
]
A = dict(
    n=102,
    tags='Python,工程化,ruff,black,isort,真实验证,动画演示',
    desc=f'本机真实对同一段乱序代码跑 black、isort、ruff:格式化与 import 排序是两件事,三者都不会删除未使用的 import(ruff 的 F401 才会报);isort 默认配置生成的网格式 import 会被 black --check 判失败,加 --profile black 后一致;ruff(I)+ruff format 与 isort+black 输出逐字相同;300 文件下 black {bl*1000:.0f} ms 对 ruff format {rf*1000:.0f} ms、isort {isr*1000:.0f} ms 对 ruff {ri*1000:.0f} ms。',
    lead='Python 项目里常见一串:isort 排 import、black 排版、flake8/ruff 查问题。它们各管什么、放在一起会不会打架、ruff 能不能一个顶三个,这篇用同一段乱代码全部真跑了一遍,包括那个著名的「isort 与 black 互相不认」冲突。',
    facts=[('1 → 0', 'isort 默认配置 → black --check 返回码;加 --profile black 后从 1 变 0'), ('结果逐字相同', 'ruff(I)+ruff format 与 isort(black profile)+black 的输出'), (f'{bl/rf:.0f}x / {isr/ri:.0f}x', '本机 300 个文件上 ruff 相对 black / isort 的速度倍数')],
    body=[
        sec('做的事:一段故意写乱的代码', '', src('messy.py(节选)', '\n'.join(mess) + '\n\ndef build(items:List[int],  mapping: Dict[str,int]={}, flag = True)->Optional[str]:\n    result = {\'a\':1,\'b\':2,\n        \'c\':3}\n    ...'),
            term('版本', ver)),
        sec('验证一:各工具只做自己的事', '', term('', block('== 一', '== 二')),
            '<p>black 与 ruff format 的改动几乎相同(31 行,其中动到 import 的只有 4 行——只是排版);isort 与 ruff 的 I 规则只动 import(isort 改 11 行 import,代码本体不动)。<b>没有一个会删除没用到的 import</b>:<code>sys</code>、<code>os</code>、<code>requests_not_installed</code> 等全都还在,想找出它们要靠 lint(ruff 的 <code>F401</code>,上面列出了前几条,可以加 <code>--fix</code> 自动删)。</p>'),
        sec('验证二:isort 默认配置与 black 的冲突', '', term('', block('== 二', '== 三')),
            '<p>isort 默认把过长的 import 排成「网格」风格:续行缩进到括号位置;black 的风格是「一行一个名字 + 尾逗号」。所以先用默认配置的 isort,black 再检查一定说「还没格式化」。<code>--profile black</code> 让 isort 直接输出 black 风格,冲突消失(返回码 0)。</p>'),
        sec('验证三:先后顺序与检查结果', '', term('', block('== 三', '== 四')),
            '<p>四种流水线的最终状态:①isort 用默认配置时,<b>无论先后,总有一个检查会失败</b>:isort 在前则 isort --check 用默认配置时失败,isort 在后则 black --check 失败;②isort 用 <code>--profile black</code>,先后都能让 black 和 isort(black profile)两个检查通过。注意这里只是同一份样例的结果,配置项更多的项目里可能有别的冲突。</p>'),
        sec('验证四:ruff 一个工具能顶两个吗', '', term('', block('== 四', '== 五')),
            '<p>在这份样例上,<code>ruff check --select I --fix</code> 加 <code>ruff format</code> 的结果和 <code>isort --profile black</code> 加 <code>black</code> 的输出完全相同(比较结果 True,最终代码见上)。这只说明这份样例上一致,<b>不是</b>所有代码都一致——两者的实现是独立的,遇到边缘情况(比如特殊注释、超长字符串)可能有差异,这里没有验证。</p>'),
        sec('验证五:速度', '', term('', block('== 五', 'zzzz')),
            f'<p>300 个文件(共 10200 行):black 要 {bl*1000:.0f} ms,ruff format {rf*1000:.0f} ms;isort {isr*1000:.0f} ms,ruff 的 import 排序 {ri*1000:.0f} ms。差距在 CI 或者保存文件自动格式化时最容易感觉到。速度不是选工具的唯一理由,但配置只需要维护一份是实打实的好处。</p>'),
        sec('分步演示:三类工作、一个冲突、一个替代', '所有输出取自上面的真实运行',
            demo('isort / black / ruff 如何协作', [('fl', 'flow', '哪一类工作'), ('t', 'term', '代码'), ('m', 'matrix', '流水线 × 检查'), ('b', 'bars', '耗时(ms)')], steps, '当前关注的代码 / 数据')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7;black 26.5.1、isort 9.0.2、ruff 0.16.9(临时虚拟环境);速度取 3 次最小值,每次从原始文件重新拷贝',
          '没有验证:项目配置文件(pyproject.toml 里的 [tool.*])的合并规则、ruff 的其他规则集(E、W、B 等)、pre-commit 集成、ruff 与 black 在更多语法(match、类型参数)上的输出差异'],
)
