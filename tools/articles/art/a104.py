import json
from lib import *
txt = out('104').splitlines(); R = json.load(open('out/104.json')); alld = R['all1']; s1, s2, names2 = R['s1'], R['s2'], R['names2']; t1, t2 = R['t']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
order = list(alld.keys()); short = lambda n: n.replace('calc.x_', '').replace('__mutmut_', '#')
FL = lambda cur, done=(): {'nodes': [['测试 + 覆盖率', '100%'], ['生成变异体', '每次改一处'], ['重新跑测试', '逐个'], ['存活 = 漏洞', ''], ['补断言再跑', '']], 'cur': cur, 'done': list(done)}
steps = [step("三个测试,覆盖率 100%(行和分支都是)。但 test_clamp_runs 只调用不断言,test_adult 只测了 30,test_total 只测了 tax=0。看起来很完整。", fl=FL([0]),
              ch={'values': [[short(n), '待测'] for n in order]}, d={'lines': ['覆盖率: src/calc.py 13 行 / 6 分支 → 100%'], 'cur': [0]})]
def chips(k, status_of):
    vals = []; mark = []; done = []
    for i, n in enumerate(order):
        st = status_of(i, n)
        vals.append([short(n), st])
        if st == '存活': mark.append(i)
        elif st == '杀死': done.append(i)
    return vals, mark, done
for k, n in enumerate(order):
    st, ls = alld[n]
    def so(i, nn, k=k): return ('杀死' if alld[nn][0] == 'killed' else '存活') if i <= k else '待测'
    vals, mark, done = chips(k, so)
    steps.append(step(f"变异体 {short(n)}:{ls[0].strip()[1:].strip()} → {ls[1].strip()[1:].strip()}。测试{'失败了(变异被发现:杀死)' if st == 'killed' else '仍然全部通过(测试没发现这个改动:存活)'}。", fl=FL([2]), ch={'values': vals, 'cur': [k], 'mark': [i for i in mark if i != k], 'done': [i for i in done if i != k]}, d={'lines': [ls[0], ls[1]], 'cur': [1]}))
vals, mark, done = chips(0, lambda i, n: '杀死' if alld[n][0] == 'killed' else '存活')
steps.append(step(f"结果:{s1['total']} 个变异体,{s1['killed']} 个被杀死、{s1['survived']} 个存活。存活的 6 个正好落在测试薄弱的地方:没断言的 clamp、只测了 30 的 is_adult、只测 tax=0 的 total。覆盖率 100% 却有 6 处改动无人察觉。", fl=FL([3], [0, 1, 2]), ch={'values': vals, 'mark': mark, 'done': done}, d={'lines': ['杀死 5 / 存活 6 / 共 11'], 'cur': [0]}))
alive2 = set(names2)
vals2 = [[short(n), '存活' if n in alive2 else '杀死'] for n in order]
steps.append(step(f"给每个函数补上边界值和有意义的断言(clamp 的等于上下限、is_adult 的 17/18、total 的 tax=0.5 与空列表),再跑一遍:{s2['killed']} 个杀死,只剩 {s2['survived']} 个存活。", fl=FL([4], [0, 1, 2, 3]), ch={'values': vals2, 'mark': [i for i, n in enumerate(order) if n in alive2], 'done': [i for i, n in enumerate(order) if n not in alive2]}, d={'lines': ['杀死 9 / 存活 2 / 共 11'], 'cur': [0]}))
steps.append(step("剩下的两个是「等价变异体」:if x <= lo: return lo。当 x == lo 时,返回 lo 和原来返回 x 的结果完全一样;if x >= hi 同理。改动没有改变任何可观察的行为,不可能被任何测试杀死——这是变异测试里必须人工判断的部分。", fl=FL([4], [0, 1, 2, 3]), ch={'values': vals2, 'cur': [i for i, n in enumerate(order) if n in alive2]}, d={'lines': ['if x < lo:   return lo   (x == lo 时返回 lo,即 x)', 'if x <= lo:  return lo   (x == lo 时返回 lo,即 x) ← 结果相同'], 'cur': [1]}))

