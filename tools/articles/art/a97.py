import json
from lib import *
txt = out('97').splitlines()
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
# 发现顺序(与真实输出一致): 名字排序后依次处理
walk = [
    ('tests/check_util.py', '文件名不匹配 test*.py → 不导入(里面的 print 也没执行)', 0, 'skip'),
    ('tests/nopkg/', '子目录没有 __init__.py → 整个目录被忽略,里面的 test_deep.py 从未被导入', 0, 'skip'),
    ('tests/pkg/', '有 __init__.py 的子目录 → 当作包进入', 0, 'enter'),
    ('tests/pkg/test_inner.py', '匹配 → 导入 → 找到 1 个用例(TestInner.test_inner)', 1, 'ok'),
    ('tests/strings_test.py', '文件名是 *_test.py,不匹配默认的 test*.py → 忽略', 0, 'skip'),
    ('tests/test_broken.py', '匹配,但导入时 ModuleNotFoundError → 变成一个名叫 _FailedTest 的「用例」,报 ERROR,发现继续', 1, 'fail'),
    ('tests/test_math.py', '匹配 → 导入 → TestAdd 里 3 个 test_ 方法被收集;helper_check、check_things 与 NotATestCase.test_ignored 都没有被收集', 3, 'ok'),
    ('tests/test_strings.py', '匹配 → 导入 → 3 个用例(其中一个 skip、一个 expectedFailure 也算在内)', 3, 'ok'),
]
lines = []; total = 0; steps = []
for i, (f, note, n, kind) in enumerate(walk):
    total += n
    mark = {'skip': '✗ 忽略', 'enter': '→ 进入', 'ok': f'✓ {n} 个用例', 'fail': '✗ 导入失败(ERROR)'}[kind]
    lines.append(f"{f:<28} {mark}")
    steps.append(step(f"{f}:{note}", w={'lines': list(lines), 'cur': [i]}, kv={'items': [['累计找到的用例', str(total)], ['被导入的文件', str(sum(1 for x in walk[:i+1] if x[3] in ('ok', 'fail')))]], 'hl': ['累计找到的用例']}))
steps.append(step("发现结束:总共 8 个用例(含 1 个 _FailedTest、1 个 skip、1 个 expectedFailure)。运行结果:Ran 8 tests … FAILED (errors=1, skipped=1, expected failures=1)。", w={'lines': list(lines), 'cur': []}, kv={'items': [['Ran', '8 tests'], ['FAILED', 'errors=1, skipped=1, expected failures=1']], 'hl': ['FAILED']}))
A = dict(
    n=97,
    tags='Python,测试,unittest,真实验证,动画演示',
    desc='本机造一棵测试目录树,真实验证 unittest discover 的规则:只导入文件名匹配 test*.py 的模块(strings_test.py、check_util.py 被忽略);没有 __init__.py 的子目录整个被跳过而且没有任何提示;导入失败的测试文件变成 _FailedTest 报 ERROR 而发现继续;只收集继承 TestCase 且以 test 开头的方法,同一个类里按方法名字母序执行;-k 过滤时导入失败仍会被报告。',
    lead='<code>python -m unittest</code> 没告诉你要跑哪个文件,它是怎么找到的?哪些会被悄悄漏掉?这篇造了一个「故意有干扰项」的测试目录——名字不对的文件、缺 <code>__init__.py</code> 的目录、导入就会报错的文件、不继承 TestCase 的类——然后让 unittest 真的去发现一遍。',
    facts=[('8 个用例', '这棵树里被发现并运行的用例数(另有几个写好的用例因为文件名或目录问题没被发现)'), ('无 __init__.py', '子目录被整个跳过,且没有任何警告'), ('_FailedTest', '导入失败的测试文件变成一个 ERROR 用例,不会中断发现')],
    body=[
        sec('做的事:一棵有干扰项的测试树', '', term('', block('== 一', '== 二')),
            '<p>其中 <code>tests/strings_test.py</code>、<code>tests/check_util.py</code> 文件名不合规;<code>tests/nopkg/</code> 没有 <code>__init__.py</code>;<code>tests/test_broken.py</code> 会在 import 时失败;<code>test_math.py</code> 里有不以 <code>test</code> 开头的方法和一个没有继承 <code>TestCase</code> 的类。</p>'),
        sec('验证一:discover 实际跑了什么', '', term('python -m unittest discover -s tests -t . -v', block('== 二', '== 三').replace('\n\n', '\n')),
            '<ul><li><b>打印出来的 <code>[import]</code> 只有三行</b>:<code>test_inner</code>、<code>test_math</code>、<code>test_strings</code>。<code>strings_test.py</code>、<code>check_util.py</code> 的导入行没有出现——它们根本没被导入;<code>nopkg/test_deep.py</code> 也没有——整个目录被跳过,而且没有任何提示。</li>'
            '<li><b>discover 会导入每个匹配的文件</b>,所以模块顶层的副作用(打印、连接数据库)在收集阶段就已经发生,不管用例最终跑不跑。</li>'
            '<li><b>导入失败不会中断</b>:<code>test_broken.py</code> 变成了名叫 <code>unittest.loader._FailedTest.tests.test_broken</code> 的 ERROR 用例,其余照常运行。</li>'
            '<li>skip 和 expectedFailure 都计入「Ran 8 tests」,结果行里单独计数。</li></ul>'),
        sec('验证二:用 TestLoader 看发现的过程', '', term('', block('== 三', '== 四')),
            '<p>自己写一个 <code>TestLoader</code> 子类记录 <code>loadTestsFromModule</code> 的调用,就能看到:每个被导入的模块都调用一次,包括 <code>tests</code>、<code>tests.pkg</code> 这两个包(0 个用例);<code>test_math</code> 3 个用例——只有 <code>TestAdd</code> 里以 <code>test</code> 开头的三个方法被收集,<code>helper_check</code>、<code>check_things</code> 和不继承 <code>TestCase</code> 的 <code>NotATestCase.test_ignored</code> 都没进来。也就是说 <b>unittest 只认「TestCase 子类 + test 开头的方法」</b>,不看类名叫不叫 Test。</p>'),
        sec('验证三:执行顺序', '', term('', block('== 四', '== 五')),
            '<p>源码里方法的写法顺序是 b、a、c,运行顺序却是 a、b、c:同一个类里的用例按方法名的字母序排序。所以不要依赖「写在前面的先执行」;需要固定顺序就在名字里编号,或者(更好)让用例彼此独立。</p>'),
        sec('验证四:-k 过滤与不带参数', '', term('', block('== 五', 'zzzz')),
            '<p><code>-k upper</code> 只选出名字里含 <code>upper</code> 的用例,<b>但导入失败的那个 ERROR 依然被报告</b>(它没有被过滤),所以最后是 <code>FAILED (errors=1)</code>。不带任何参数的 <code>python -m unittest</code> 等价于 <code>discover</code>,从当前目录开始找,同样跑出 8 个。</p>'),
        sec('分步演示:discover 逐项处理这棵目录树', '每一项的结论都是上面真实运行的结果',
            demo('unittest 如何发现测试', [('w', 'term', '目录树与处理结果'), ('kv', 'kv', '累计')], steps, '当前处理的文件')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>unittest</code>(<code>discover</code> 默认规则)',
          '没有验证:<code>load_tests</code> 协议、<code>setUpModule</code>/<code>setUpClass</code> 的调用时机、与 pytest 收集规则的差异(见下一篇)、旧版本对命名空间包的支持'],
)
