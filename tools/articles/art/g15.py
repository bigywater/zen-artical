from lib import *
S = SS('g15')
steps = [
    step("Dog 嵌入 Animal:d.Name 与 d.Animal.Name 都是 \"旺财\"(字段被提升);d.Rename(\"小黄\") 之后 d.Name = \"小黄\"(提升的指针接收者方法改的是嵌入的 Animal);Dog 自己定义了 Speak:d.Speak() = \"小黄 汪汪\",d.Animal.Speak() = \"小黄 发出声音\"(被遮蔽的方法仍可通过嵌入字段访问)。d.Intro() 是 Animal 的方法,里面调用 a.Speak(),得到 \"我是 小黄,我的声音:小黄 发出声音\"——没有调用 Dog 的 Speak,Go 的嵌入没有虚函数分派。", t=tl(S(1)), done=lidx(S(1), 'd.Name = ', 'Dog 自己定义了 Speak'), mark=lidx(S(1), 'd.Intro()'), kv=KV([['d.Name / d.Animal.Name', '同一个字段(提升)'], ['d.Speak()', 'Dog 自己的:\"小黄 汪汪\"'], ['d.Animal.Speak()', '被遮蔽的原方法仍可访问'], ['d.Intro()', '内部调用的是 Animal.Speak,不是 Dog.Speak']], ['d.Intro()'])),
    step("方法集:Animal 是 Intro、Speak,*Animal 是 Intro、Rename、Speak;Dog(嵌入 Animal 值)的方法集是 Intro、Speak,*Dog 是 Intro、Rename、Speak;Cat(嵌入 *Animal)的方法集 Intro、Rename、Speak,*Cat 也是 Intro、Rename、Speak。嵌入指针以后,值类型本身就有指针接收者的方法。", t=tl(S(2)), done=lidx(S(2), 'Animal 的方法集', 'Dog(嵌入 Animal)'), mark=lidx(S(2), 'Cat(嵌入 *Animal)'), kv=KV([['嵌入 T(Dog)', 'Dog:Intro、Speak;*Dog:加上 Rename'], ['嵌入 *T(Cat)', 'Cat 与 *Cat 都是 Intro、Rename、Speak']], ['嵌入 *T(Cat)'])),
    step("装饰器:countWriter 嵌入 io.Writer 并只改写 Write(累计字节数再转发):经它写 \"hello, world\" 与 \"!\",统计 n = 13,底层缓冲区是 \"hello, world!\"。嵌入的接口如果是 nil,调用被转发的方法会 panic:runtime error: invalid memory address or nil pointer dereference。", t=tl(S(3)), done=lidx(S(3), '统计 n = 13'), mark=lidx(S(3), 'nil 的嵌入接口'), kv=KV([['countWriter.Write', '累计 n = 13 后转发给底层 Writer'], ['底层缓冲区', '\"hello, world!\"'], ['嵌入的接口为 nil', 'panic:nil pointer dereference']], ['嵌入的接口为 nil'])),
    step("json.Marshal 把嵌入的 Inner 展开成顶层字段:{\"id\":7,\"note\":\"内层备注\",\"name\":\"名称\",\"outer_note\":\"外层备注\"}(Inner 与 Outer 各有 Note,json tag 不同所以并存)。reflect:Outer.Note 解析到 index [2](外层的),Outer.ID 解析到 index [0 0](提升自 Inner);Outer 有 3 个顶层字段(Inner、Name、Note),Inner 的 Anonymous = true。", t=tl(S(4)), done=lidx(S(4), 'json.Marshal'), mark=lidx(S(4), 'Outer.Note 解析到', 'reflect 报告'), kv=KV([['JSON 输出', '嵌入的 Inner 字段展开到顶层'], ['Outer.Note', 'index [2]:外层的'], ['Outer.ID', 'index [0 0]:提升自 Inner'], ['Inner 字段', 'Anonymous = true']], ['JSON 输出'])),
    step("编译器的报错:C 同时嵌入 A 与 B,二者都有 X,c.X 在同一深度有歧义:main.go:19:8: ambiguous selector c.X;Q 嵌入 P(值),Inc 是 *P 的方法:var i Incer = Q{} 报错 Q does not implement Incer (method Inc has pointer receiver)。", t=tl(S(5)), mark=lidx(S(5), 'ambiguous selector c.X', 'does not implement Incer'), kv=KV([['同一深度的同名字段', 'ambiguous selector c.X'], ['嵌入 P(值),接口要 Inc', 'Q does not implement Incer (method Inc has pointer receiver)']], ['同一深度的同名字段'])),
]
A = mkartg('g15', 15, 'Go,结构体嵌入,方法提升,接口,json,真实验证,动画演示',
    '用 Go 1.27.1 实测结构体嵌入:字段与方法被提升,外层定义同名方法会遮蔽(但嵌入类型里调用的仍是自己的方法,没有虚函数分派);嵌入 T 与嵌入 *T 的方法集不同;嵌入接口可以只改写一个方法做装饰器,嵌入的接口为 nil 调用会 panic;json 把嵌入结构体的字段展开;同深度同名字段是编译错误。',
    'Go 没有继承,嵌入是“组合 + 自动转发”。这篇用真实输出看清它到底做了什么:提升的字段与方法、遮蔽、嵌入指针与嵌入值的方法集、嵌入接口做装饰器、与 encoding/json 的交互,以及容易误以为有的“虚函数”其实没有。',
    [('没有虚函数', 'Animal.Intro 里调用的是 Animal.Speak,而不是外层 Dog.Speak'), ('T / *T', '嵌入 T 时 Dog 的方法集没有 Rename,嵌入 *T 时 Cat 就有'), ('13 字节', 'countWriter 只改写了 Write,统计到 \"hello, world!\" 的字节数')],
    [('提升与遮蔽', '<p>嵌入字段的字段与方法会被提升到外层,可以直接 <code>d.Name</code>、<code>d.Rename(...)</code>。外层定义同名方法时遮蔽被嵌入的那个,但嵌入的方法并没有消失,可以通过 <code>d.Animal.Speak()</code> 访问。更深的层级里同名会被更浅的遮蔽;同一深度的同名字段是歧义,编译器拒绝(第五节)。</p>'),
     ('不是继承', '<p>关键的一点:<code>Animal.Intro</code> 的接收者是 <code>Animal</code>,它里面的 <code>a.Speak()</code> 永远是 <code>Animal.Speak</code>,不会因为外面包了一层 <code>Dog</code> 就改调 <code>Dog.Speak</code>。要想让被嵌入类型的方法能调用到外层的“重写”,必须把外层的行为作为接口或函数字段传进去。</p>'),
     ('嵌入接口做装饰器', '<p>嵌入 <code>io.Writer</code> 的结构体自动拥有 <code>Write</code>,再改写一个方法就是一个装饰器,其余方法保持不变。风险是嵌入的接口没有初始化:调用被转发的方法会解引用 nil,panic。</p>'),
     ('与 encoding/json', '<p><code>encoding/json</code> 把匿名嵌入的结构体当作字段展开到外层;同名字段按层级与 tag 规则选择。reflect 里能看到嵌入字段的 <code>Anonymous</code> 为 true,以及 <code>FieldByName</code> 返回的是多层的下标路径。这里只展示了最简单的情形,同名字段冲突时的完整规则在 <code>encoding/json</code> 的文档里,我没有逐条验证。</p>'),
     ('两类编译错误', '<p>歧义选择器(同深度同名)与“值没有指针方法”的接口赋值,都是编译期就报错,不会拖到运行时。</p>')],
    steps,
    [ENV_G + '。方法集用 reflect.Type.Method 列出;JSON 输出是 encoding/json 的真实结果;编译错误是 go build 的原样输出',
     '没有验证:嵌入泛型类型、嵌入接口与方法重叠的细则(Go 1.14 起允许重叠方法集的接口嵌入,本文没有运行)、嵌入对内存布局与对齐的影响、encoding/json 在多层嵌入与 tag 冲突时的全部规则、序列化库(gob、xml)对嵌入的处理'],
    '结构体嵌入')