A = dict(
    n=104,
    tags='Python,测试,变异测试,mutmut,真实验证,动画演示',
    desc=f'本机 mutmut 3.8.0 真实对一个 13 行、覆盖率 100% 的小模块做变异测试:11 个变异体里 5 个被杀死、6 个存活(clamp 无断言、is_adult 只测 30、total 只测 tax=0);补上边界断言后 9 个杀死、2 个存活,那 2 个是无法被杀死的等价变异体(x <= lo 与 x < lo 在 x==lo 时返回值相同)。',
    lead='覆盖率告诉你代码被执行过,不告诉你测试会不会发现错误。变异测试反过来:故意把代码改坏一点点(把 <code>&gt;=</code> 改成 <code>&gt;</code>、<code>+</code> 改成 <code>-</code>),看你的测试会不会「报警」。一处改动测试没发现,就说明这处代码的测试是形同虚设。这篇用 mutmut 在一个覆盖率 100% 的小模块上真的做一遍。',
    facts=[('100% → 5/11', '覆盖率 100%,但 11 个变异体里只有 5 个被测试发现'), ('6 个存活', 'clamp 边界、is_adult 边界、total 的运算符和 tax 项'), ('2 个等价变异体', '补全测试后仍无法杀死:改动没有改变任何可观察行为')],
    body=[
        sec('做的事:一个「覆盖率 100%」的小模块', '', src('src/calc.py', '''def clamp(x, lo, hi):
    if x < lo: return lo
    if x > hi: return hi
    return x

def is_adult(age): return age >= 18

def total(prices, tax):
    s = 0
    for p in prices: s += p
    return s * (1 + tax)'''), src('test_calc.py(初版)', '''def test_clamp_runs():
    clamp(5, 0, 10); clamp(-1, 0, 10); clamp(99, 0, 10)   # 只调用, 不断言
def test_adult():  assert is_adult(30)
def test_total():  assert total([1, 2], 0) == 3'''),
            term('', txt[0] + '\n' + block('== 一', '== 二')),
            '<p>3 个测试全部通过,行覆盖与分支覆盖都是 100%——第 100 篇里讲过,这个数字只说明代码被执行了。</p>'),
        sec('验证一:变异测试怎么做', '', term('', block('== 二', '== 三')),
            '<p><code>mutmut run</code> 把源码里的比较、算术、常量等各改动一处,生成一个变异体,然后对每个变异体重新跑测试套件:测试失败,变异体被<b>杀死</b>(测试能发现这个错误);测试仍然全部通过,变异体<b>存活</b>(测试对这处改动毫无察觉)。11 个变异体里,5 个被杀死、6 个存活。</p>'),
        sec('验证二:存活的变异体具体是什么', '', term('', block('== 三', '== 四')),
            '<p>每个存活变异体都精确对应一个测试盲点:<code>x &lt; lo</code> 改成 <code>x &lt;= lo</code> 没人发现——因为测试从没有让 <code>x</code> 恰好等于下限;<code>age &gt;= 18</code> 改成 <code>&gt; 18</code> 或 <code>&gt;= 19</code> 没人发现——只测了 30;<code>s * (1 + tax)</code> 改成 <code>s / (1 + tax)</code> 或 <code>s * (1 - tax)</code> 没人发现——只测了 tax=0,乘除、加减在 0 时结果一样。它们全在「覆盖率 100%」的代码里。</p>'),
        sec('验证三:补上边界与有意义的断言之后', '', term('', block('== 四', 'zzzz')),
            f'<p>补上 clamp 的等于上下限、is_adult 的 17 与 18、total 的 <code>tax=0.5</code> 和空列表,再跑:{s2["total"]} 个变异体里杀死 {s2["killed"]} 个。剩下 2 个是<b>等价变异体</b>:<code>if x &lt;= lo: return lo</code>——当 <code>x == lo</code> 时它返回 <code>lo</code>,而原来的代码(不进这个 if)返回 <code>x</code>,两者相等,行为完全一样,没有任何测试能区分。变异测试因此不能追求「存活为 0」,要人工审视每个存活的变异体:是测试的漏洞,还是等价的?</p>'
            f'<p>另外这个小例子上,一次完整的变异测试只花了 {t1:.1f} s——因为只有 11 个变异体。变异体数量大致随代码量线性增长,每个都要跑一遍测试套件,大项目上会慢得多,所以通常只对关键模块或变更的部分运行。这个耗时我没有在大项目上验证。</p>'),
        sec('分步演示:11 次「故意改坏」,测试发现了几次', '状态取自 mutmut 的真实结果',
            demo('变异测试', [('fl', 'flow', '阶段'), ('ch', 'chips', '变异体(小字为状态)'), ('d', 'term', '改动')], steps, '当前变异体')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,mutmut 3.8.0、pytest 9.1.1、coverage 7.16.2;变异体由 mutmut 生成,不是我手写',
          '没有验证:mutmut 之外的工具(cosmic-ray、mutatest)、大型项目上的耗时与变异体数量、如何自动识别等价变异体'],
)
