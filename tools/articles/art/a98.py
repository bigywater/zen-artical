import json, re
from lib import *
txt = out('98').splitlines(); J = json.load(open('out/98.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
tp, tl = J['tp'], J['tl']
one = block('== 一', '== 二').splitlines()
cases = [l for l in one if l.startswith('test_slug.py::')]
FL = lambda cur, done=(): {'nodes': [['参数列表', '10 组'], ['收集阶段', '生成 10 个用例'], ['运行', '各自独立'], ['结果', '精确到某一组']], 'cur': cur, 'done': list(done)}
steps = [step("一个 test_slugify 函数 + 10 组 (raw, expected) 参数。在 pytest 眼里,这不是 1 个测试,而是 10 个。", fl=FL([0]), t={'lines': ['@pytest.mark.parametrize("raw, expected", [ ...10 组... ])', 'def test_slugify(raw, expected): assert slugify(raw) == expected'], 'cur': [0]})]
lines = []
for i, l in enumerate(cases):
    name = re.sub(r'\s+\S+\s+\[.*$', '', l).replace('test_slug.py::', ''); st = 'FAILED' if 'FAILED' in l else 'PASSED'
    lines.append(f"{name:<50} {st}")
    steps.append(step(f"第 {i+1} 个用例 {name}:{'失败——只有这一组挂了,它的 id 直接出现在报告里' if st=='FAILED' else '通过'}。" , fl=FL([2], [0, 1]), t={'lines': list(lines), 'cur': [len(lines) - 1]}))
steps.append(step("汇总:2 failed, 8 passed。两个失败的用例都被报告了,其余照常通过。对照:把 10 组写进一个 for 循环,第 2 组失败后循环就中断,后面的用例(包括第二个失败)根本没被检查。", fl=FL([3], [0, 1, 2]), t={'lines': list(lines) + ['', '合计: 2 failed, 8 passed'], 'cur': []}))
A = dict(
    n=98,
    tags='Python,测试,pytest,真实验证,动画演示',
    desc=f'本机 pytest 9.1.1 真实验证 @pytest.mark.parametrize:10 组参数生成 10 个独立用例,2 个失败都被精确报告(for 循环写法只报第一个);默认 id 对非基本类型退化为 x4、x5;叠加两个 parametrize 得到 3×4=12 的笛卡尔积;共享的可变参数在用例间是同一个对象;3000 个参数化用例总耗时 {tp:.2f} s、单个用例循环 {tl:.2f} s。',
    lead='把同一个断言换十组输入,最省事的写法是 for 循环;pytest 的写法是 <code>parametrize</code>。它们在失败时的表现、用例的命名、组合的方式上差别很大。这篇拿一个 <code>slugify</code> 函数,一项一项验证。',
    facts=[('10 组 → 10 个用例', '每组参数一个独立用例,各自通过或失败'), ('2 vs 1', 'parametrize 报告了 2 个失败,for 循环只暴露第一个'), ('3 × 4 = 12', '叠加两个 parametrize 得到笛卡尔积')],
    body=[
        sec('验证一:一组参数一个用例', '', src('test_slug.py(节选)', '''@pytest.mark.parametrize("raw, expected", [
    ("Hello World", "hello-world"),
    ("Café Crème", "cafe-creme"),   # 期望「去重音」,但 slugify 没做
    ("Ünï", "uni"),
    ("2026年9月", "2026-9"),
    ...])
def test_slugify(raw, expected):
    assert slugify(raw) == expected'''), term('pytest test_slug.py -v --tb=line -rf', block('== 一', '== 二')),
            '<p>10 组参数变成 10 个用例,每个 id 由参数值拼出来。有两组失败,它们的名字直接出现在报告里,失败差异也逐个给出(<code>\'caf-cr-me\' == \'cafe-creme\'</code>、<code>\'n\' == \'uni\'</code>)——你一眼就知道是哪个输入出了问题。注意:id 里的非 ASCII 字符被转义成了 <code>\\xe9</code> 这样的形式,想要好读的名字就要自己指定(见验证三)。</p>'),
        sec('验证二:for 循环写法会遮住后面的失败', '', term('pytest test_loop.py -v --tb=line', block('== 二', '== 三')),
            '<p>把同样的数据放进一个 for 循环,整个测试只算 1 个用例;第二组失败时循环就中断,剩下的组(包括另一个会失败的 <code>Ünï</code>)从来没有被检查,报告里也只有一个失败。修完一个再跑,才会撞上下一个。</p>'),
        sec('验证三:用例 id', '默认规则与自定义', term('', block('== 三', '== 四')),
            '<p>基本类型(int、str、None、float、bytes)直接用值做 id;元组、列表、字典、<code>object()</code> 这类没法生成可读 id 的,退化成「参数名 + 序号」:<code>x4</code>、<code>x5</code>、<code>x6</code>、<code>x7</code>;长字符串的 id 也会完整保留(并转义非 ASCII)。想要好读的名字,用 <code>pytest.param(..., id="small")</code>——同一个地方还能给单个用例打 <code>skip</code>、<code>xfail</code> 标记,上面运行结果里 <code>zero</code> 被跳过、<code>known-bug</code> 是 XFAIL,不影响其他两个通过。</p>'),
        sec('验证四:叠加 parametrize 是笛卡尔积', '', term('', block('== 四', '== 五')),
            '<p>两个 <code>parametrize</code> 叠在同一个函数上:3 个浏览器 × 4 个系统 = 12 个用例。id 是各参数的 id 拼接(注意顺序:下面那个装饰器的参数在前)。可以用完整 id 直接指定单个用例,也可以用 <code>-k "firefox and not win"</code> 按表达式筛选(这里选出 3 个)。</p>'),
        sec('验证五:可变参数在用例间共享', '', term('', block('== 五', '== 六')),
            '<p>三个用例传的是同一个列表对象 <code>SHARED</code>。第一个用例往里 <code>append(1)</code> 后长度是 1,通过;第二个用例拿到的还是这个列表,长度变成 2,失败;第三个变成 3。<code>parametrize</code> 只在收集阶段把参数对象存起来,并不会给每个用例复制一份——参数里放了可变对象,就要自己保证用例不会修改它(或者在用例里先拷贝)。</p>'),
        sec('验证六:开销', '', term('', block('== 六', 'zzzz')),
            f'<p>3000 个 <code>n * 2 == n + n</code> 的断言:参数化成 3000 个用例总耗时 {tp:.2f} s(pytest 自己报告的运行时间 0.83 s,其余是收集和进程启动);放进一个用例的循环里总共 {tl:.2f} s(运行 0.13 s)。每个用例都有固定的调度成本,大约每个 0.2 ms,所以「几十组」参数几乎没有感知,但「几万组」就要考虑是不是把它们放进循环。用例是否值得独立,取决于你想要失败定位的精度还是运行速度。</p>'),
        sec('分步演示:10 个用例逐个运行', '每一行都是 pytest -v 的真实输出',
            demo('parametrize 生成的用例', [('fl', 'flow', '阶段'), ('t', 'term', '用例与结果')], steps, '当前用例')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,pytest 9.1.1(装在临时虚拟环境,<code>-p no:cacheprovider</code>)',
          '没有验证:参数化 fixture(<code>params=</code>)与间接参数化(<code>indirect=True</code>)、pytest-xdist 并行时的分配、用例数量达到几十万时的收集内存'],
)
