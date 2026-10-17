import json
from lib import *
txt = out('100').splitlines(); J = json.load(open('out/100.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
hot, many = J['hot'], J['many']
srcl = ["1  def price_with_discount(price, qty, is_member):", "2      total = price * qty", "3      if qty >= 10:", "4          total = total * 0.9", "5      if is_member:", "6          total = total - 5", "7      return total"]
FL = lambda cur, done=(): {'nodes': [['行覆盖', '每行执行过吗'], ['分支覆盖', '每个 if 的两边'], ['断言', '结果对不对'], ['统计范围', '哪些文件算数']], 'cur': cur, 'done': list(done)}
steps = [
    step("被测函数 7 行,有两个 if。会员再减 5 元没有下限——price=1、qty=1 的会员订单结果会是 -4。", fl=FL([0]), src={'lines': srcl, 'cur': []}, kv={'items': [['price_with_discount(1, 1, True)', '-4(bug)']], 'hl': ['price_with_discount(1, 1, True)']}),
    step("测试只调用一次 price_with_discount(100, 10, True),什么也不断言。每一行都被执行过 → 行覆盖 100%。", fl=FL([0]), src={'lines': srcl, 'done': list(range(7))}, kv={'items': [['行覆盖', '7 / 7 = 100%'], ['测试结果', 'passed(没有断言,不可能失败)']], 'hl': ['行覆盖']}),
    step("打开分支覆盖:两个 if 都只走了「进入」的一侧——3→5(qty<10 时跳过打折)和 5→7(非会员时跳过减 5)从未发生。同一批测试,数字变成 82%。", fl=FL([1], [0]), src={'lines': srcl, 'done': [0, 1, 3, 5, 6], 'mark': [2, 4]}, kv={'items': [['未走过的分支', '3->5, 5->7'], ['行 + 分支覆盖', '82%']], 'hl': ['未走过的分支']}),
    step("再加几个只调用的测试补上这两个方向:分支也 100% 了。但断言依然一条没有——覆盖率只说明代码被执行过,不说明被验证过。", fl=FL([1], [0]), src={'lines': srcl, 'done': list(range(7))}, kv={'items': [['行覆盖', '100%'], ['分支覆盖', '100%'], ['发现 bug?', '没有']], 'hl': ['发现 bug?']}),
    step("一条真正断言业务规则的测试 assert price_with_discount(1, 1, True) >= 0:失败,bug 被发现。有意思的是它自己的覆盖率反而只有 73%(只走了一条路径)。", fl=FL([2], [0, 1]), src={'lines': srcl, 'cur': [4, 5]}, kv={'items': [['这条测试的结果', '1 failed'], ['这条测试的覆盖率', '73%']], 'hl': ['这条测试的结果']}),
    step("统计范围:默认只统计「被导入过」的文件。untested.py 里 4 行代码从没被任何测试导入,报告里根本没有它——总覆盖率显示 100%。加上 --source=.,它以 0% 出现,总覆盖率变成 73%。", fl=FL([3], [0, 1, 2]), b={'items': [['默认报告', 100, '100%'], ['--source=.', 73, '73%']], 'max': 100, 'cur': [1]}),
    step("# pragma: no cover 会把代码从统计里拿掉:被标记的 else 分支根本没执行过,报告仍是 100%,分支数也从 2 变成 0。", fl=FL([3]), kv={'items': [['shop2.py(else 上加了 pragma)', '3 语句 / 0 未执行 / 0 分支 → 100%']], 'hl': ['shop2.py(else 上加了 pragma)']}),
]
A = dict(
    n=100,
    tags='Python,测试,coverage,真实验证,动画演示',
    desc=f'本机 coverage 7.16.2 真实验证覆盖率的含义:一个只调用不断言的测试行覆盖 100%、行+分支覆盖 82%,却完全发现不了「会员订单价格变负」的 bug;补齐分支后仍是 100% 却仍无断言;没被 import 的文件默认不进报告(100% → 加 --source=. 后 73%);# pragma: no cover 直接改变数字;3 万行不同代码各跑一次时开销 {many[1]/many[0]:.0f}x(行)/{many[2]/many[0]:.0f}x(分支),反复跑的热循环几乎无开销。',
    lead='「覆盖率 90%」是一个很容易被误读的数字。它到底测的是什么、什么情况下会骗你?这篇用一个 7 行的函数和 5 组对照实验,把覆盖率<b>能证明</b>和<b>不能证明</b>的事分开。',
    facts=[('100% vs 82%', '同一个只调用不断言的测试:行覆盖与行+分支覆盖的读数'), ('-4', '被「100% 覆盖」的函数里,一直没人发现的 bug 的结果'), ('100% → 73%', '把没被导入的文件也算进来(--source=.)后的总覆盖率')],
    body=[
        sec('做的事:一个函数,几种测试', '',
            src('shop.py', '''def price_with_discount(price, qty, is_member):
    total = price * qty
    if qty >= 10:
        total = total * 0.9
    if is_member:
        total = total - 5        # 没有下限!
    return total'''),
            src('test_shop_noassert.py', '''def test_runs():
    price_with_discount(100, 10, True)      # 只是调用, 什么也不断言'''),
            term('coverage 版本', txt[0])),
        sec('验证一:行覆盖 100%,分支覆盖 82%', '同一个测试的两种读数', term('', block('== 一', '== 二')),
            '<p>这个测试只调用了一次,但每一行都执行到了:行覆盖 <b>100%</b>。打开 <code>--branch</code> 之后同一批测试变成 <b>82%</b>,<code>Missing</code> 列指出 <code>3->5</code> 和 <code>5->7</code> 两个分支从未发生——也就是「数量不到 10」和「不是会员」这两种情况从没被走过。行覆盖看不到「if 条件为假」这条路,分支覆盖能。</p>'),
        sec('验证二:覆盖率高,不等于测过', '', term('', block('== 二', '== 三')),
            '<p>函数里的 bug 是会员减 5 元没有下限,一个 1 元订单会变成 -4 元。那个「100% 行覆盖」的测试通过了——它没有断言,也不可能失败。换成一条断言业务规则的测试(价格不能为负),立刻失败,bug 被发现;而这条测试自己的覆盖率只有 73%,比前一个低。<b>覆盖率衡量代码是否被执行,不衡量结果是否被检查。</b>用它找「没测到的地方」是有效的(读数低说明肯定没测),用它证明「测好了」是无效的。</p>'),
        sec('验证三:没被 import 的文件,默认不在报告里', '', term('', block('== 三', '== 四')),
            '<p>默认报告只统计「测试运行期间被导入过」的文件。<code>untested.py</code> 里 4 行代码没有任何测试碰过,但它根本不在报告里,总覆盖率看起来是 100%。加上 <code>--source=.</code> 让 coverage 主动去找目录里的所有文件,它才以 0% 出现,总覆盖率掉到 73%。所以 CI 里的覆盖率门槛,要配上 <code>source</code>,否则漏测的文件会「隐形」。</p>'),
        sec('验证四:# pragma: no cover', '', term('', block('== 四', '== 五')),
            '<p>在 <code>else:</code> 那一行加上 <code># pragma: no cover</code>,那个分支就从统计里整个消失(分支数是 0),即使它从来没被执行过,报告依然是 100%。用它排除「防御性代码」是常见做法,但滥用就会让数字失真——review 时值得留意。</p>'),
        sec('验证五:开销', '', term('', block('== 五', 'zzzz')),
            f'<p>同一批代码反复执行(200 万次循环)时,覆盖率几乎没有额外开销({hot[1]/hot[0]:.2f}x)——(我的推测是已经记录过的行不必再被追踪,这一点没有验证)。相反,3 万行不同的代码各执行一次时,行覆盖是 {many[1]/many[0]:.0f}x、行+分支覆盖是 {many[2]/many[0]:.0f}x(基线只有 {many[0]:.1f} ms,绝对值是 {many[1]:.1f} 与 {many[2]:.1f} ms):开销正比于「第一次见到多少不同的行」,而不是执行了多少次。所以覆盖率对「大量各不相同的代码、每样跑一次」的测试(例如大量小测试)拖累最明显。</p>'),
        sec('分步演示:同一个函数,覆盖率一步步「说」了什么', '所有数字取自上面的真实输出',
            demo('覆盖率的含义与边界', [('fl', 'flow', '看哪一个维度'), ('src', 'term', '被测代码(绿 = 执行过,黄 = 分支未走完)'), ('kv', 'kv', '读数'), ('b', 'bars', '总覆盖率')], steps, '当前观察')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,coverage 7.16.2(C 扩展)、pytest 9.1.1;每项开销取 7 次最小值',
          '没有验证:HTML/XML 报告、<code>fail_under</code> 门槛、多进程 / subprocess 覆盖(需要额外配置)、sys.monitoring 与旧追踪器(sys.settrace)在开销上的差别'],
)
