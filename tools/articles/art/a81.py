import json
from lib import *
txt = out('81').splitlines()
R = json.load(open('out/81.json'))['order']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
bc = [f"{op:<11} {arg}" for op, arg in R]
# 堆式下标: a + b * c → ['+','a','*',None,None,'b','c']
T1 = ['+', 'a', '*', None, None, 'b', 'c']
def tr(vals, **k): return dict(values=vals, **k)
steps = [
    step("源码 x = a + b * c 里的表达式部分是 a + b * c。词法分析先切成 token,语法分析按优先级把它们组装成树——先从空树开始。", t=tr([]), bc={'lines': bc, 'cur': []}),
    step("根节点是最后才会算的那个运算:+(加号优先级低于乘号,所以它在树的最上面)。", t=tr(['+'], cur=[0]), bc={'lines': bc, 'cur': []}),
    step("加号的左操作数是名字 a。", t=tr(['+', 'a'], cur=[1], done=[0]), bc={'lines': bc, 'cur': []}),
    step("右操作数不是一个名字,而是整个 b * c——乘号成为加号的右子树。这就是「乘法先算」在树里的样子。", t=tr(['+', 'a', '*'], cur=[2], done=[0, 1]), bc={'lines': bc, 'cur': []}),
    step("乘号的两个操作数 b 和 c。树建好了(ast.dump 里对应 BinOp(left=a, Add, right=BinOp(b, Mult, c)))。", t=tr(T1, cur=[5, 6], done=[0, 1, 2]), bc={'lines': bc, 'cur': []}),
    step("编译器对树做后序遍历生成字节码。第 1 条:LOAD_NAME a。", t=tr(T1, cur=[1]), bc={'lines': bc, 'cur': [0]}),
    step("第 2 条:LOAD_NAME b。", t=tr(T1, cur=[5], done=[1]), bc={'lines': bc, 'cur': [1]}),
    step("第 3 条:LOAD_NAME c。", t=tr(T1, cur=[6], done=[1, 5]), bc={'lines': bc, 'cur': [2]}),
    step("第 4 条:BINARY_OP *——b 和 c 先算。", t=tr(T1, cur=[2], done=[1, 5, 6]), bc={'lines': bc, 'cur': [3]}),
    step("第 5 条:BINARY_OP +——最后才加。这个顺序正好是上面 dis 真实输出的顺序。", t=tr(T1, cur=[0], done=[1, 2, 5, 6]), bc={'lines': bc, 'cur': [4]}),
    step("换成 (a + b) * c:同样三个名字、同样两个运算符,但树的形状完全不同——加号在下面,乘号成了根。括号本身没有出现在树里,它只是改变了形状。", t=tr(['*', '+', 'c', 'a', 'b'], mark=[0, 1]), bc={'lines': ['ast.dump((a + b) * c) 的形状:', 'BinOp(BinOp(a, Add, b), Mult, c)'], 'cur': []}),
]
A = dict(
    n=81,
    tags='Python,标准库,编译原理,真实验证,动画演示',
    desc='本机真实用 ast 解析源码:括号与注释都不在树里、优先级由树形状表达;统计 json/decoder.py 的 1759 个节点(48 种类型);用 NodeTransformer 把常量都加 1 后重新编译执行得到 39;literal_eval 拒绝函数调用而 eval 直接执行;编译器会常量折叠(2*3+1 直接变成 7)。',
    lead='Python 在执行代码之前先把源码变成一棵树。这篇用 <code>ast</code> 模块把这棵树摊开来看:括号去哪了、注释去哪了、优先级怎么变成形状、改树之后再执行会怎样——每一项都是真跑出来的。',
    facts=[('1759 个节点', 'json/decoder.py 这一个文件(364 行)的 AST 节点数'), ('39', '把 10*2+5 里所有整数常量 +1 之后重新编译,执行出的结果(11*3+6)'), ('LOAD_SMALL_INT 7', '2*3+1 在编译时就折叠成了 7')],
    body=[
        sec('验证一:一行赋值的语法树', '', src('源码', 'x = a + b * c'), term('ast.dump(ast.parse(src), indent=2)', '\n'.join(txt[1:13])),
            '<p>根是 <code>Module</code>,里面一条 <code>Assign</code>,赋值号右边是一个 <code>BinOp</code>。注意加号是根、乘号被挂在加号的<b>右子树</b>里——<code>+</code> 的优先级低于 <code>*</code>,所以乘法在树里更深,更早求值。<code>Name</code> 上的 <code>ctx=Load()/Store()</code> 区分「读」和「写」这个名字。</p>'),
        sec('验证二:括号不在树里', '优先级和括号只用形状来表达', term('', block('== 二', '== 三')),
            '<p>三个写法里,<code>(a + b) * c</code> 的树形状不同(加号在乘号下面);而 <code>a + b * c</code> 和 <code>a + (b * c)</code> 的树完全相同——那对多余的括号从解析结果里消失了。</p>'),
        sec('验证三:注释和空白也不在树里', '', term('', block('== 三', '== 四')),
            '<p>带注释和一堆空白的源码,与干净源码的 <code>ast.dump</code> 完全一样。所以「用 ast 解析后再 <code>unparse</code> 回写」会丢注释、统一格式(括号按需重新生成)——需要保留注释和格式的重构工具不能只靠 <code>ast</code>。位置信息则保留在每个节点上:<code>lineno</code>、<code>col_offset</code>、<code>end_lineno</code>、<code>end_col_offset</code>,可以精确指回源码。</p>',
            term('', block('== 四', '== 五'))),
        sec('验证四:拿真实文件数一数', '', term('', block('== 五', '== 六')),
            '<p>标准库的 <code>json/decoder.py</code> 364 行,树里有 1759 个节点、48 种类型。最多的是 <code>Name</code> 和 <code>Load</code>——绝大多数节点都是「读一个名字」。<code>ast.walk</code> 可以遍历整棵树,写 lint 工具、找函数定义、统计调用,都是这类遍历。</p>'),
        sec('验证五:改树,再让 Python 执行', '', term('', block('== 六', '== 七')),
            '<p>用 <code>NodeTransformer</code> 把所有整数常量加 1,<code>unparse</code> 出来的是 <code>11 * 3 + 6</code>,<code>compile</code> 后执行得到 39;而 <code>print</code> 里的字符串常量没有被动(我只改了 int)。整个流程就是:解析成树 → 改树 → 重新编译 → 执行,不需要碰源码文本。</p>'),
        sec('验证六:literal_eval 和 eval 的区别', '', term('', block('== 七', '== 八')),
            '<p><code>literal_eval</code> 只接受字面量(字典、列表、元组、数字、字符串)组成的树,遇到函数调用这样的节点直接 <code>ValueError</code>;<code>eval</code> 则毫不犹豫地执行了 <code>__import__(\'os\').getcwd()</code>。解析来自外部的配置字符串,请用 <code>literal_eval</code>——但要记住它也不是万能沙箱,它只保证「不执行代码」,不保证「输入合理」。</p>'),
        sec('验证七:编译器在树上做的事', '常量折叠 + 后序遍历', term('', block('== 八', 'zzzz')),
            '<p><code>2 * 3 + 1</code> 编译后只有一条 <code>LOAD_SMALL_INT 7</code>——编译器在树上就把常量算掉了,运行时没有任何乘法。而 <code>a * b + 1</code> 里有变量,保留了完整的运算:先 <code>LOAD a</code>、<code>LOAD b</code>、<code>*</code>,再 <code>+ 1</code>。<code>a + b * c</code> 的执行顺序是 a、b、c、乘、加,正是这棵树的后序遍历。</p>'),
        sec('分步演示:一棵表达式树的生长与求值', '树的形状、字节码顺序都来自上面的真实输出',
            demo('a + b * c 的语法树', [('t', 'tree', '语法树'), ('bc', 'term', '字节码(dis 的真实输出)')], steps, '当前节点 / 当前字节码')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>ast</code>、<code>dis</code>',
          '没有验证:词法分析(tokenize)阶段的细节(见第 83 篇)、类型注释、不同 Python 版本 AST 节点的差异、更复杂语句(函数、类、推导式)的树形状'],
)
