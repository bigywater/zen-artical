import json
from lib import *
txt = out('83').splitlines()
R = json.load(open('out/83.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())

# 演示 A: 逐个 token
toks = R['toks']
descA = {'NAME': '名字(变量或关键字都是 NAME)', 'OP': '运算符/标点', 'NUMBER': '数字字面量', 'COMMENT': '注释——tokenize 保留它,ast 会丢掉', 'NEWLINE': '逻辑行结束', 'ENDMARKER': '文件结束'}
steps = []
for i, (ty, s, c0, c1) in enumerate(toks):
    vals = [[('\\n' if t[1] == '\n' else (t[1] or '∅')), t[0]] for t in toks[:i + 1]]
    steps.append(step(f"第 {i+1} 个 token:{ty} {s!r},占第 {c0}–{c1} 列。{descA.get(ty, '')}", src={'lines': ["total = price * 3  # 加税"], 'mark': [0]}, tk={'values': vals, 'cur': [i]}, ind={'items': [], 'hl': -1}))
# 演示 B: 缩进栈
row2 = R['row2']; lines = ["if x:", "    y = 1", "    if z:", "        w = 2", "v = 3"]
stack = [0]; cur_tokens = []; line_i = 0
def indent_state(): return {'items': [f"缩进 {n}" for n in stack], 'hl': len(stack) - 1}
allv = []
li = 0; buf = []
for ty, s in row2:
    label = ('\\n' if s == '\n' else (s.strip() or '∅'))
    buf.append([label, ty]); allv.append([label, ty])
    if ty == 'INDENT': stack.append(stack[-1] + 4)
    if ty == 'DEDENT': stack.pop()
    if ty == 'NEWLINE':
        nxt = row2[len(allv)][0] if len(allv) < len(row2) else ''
        # 当前行结束后, 若下一个 token 是 DEDENT 则连同一起呈现
        steps.append(step(f"第 {li+1} 行 {lines[li]!r} 读完。缩进栈:{stack}", src={'lines': lines, 'mark': [li]}, tk={'values': list(allv), 'cur': [len(allv) - 1]}, ind=indent_state()))
        li += 1
    elif ty in ('INDENT', 'DEDENT'):
        steps.append(step(f"看到 {ty}:{'缩进变深,栈压入一层' if ty=='INDENT' else '缩进变浅,栈弹出一层'} → {stack}", src={'lines': lines, 'mark': [min(li, 4)]}, tk={'values': list(allv), 'cur': [len(allv) - 1]}, ind=indent_state()))
# 演示 A 的第一个 step 之后 panels 保持一致
A = dict(
    n=83,
    tags='Python,标准库,编译原理,真实验证,动画演示',
    desc='本机真实用 tokenize 切分源码:一行赋值被切成 8 个 token(含 COMMENT 和 NEWLINE);缩进以 INDENT/DEDENT token 表示;注释在 tokenize 里保留而在 ast 里不存在;f-string 在 3.12+ 被拆成 FSTRING_START/MIDDLE/END;括号内换行是 NL 而不是 NEWLINE;inconsistent 缩进 tokenize 不报错而 compile 报 IndentationError。',
    lead='语法树之前还有一步:词法分析。<code>tokenize</code> 模块能让你看到这一步的原始产物——每个 token 的类型、文本、起止位置。这篇把它从头到尾摊开:注释去哪了、缩进怎么变成 token、f-string 怎么被拆开、哪些错误发生在这一步。',
    facts=[('8 个 token', '一行 total = price * 3 # 加税 的切分结果'), ('INDENT / DEDENT', '缩进被当成 token,而不是字符'), ('NL ≠ NEWLINE', '括号里的换行不结束一条语句')],
    body=[
        sec('验证一:一行代码被切成哪些 token', '',
            src('源码', 'total = price * 3  # 加税'),
            term('tokenize.generate_tokens(...)', block('== 一', '== 二')),
            '<p>每个 token 带有类型、字符串、起止行列。空白不产生 token(只体现在位置上);行末的 <code>NEWLINE</code> 标志一条逻辑语句结束;<code>ENDMARKER</code> 标志文件结束。<b>注释是一个 <code>COMMENT</code> token</b>——它出现在 tokenize 里,却不会出现在语法树里(见下面验证三)。</p>'),
        sec('验证二:缩进是 token', '', term('', block('== 二', '== 三')),
            '<p>Python 不用花括号,块结构由缩进决定。词法分析器为此维护一个缩进栈:某行缩进比栈顶深,输出一个 <code>INDENT</code>;变浅,就输出一个(或几个)<code>DEDENT</code>。上面最后的 <code>w = 2</code> 之后连续两个 <code>DEDENT</code>,是因为下一行 <code>v = 3</code> 直接退回了最外层,要一口气弹出两层。</p>'),
        sec('验证三:tokenize 与 ast 看到的东西不同', '', term('', block('== 三', '== 四')),
            '<p>注释在 tokenize 里有,在 ast 里没有(<code>ast.dump</code> 里找不到「加税」)。所以需要保留注释和原始格式的工具(格式化、重构)要在 tokenize 层工作。另外,<code>def</code>、<code>return</code> 这样的关键字和普通变量一样,在 tokenize 里都是 <code>NAME</code>;是不是关键字要靠 <code>keyword</code> 模块判断。软关键字(<code>match</code>、<code>case</code>、<code>_</code>、<code>type</code>)在别处可以当变量名用,更没法在这一层区分。</p>'),
        sec('验证四:f-string 被拆开了', '', term('', block('== 五', '== 六')),
            '<p>本机这版 Python 里 <code>f"a{x + 1}b"</code> 不再是一个整体的 STRING,而是 <code>FSTRING_START</code>、<code>FSTRING_MIDDLE</code>、花括号里的普通 token(<code>x</code>、<code>+</code>、<code>1</code>)、再一个 <code>FSTRING_MIDDLE</code>、<code>FSTRING_END</code>。所以花括号里的表达式和普通代码用同一套规则切分。</p>'),
        sec('验证五:括号里换行不算一条语句结束', '', term('', block('== 六', '== 七')),
            '<p>括号没闭合时的换行是 <code>NL</code>(非逻辑换行),不是 <code>NEWLINE</code>。两行文字里 <code>x = (1 +\\n 2)</code> 只产生一个 NEWLINE,加上后面 <code>y = 3</code> 的一个,共 2 个;NL 是 1 个。这也是为什么在括号里可以随意折行。</p>'),
        sec('验证六:哪些错误在词法分析阶段出现', '', term('', block('== 七', '== 八')),
            '<p>字符串没闭合、括号没闭合,<code>tokenize</code> 直接抛 <code>TokenError</code>,<code>compile</code> 报的是 SyntaxError,两者位置说法略有不同。有意思的是最后一条:缩进不一致的那段代码 <code>tokenize</code> 完全没报错,<code>compile</code> 才报 <code>IndentationError</code>——<code>tokenize</code> 模块和真正的编译器词法分析并非一回事,它是给工具用的宽松版本。用它做静态检查时要记住这一点。</p>'),
        sec('验证七:真实文件里的 token 分布', '', term('', block('== 八', 'zzzz')),
            '<p>364 行的 <code>json/decoder.py</code>:NAME 和 OP 加起来占了绝大多数,72 对 INDENT/DEDENT 说明有 72 个缩进块,15 个注释。</p>'),
        sec('分步演示:一行代码的切分,以及缩进栈', '每一步都是 tokenize 的真实输出',
            demo('tokenize 逐个 token 读源码', [('src', 'term', '源码'), ('tk', 'chips', '已经读出的 token(下方小字是类型)'), ('ind', 'stack', '缩进栈')], steps, '刚读到的 token')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>tokenize</code>、<code>token</code>、<code>keyword</code>、<code>ast</code>',
          '没有验证:C 解析器内部的词法分析与 tokenize 模块在边界情况上的其他差异、tab 与空格混用的处理、字节流输入(<code>tokenize.tokenize</code>)与编码声明'],
)
