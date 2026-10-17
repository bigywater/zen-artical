from lib import *
S = SS('g100')
steps = [
    step("管道:前一个命令的结果作为后一个命令的最后一个参数。{{.Name | printf \"%q\"}} → \"小明\";{{3 | printf \"%d-%d\" 1}} → 1-3(3 是最后一个参数);{{.Name | printf \"%q\" | len}} → 8;{{len .Tags | printf \"标签数=%d\"}} → 标签数=2;{{printf \"%s=%d\" .Name .Age}} → 小明=20;{{.Greeting}}(值接收者的方法)→ 你好,小明;{{.PtrMethod}} 对值 u 执行出错 can't evaluate field PtrMethod in type main.User,对 &u 则正常输出“指针方法:小明”。", t=tl(S(1)), done=lidx(S(1), '1-3', '"小明"', '标签数=2', '指针方法'), mark=lidx(S(1), 'PtrMethod}}(值 u)'), kv=KV([['管道', '结果作为后一个命令的最后一个参数'], ['值接收者方法', '值和指针都能调用'], ['指针接收者方法', '数据必须是可寻址的指针,否则报错']], ['指针接收者方法'])),
    step("变量与作用域:在 if 里用 := 声明新变量,if 结束后外面的 $x 还是 1;用 = 赋值则改到了外面的变量,结果 2;range 里 {{$n = add $n .}} 累加 1+2+3+4 → 10;range $i, $v 给出下标和值 0=x;1=y;;$ 始终指向传入的根数据(小明-a;小明-b;);with 改变 .:a|小明。", t=tl(S(2)), done=lidx(S(2), '用 = 赋值', 'range 里累加', '$ 指向根数据'), mark=lidx(S(2), '用 := 声明', 'with 改变'), kv=KV([[':=', '新变量,作用到所在的 {{end}}'], ['=', '修改外层变量'], ['$', '根数据,在 range / with 里也能用']], ['$'])),
    step("缺 key、缺字段与未定义的函数:map 缺 key 默认输出 <no value>;Option(\"missingkey=error\") 执行出错 map has no entry for key \"b\";missingkey=zero 输出零值 0;结构体缺字段在执行时报 can't evaluate field Nope in type main.User;nil 指针上取字段报 nil pointer evaluating *main.User.Name;未定义的函数在解析时就失败:function \"nofunc\" not defined。", t=tl(S(3)), mark=lidx(S(3), '<no value>', 'missingkey=error', '缺字段', 'nil 指针', 'nofunc'), done=lidx(S(3), 'missingkey=zero'), kv=KV([['map 缺 key', '默认静默输出 <no value>'], ['结构体缺字段', '执行时报错(不是解析时)'], ['未定义函数', '解析时报错']], ['map 缺 key'])),
    step("什么算“真”:{{if .}} 对空字符串、0、空切片、nil 都是假;对非空 map、零值结构体是真。or 会短路:{{or true (side)}} 里 side() 被调用了 0 次。", t=tl(S(4)), done=lidx(S(4), '对非空 map', '对结构体(零值)'), mark=lidx(S(4), '空字符串', '对 0', '空切片', '对 nil', 'side()'), kv=KV([['假', '空字符串、0、nil、空 slice/map'], ['真', '非空 map、零值结构体'], ['or / and', '短路求值']], ['真'])),
    step("FuncMap:div 10 2 → 5;div 10 0(函数返回 error)→ 已经输出的 \"前缀\" 留在输出里,执行出错 error calling div: 除数为 0;先 Parse 再 Funcs 会 panic:function \"up\" not defined(函数必须在 Parse 之前注册);FuncMap 里的函数返回 3 个值时 panic:function bad has 3 return values; should be 1 or 2。", t=tl(S(5)), done=lidx(S(5), 'div 10 2'), mark=lidx(S(5), 'div 10 0', '先 Parse 再 Funcs', '返回 3 个值'), kv=KV([['函数返回 error', '执行中断,已输出部分保留'], ['注册时机', '必须在 Parse 之前'], ['返回值个数', '1 个或 2 个(第二个是 error)']], ['注册时机'])),
    step("空白修剪:不修剪时 \"[\\n{{.Name}}\\n]\" 输出 [\\n小明\\n];用 {{- .Name -}} 修剪两侧空白后输出 [小明]。", t=tl(S(6)), mark=lidx(S(6), '修剪'), done=lidx(S(6), '不修剪'), kv=KV([['{{-', '去掉左边的空白(含换行)'], ['-}}', '去掉右边的空白(含换行)']], ['{{-'])),
    step("成本:已解析的模板 Execute 612 ns/次、6 次分配;fmt.Fprintf 77 ns/次、1 次分配;每次都 Parse + Execute 3474 ns/次、69 次分配。模板解析一次、复用。", t=tl(S(7)), mark=lidx(S(7), '已解析的模板'), b=bars([['fmt.Fprintf (ns)', 77, '77'], ['已解析模板 Execute', 612, '612'], ['每次 Parse + Execute', 3474, '3474']], 3474, done=[0, 1], mark=[2]), kv=KV([['Fprintf', '77 ns'], ['Execute', '612 ns,约 8 倍'], ['每次都 Parse', '3474 ns、69 次分配,约 5.7 倍于 Execute']], ['每次都 Parse'])),
    step("文档(go doc text/template):管道可以用 '|' 连接一串命令构成“链”;在链式管道里,每个命令的结果作为下一个命令的最后一个参数;最后一个命令的输出就是管道的值。", t=tl(S(8)), done=lidx(S(8), 'chained', 'last argument'), kv=KV([['管道', '命令用 | 串联'], ['传值方式', '结果作为下一个命令的最后一个参数']], ['传值方式'])),
]
A = mkartg('g100', 100, 'Go,text/template,模板,管道,FuncMap,真实验证,动画演示',
    '在 Go 1.27.1 里实测 text/template 的求值规则:管道把结果作为后一个命令的最后一个参数(3 | printf "%d-%d" 1 得到 1-3);:= 与 = 的作用域差别;map 缺 key 默认输出 <no value>,missingkey=error 才报错;空字符串、0、nil、空 slice 为假,or 会短路;FuncMap 必须在 Parse 之前注册,函数返回 error 会中断执行;已解析模板 Execute 612 ns,每次都 Parse 要 3474 ns。',
    'text/template 的管道、变量和函数调用有一套自己的求值规则,和 Go 代码的直觉不完全一样:管道把值放在最后一个参数,变量用 := 和 = 的作用域不同,缺 key 默认不报错。这篇用一个个小模板验证这些规则,并量解析与执行的成本。',
    [('1-3', '{{3 | printf "%d-%d" 1}} 的输出:管道的值是 printf 的最后一个参数'), ('<no value>', 'map 缺 key 时的默认输出;Option("missingkey=error") 才会报错'), ('612 vs 3474 ns', '已解析模板的 Execute 与每次都 Parse + Execute 的耗时')],
    [('管道的参数位置', '<p>管道把前一个命令的结果放在后一个命令<strong>最后一个</strong>参数的位置:<code>{{3 | printf "%d-%d" 1}}</code> 得到 <code>1-3</code>。所以要在函数设计时把“被管道传进来的值”放在参数列表最后。方法也能直接调用,但指针接收者的方法在传值数据上会报 “can&#39;t evaluate field”。</p>'),
     ('变量作用域', '<p><code>:=</code> 声明的变量到所在块的 <code>{{end}}</code> 为止,内层的 <code>{{$x := 2}}</code> 不会影响外面的 <code>$x</code>;<code>=</code> 才是改外面的变量(range 里累加就靠它);<code>$</code> 始终指向传入的根数据。</p>'),
     ('缺失的东西', '<p>map 缺 key 默认输出 <code>&lt;no value&gt;</code>,要报错得设 <code>missingkey=error</code>;结构体缺字段在执行时报错;nil 指针取字段报错;未定义的函数在解析时就失败。所以模板里的拼写错误,有的要等到运行时才暴露。</p>'),
     ('真值与短路', '<p>空字符串、0、nil、空切片/map 为假,非空 map 与零值结构体为真;<code>or</code>/<code>and</code> 短路,<code>{{or true (side)}}</code> 里 <code>side()</code> 一次都没被调用。</p>'),
     ('FuncMap', '<p>函数必须在 <code>Parse</code> 之前注册,否则解析时就 panic;函数可以返回一个值或两个值(第二个是 error),返回 error 会中断执行,中断前已经写出的输出仍然保留在 writer 里。</p>'),
     ('空白', '<p><code>{{-</code> 与 <code>-}}</code> 去掉动作两侧的空白(包括换行),生成纯文本格式时很常用。</p>'),
     ('成本', '<p>已解析的模板 <code>Execute</code> 约 612 ns,是 <code>fmt.Fprintf</code> 的约 8 倍;每次都 <code>Parse</code> 要 3474 ns、69 次分配。模板应该启动时解析一次,复用。</p>'),
     ('文档', '<p>文档对管道的描述与第一节的实验一致:链式管道里每个命令的结果是下一个命令的最后一个参数。</p>')],
    steps,
    [ENV_G + '。每个例子是一个很小的模板加一份数据,输出由 Execute 得到(换行在输出中以 \\n 显示);成本用 testing.Benchmark,模板是一行带 range 的文本;读过的文档:go doc text/template 中关于管道的一段',
     '没有验证:template 与 define/block 的嵌套模板、自定义分隔符、并发执行同一个模板的安全性、html/template 的转义(下一篇)、模板函数的类型转换规则、大模板的解析成本'],
    'text/template')
