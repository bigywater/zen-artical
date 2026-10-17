import json
from lib import *
txt = out('99').splitlines(); J = json.load(open('out/99.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
seen, uniq, calls, fails = J['seen'], J['uniq'], J['calls'], J['fails']
def disp(s):
    r = repr(s)
    ascii_r = r.encode('unicode_escape').decode() if False else r
    return (r[:14] + '…') if len(r) > 15 else r
FL = lambda cur, done=(): {'nodes': [['生成输入', 'st.text()'], ['执行 property', 'decode(encode(s)) == s'], ['发现失败', ''], ['缩小(shrink)', '找最小反例'], ['最终反例', '']], 'cur': cur, 'done': list(done)}
steps = []
vals = []
for i, s in enumerate(seen):
    bad = s in uniq or (i in (6, 8))
    vals.append([disp(s), '失败' if bad else '通过'])
    kind = 'fail' if bad else 'ok'
    note = f"第 {i+1} 个随机输入 {disp(s)}:" + ("包含数字字符 → 编码后无法还原 → property 失败。" if bad else "通过。")
    steps.append(step(note, fl=FL([2] if bad else [1], [0]), inp={'values': [list(v) for v in vals], 'cur': [i] if bad else [], 'done': [k for k, v in enumerate(vals) if v[1] == '通过' and k != i] if not bad else [k for k, v in enumerate(vals) if v[1] == '通过'], 'mark': [k for k, v in enumerate(vals) if v[1] == '失败']}, kv={'items': [['已调用', f'{i+1} 次'], ['失败', f"{sum(1 for v in vals if v[1]=='失败')} 次"]], 'hl': []}))
steps.append(step(f"Hypothesis 有了失败的输入,开始缩小:把它变短、把字符换成「更简单」的字符,每次重新跑一遍 property,只要还失败就接受。整个过程 property 又被调用了 {calls-len(seen)} 次。", fl=FL([3], [0, 1, 2]), inp={'values': [[disp(u), f'长度 {len(u)}'] for u in uniq], 'cur': [], 'mark': [], 'done': []}, kv={'items': [['总调用', f'{calls} 次'], ['其中失败', f'{fails} 次']], 'hl': ['总调用']}))
steps.append(step(f"缩小过程中依次留下的失败输入:{' → '.join(disp(u) for u in uniq)}。最终反例是 '0'——一个字符。编码得到 '10',解码时把 '1' '0' 都当成了重复次数,没有字符可重复,返回空串,不等于原来的 '0'。", fl=FL([4], [0, 1, 2, 3]), inp={'values': [[disp(u), f'长度 {len(u)}'] for u in uniq], 'cur': [len(uniq) - 1], 'mark': [], 'done': list(range(len(uniq) - 1))}, kv={'items': [['最小反例', "'0'"], ['encode("0")', "'10'"], ['decode("10")', "''(空串)"]], 'hl': ['最小反例']}))
A = dict(
    n=99,
    tags='Python,测试,hypothesis,真实验证,动画演示',
    desc=f'本机 hypothesis 6.168.3 真实测一个行程编码函数:手写 7 个例子全部通过,而 property「decode(encode(s)) == s」在第 7 个随机输入 Ö7 就失败并缩小到最小反例 "0";第一次「修复」排除 Nd 类别仍被发现 "²"(isdigit 为真但类别是 No)引起 ValueError;失败例子被记入 .hypothesis 数据库,第二次运行只调用 2 次就复现。',
    lead='手写测试只能覆盖你想到的输入。基于属性的测试(property-based testing)换了个思路:你描述「对任何输入都应成立的规律」,让 Hypothesis 去生成成百上千个输入,找到反例后还会自动把它缩到最小。这篇用一个看上去没问题的行程编码函数,亲眼看它怎么被找出毛病。',
    facts=[('7 / 7 通过', '手写的 7 个例子全部通过——bug 依然在'), ("'0'", 'Hypothesis 缩小得到的最小反例,只有 1 个字符'), ('2 次', '失败被记入数据库后,重跑只调用了 2 次 property 就复现')],
    body=[
        sec('做的事:一个「看起来没问题」的行程编码', '',
            src('rle.py', '''def rle_encode(s):               # "aaabcc" → "3a1b2c"
    out = []; i = 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]: j += 1
        out.append(f"{j - i}{s[i]}"); i = j
    return "".join(out)

def rle_decode(t):
    out = []; num = ""
    for ch in t:
        if ch.isdigit(): num += ch
        else: out.append(ch * int(num)); num = ""
    return "".join(out)'''),
            term('', block('== 一', '== 二')),
            '<p>7 个手写例子(<code>"aaabcc"</code>、空串、<code>"hello world"</code>……)全部通过。这些都是「合理的输入」,恰好绕开了 bug。</p>'),
        sec('验证一:告诉 Hypothesis 一条规律', '', src('property', '''@given(st.text(max_size=30))
def prop(s):
    assert rle_decode(rle_encode(s)) == s'''), term('', block('== 二', '== 三')),
            f'<p>不到 20 次调用就失败了:第 7 个随机输入 <code>\'Ö7\'</code>(含数字字符)就让往返不成立。Hypothesis 报告的不是这个随机串,而是<b>缩小之后的最小反例 <code>\'0\'</code></b>——「note」里给出的 <code>s=\'0\'</code> 就是你可以直接拿去写回归测试的输入。整个过程 property 被调用了 {calls} 次,其中 {fails} 次失败(都是缩小阶段的试探)。仔细看被调用的前 12 个输入:空串、单字符、带控制字符和各种 Unicode 的字符串——它们不是随便乱来的,Hypothesis 会偏向边界值(空串排第一个)。</p>'
            '<p>原因:<code>encode("0")</code> 得到 <code>"10"</code>,解码时 <code>1</code> 和 <code>0</code> 都被当成数字累积成重复次数,没有后续字符可重复,返回空串。行程编码没有为「输入本身含数字」留出转义,这是设计上的漏洞。</p>'),
        sec('验证二:「修复」得不彻底,它会再次找到', '只排除 Unicode 类别 Nd 的字符', term('', block('== 三、', '== 三·补')),
            '<p>我第一次的修复思路是:输入里不要出现十进制数字字符(类别 <code>Nd</code>)。Hypothesis 立刻又找到两种失败:<code>\'²\'</code>(上标 2)的 <code>isdigit()</code> 是 True——而它的类别是 <code>No</code>、<code>isdecimal()</code> 却是 False,所以既躲过了我的类别过滤,又骗过了 <code>decode</code> 里的 <code>isdigit()</code> 判断,最后 <code>int(\'1²1\')</code> 抛出 <code>ValueError</code>。一个手写例子里很难想到「上标数字」。</p>'),
        sec('验证三:用真正的判据过滤', '', term('', block('== 三·补', '== 四')),
            '<p>直接用 <code>str.isdigit</code> 本身当条件过滤,300 个随机输入全部通过。要注意:这只是把「有 bug 的输入范围」排除了——真正的修法是给编码格式加上转义或改用长度前缀,让含数字的输入也能正确往返。</p>'),
        sec('验证四:失败会被记住', '', term('', block('== 四', '== 五')),
            '<p>默认情况下 Hypothesis 会把找到的失败例子存进当前目录的 <code>.hypothesis/examples</code>。第一次运行调用了十几次才碰到反例;第二次运行,它先回放数据库里的旧反例,只调用 2 次就再次失败——所以修 bug 期间每次重跑都是立刻复现,不必再等随机碰运气。这个目录不要提交进版本库(它自带 <code>.gitignore</code>)。</p>'),
        sec('验证五:生成的输入会偏向边界', '', term('', block('== 五', 'zzzz')),
            '<p>100 个 <code>st.integers()</code> 样本里既有 0、也有远超 <code>2**32</code> 的大整数(20 个),最大的有 37 位;100 个 <code>st.text()</code> 里有空串、91 个含非 ASCII 字符、20 个含数字字符。这种「刻意覆盖极端值」的分布,是它比随机数更容易撞出 bug 的原因。</p>'),
        sec('分步演示:从随机输入到最小反例', '输入序列取自上面实验的真实记录(带 derandomize=True,可重复)',
            demo('Hypothesis 找到并缩小反例', [('fl', 'flow', '阶段'), ('inp', 'chips', '输入(小字是结果)'), ('kv', 'kv', '计数')], steps, '当前输入')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,hypothesis 6.168.3、pytest 9.1.1(临时虚拟环境);演示部分用 <code>derandomize=True</code>、<code>database=None</code> 保证可重复,验证四没有关闭随机和数据库',
          '没有验证:stateful 测试、<code>st.builds</code>/<code>st.composite</code> 的组合策略、<code>@example</code> 固定用例、profile 设置对 CI 的影响'],
)
