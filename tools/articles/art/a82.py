import json
from lib import *
txt = out('82').splitlines()
R = json.load(open('out/82.json'))
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
ts, tc, tn = R['t']
FL = lambda cur, done=(): {'nodes': [['源码字符串', ''], ['compile', ''], ['code 对象', ''], ['exec / eval', ''], ['命名空间字典', '']], 'cur': cur, 'done': list(done)}
steps = [step("一个空字典 ns = {} 准备当作全局命名空间。要执行的四段源码都还只是字符串。", fl=FL([0]), kv={'items': [], 'hl': []})]
notes = ["compile 得到 code 对象(co_names=('x',)),exec 执行它:命名空间里多了 x。",
         "第二段读 x、写 y。exec 用的就是同一个 ns,所以能看到刚才的 x。",
         "def 语句执行的结果是在 ns 里绑定了一个函数对象 sq。",
         "z = sq(y):函数在 ns 里被找到并调用,z=36。"]
for i, (s, snap) in enumerate(zip(R['stmts'], R['snaps'])):
    steps.append(step(f"exec({s!r})。" + notes[i], fl=FL([3, 4], [0, 1, 2]), kv={'items': [[k, str(v)] for k, v in snap.items()], 'hl': [list(snap.keys())[-1]]}))
steps.append(step("eval('z + 1', ns):eval 也从 ns 里取名字,并且有返回值 37;exec 没有返回值。", fl=FL([3], [0, 1, 2]), kv={'items': [[k, str(v)] for k, v in R['snaps'][-1].items()] + [['eval 的返回值', str(R['ev'])]], 'hl': ['eval 的返回值']}))

A = dict(
    n=82,
    tags='Python,标准库,编译原理,安全,真实验证,动画演示',
    desc=f'本机真实验证 compile 的 eval/exec/single 三种模式,exec 会往传入的字典里塞 __builtins__,在函数里 exec 写的变量读不到;空 __builtins__ 拦得住 print 却拦不住通过 object.__subclasses__() 找回 __import__(实测调用了 os.getpid());eval 字符串 {ts:.0f} ns 而预编译 code {tc:.0f} ns。',
    lead='<code>eval</code>、<code>exec</code>、<code>compile</code> 三个函数常被混着用,其实是同一条流水线的不同环节:字符串 → code 对象 → 在某个字典里执行。这篇把每个环节的输入输出、命名空间、以及「空 builtins 就安全」的误解都实测了一遍。',
    facts=[('3 种 mode', 'eval 只接表达式、exec 接语句、single 像交互式解释器'), (f'{ts:.0f} → {tc:.0f} ns', 'eval(字符串) 与 eval(预编译 code) 单次耗时'), ('280 个类', '空 __builtins__ 下仍能通过 () 摸到的类,足以找回 __import__')],
    body=[
        sec('验证一:三种 mode 的区别', '', term('', block('== 一', '== 二')),
            '<p><code>mode=\'eval\'</code> 只接受一个表达式,<code>x = 1</code> 这种语句直接 SyntaxError;<code>\'exec\'</code> 接受任意语句,<code>co_names</code> 里列出了会用到的名字;<code>\'single\'</code> 是交互式解释器用的模式,表达式语句的值会被打印出来(输出里的孤零零的 <code>3</code>)。返回值上:<code>eval</code> 返回表达式的值,<code>exec</code> 永远返回 <code>None</code>。</p>'),
        sec('验证二:代码写进了哪个字典', '', term('', block('== 二', '== 三')),
            '<p><code>exec</code> 把定义的名字都写进你传的字典,并且会自动往里加一个 <code>__builtins__</code> 键(值是一个字典)。<b>在函数里直接 <code>exec("z = 99")</code>,然后读 z,得到 NameError</b>——exec 改的是一份局部变量快照,不是函数真实的局部变量。想拿到结果,就显式传一个字典进去读,像最后一行那样。</p>'),
        sec('验证三:空 __builtins__ 不是沙箱', '', term('', block('== 三', '== 四')),
            callout('把 <code>__builtins__</code> 设成空字典,直接写 <code>print</code> 确实会 NameError,很多人因此以为「安全了」。但 Python 的对象之间有大量相互引用:从一个元组 <code>()</code> 出发沿着 <code>__class__ → __base__ → __subclasses__()</code> 能摸到 280 个类,其中某个类的实例里又带着 <code>__builtins__</code>,于是 <code>__import__</code> 被找回来,<code>os.getpid()</code> 被调用,返回值和当前进程一致。<b>不要用 <code>eval</code>/<code>exec</code> 加受限 builtins 去执行不可信的输入。</b>'),
            '<p>解析不可信的字面量用 <code>ast.literal_eval</code>(见上一篇);要执行不可信代码,需要的是进程级隔离,而不是替换命名空间。</p>'),
        sec('验证四:code 对象里有什么', '', term('', block('== 四', '== 五')),
            '<p>函数的 <code>__code__</code> 和 <code>compile</code> 的返回值是同一种东西:参数个数、局部变量名、常量表、用到的全局名、定义所在的文件与行号,以及字节码本身(<code>co_code</code>,就是 bytes)。<code>exec</code> 一个 code 对象和 <code>exec</code> 一个字符串效果一样,只是跳过了编译。</p>'),
        sec('验证五:文件名会出现在回溯里', '所以别总用默认的 "&lt;string&gt;"', term('', block('== 五', '== 六')),
            '<p><code>compile</code> 的第二个参数就是回溯里显示的「文件名」。给用户配置、模板、DSL 起一个有意义的名字(比如 <code>&lt;用户配置第3行&gt;</code>),出错时一眼就知道是哪一段。<code>SyntaxError</code> 里也带着 filename 和 lineno。</p>'),
        sec('验证六:optimize 会去掉 assert', '', term('', block('== 六', '== 七')), term('', out('82b')),
            '<p><code>optimize=1</code> 时 <code>assert</code> 语句根本没有被编译进去——命令行的 <code>-O</code> 开关也是同样的效果(见上面加了 -O 的那条命令),所以用 assert 做的校验会整个消失。绝不要用 assert 做输入校验或权限检查。</p>'),
        sec('验证七:每次 eval 字符串都要重新编译', '', term('', block('== 七', '== 八')),
            f'<p>同一个表达式,<code>eval(字符串)</code> 每次 {ts:.0f} ns;先 <code>compile</code> 一次,再反复 <code>eval(code)</code> 只要 {tc:.0f} ns,快了约 {ts/tc:.0f} 倍;而直接写成 Python 表达式是 {tn:.0f} ns。如果要在循环里反复求值同一段表达式(比如用户配置的规则),一定要预编译。</p>'),
        sec('分步演示:字符串怎样变成命名空间里的名字', '每一步的字典都是上面实验的实际内容',
            demo('exec / eval 与命名空间', [('fl', 'flow', '流水线'), ('kv', 'kv', 'ns 命名空间里此刻有什么(不含 __builtins__)')], steps, '此刻新写入的名字')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,内置 <code>compile</code>、<code>eval</code>、<code>exec</code>,标准库 <code>dis</code>、<code>traceback</code>',
          '没有验证:<code>locals()</code> 的具体语义在不同版本的差异、<code>flags</code>/<code>dont_inherit</code> 的其他取值、更严格的沙箱手段(进程隔离等)'],
)
