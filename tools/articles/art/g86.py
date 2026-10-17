from lib import *
S = SS('g86')
steps = [
    step("经典的灾难性模式 ^(a+)+$,输入是 n 个 a 加一个 b(不匹配)。Go regexp:1000 个 a 0.1 ms,1 万个 0.4 ms,10 万个 4.2 ms,100 万个 38.0 ms(输入长 10 倍,耗时约长 10 倍)。同一个模式、同样的输入,Python 3 的 re(回溯引擎):20 个 a 35 ms,24 个 549 ms,26 个 2193 ms,28 个 8919 ms,30 个超过 20 秒被我中断(每多 2 个字符约慢 4 倍)。", t=tl(S(1)), done=lidx(S(1), '1000000 个 a', '100000 个 a'), mark=lidx(S(1), 'Python re `^(a+)+$` 匹配 28', 'Python re `^(a+)+$` 匹配 30', 'Python re `^(a+)+$` 匹配 26'), b=bars([['Go:100 万个 a (ms)', 38.0, '38'], ['Python:24 个 a', 549, '549'], ['Python:26 个 a', 2193, '2193'], ['Python:28 个 a', 8919, '8919']], 8919, done=[0], mark=[1, 2, 3]), kv=KV([['Go', '线性:100 万字符 38 ms'], ['Python re', '指数:28 个字符 8.9 秒,30 个 >20 秒'], ['输入规模', 'Go 的输入大 3.5 万倍']], ['Python re'])),
    step("Go 不支持的语法:反向引用 (a)\\1 → invalid escape sequence: `\\1`;正向先行 (?=a)b 和负向先行 (?!a)b → invalid or unsupported Perl syntax;后行断言 (?<=a)b → invalid named capture;占有量词 a++ → invalid nested repetition operator: `++`;重复次数上限:\\d{1,1001} → invalid repeat count: `{1,1001}`;(?i) 这样的标志可以。", t=tl(S(2)), mark=lidx(S(2), '\\1', '(?=a)b', '(?!a)b', '(?<=a)b', 'a++', '{1,1001}'), done=lidx(S(2), '(?i)abc'), kv=KV([['不支持', '反向引用、先行/后行断言、占有量词'], ['重复上限', '1000'], ['支持', '(?i) 等标志']], ['不支持'])),
    step("最左优先 vs 最左最长:`a|ab` 在 \"ab\" 里,默认(Perl 风格最左优先)匹配 \"a\";调用 Longest()(POSIX 最左最长)匹配 \"ab\";MustCompilePOSIX 也匹配 \"ab\"。", t=tl(S(3)), mark=lidx(S(3), '默认', 'Longest()', 'MustCompilePOSIX'), kv=KV([['默认', 'a|ab → \"a\"(先写的分支优先)'], ['Longest / POSIX', 'a|ab → \"ab\"']], ['默认'])),
    step("成本:在 63000 字节文本的开头附近命中,re.MatchString 172 ns/次,strings.Contains 7 ns/次。regexp.MustCompile 一次 1149 ns/次(21 次分配);每次都用 regexp.MatchString(内部再编译)1118 ns/次;预编译后对短串 re.MatchString 68 ns/次。", t=tl(S(4)), mark=lidx(S(4), 're.MatchString 172', 'regexp.MustCompile 一次'), b=bars([['strings.Contains (ns)', 7, '7'], ['预编译 re.MatchString(短串)', 68, '68'], ['re.MatchString(63 KB 文本)', 172, '172'], ['每次编译 + 匹配', 1118, '1118']], 1118, done=[0, 1, 2], mark=[3]), kv=KV([['Contains', '7 ns'], ['预编译 + 短串', '68 ns'], ['每次编译', '1118 ns,比预编译慢约 16 倍']], ['每次编译'])),
    step("源码与文档:backtrack.go 的注释——backtrack 是针对小正则和小文本的、带子匹配跟踪的搜索,它分配一个 (输入长度)×(程序长度) 位的位向量,保证不会重复探索同一个 (字符位置, 指令) 状态,因此搜索时间与文本长度成线性关系;它是 onepass 不可用时,对小正则的 NFA 代码的快速替代。go doc regexp:该实现保证运行时间与输入大小成线性关系(这是多数开源正则实现不保证的属性)。", t=tl(S(5)), done=lidx(S(5), 'backtrack.go', 'bit vector'), mark=lidx(S(5), 'guaranteed to run in time linear'), kv=KV([['保证', '运行时间与输入大小线性'], ['backtrack 引擎', '位向量记录已访问的状态,不重复探索'], ['代价', '不能支持反向引用等']], ['代价'])),
]
A = mkartg('g86', 86, 'Go,regexp,RE2,线性时间,回溯,真实验证,动画演示',
    '在 Go 1.27.1 里验证 regexp 的线性时间保证:灾难性模式 ^(a+)+$ 在 100 万个字符的输入上只要 38.0 ms,而同一个模式在 Python 3 的 re 里 28 个字符就要 8919 ms、30 个字符超过 20 秒;Go 不支持反向引用、先行/后行断言和占有量词;默认最左优先而不是最左最长;预编译比每次编译快约 16 倍。',
    'Go 标准库的 regexp 不支持反向引用和断言,这是个常被抱怨的限制。它换来的是一个保证:匹配时间与输入长度成线性关系,不会被恶意输入拖垮(ReDoS)。这篇用同一个灾难性模式在 Go 和 Python 上各跑一遍,把这个代价与收益都摆出来。',
    [('38.0 ms', 'Go 用 ^(a+)+$ 匹配 100 万个 a 加一个 b 的耗时'), ('8919 ms', 'Python re 匹配 28 个 a 加一个 b 的耗时,30 个超过 20 秒'), ('1118 vs 68 ns', '每次都编译再匹配与预编译后匹配的耗时')],
    [('线性 vs 指数', '<p>Go 的耗时随输入线性增长:1000 个字符 0.1 ms,100 万个 38.0 ms。回溯引擎(Python 的 re)在同一个模式上每多 2 个字符约慢 4 倍:24 个字符 549 ms,28 个 8919 ms。这就是 ReDoS:攻击者用几十个字符就能耗尽一个线程。Python 的结果只代表这个版本的 re,别的回溯引擎(如 PCRE、Java)的数字不同,但指数增长的形状相似,我没有测。</p>'),
     ('付出的代价', '<p>不支持反向引用 <code>\\1</code>、先行 <code>(?=…)</code>/<code>(?!…)</code>、后行断言和占有量词 <code>a++</code>,重复次数上限是 1000;这些在编译时就会报错,不会静默地降级。</p>'),
     ('匹配语义', '<p>默认是 Perl 风格的最左优先:<code>a|ab</code> 匹配 "ab" 得到 "a"。需要 POSIX 的最左最长就用 <code>Longest()</code> 或 <code>CompilePOSIX</code>,得到 "ab"。</p>'),
     ('性能与用法', '<p>预编译的短串匹配 68 ns,每次都 <code>regexp.MatchString</code>(内部再编译)1118 ns,要预编译并复用。简单的子串查找,<code>strings.Contains</code> 7 ns 比 regexp 快得多,不需要正则就别用。</p>'),
     ('为什么能保证线性', '<p>源码里的 <code>backtrack.go</code> 注释说明了它的做法:用位向量记住已经探索过的 (位置, 指令) 状态,不重复探索,所以时间与文本长度线性相关;文档也明确写了“保证与输入大小成线性”。这里我没有读 NFA 与 onepass 引擎的细节。</p>')],
    steps,
    [ENV_G + '。Python 为本机的 Python 3.14 的 re 模块,每次最多等 20 秒(用 SIGALRM 中断);Go 的耗时是单次测量;预编译对比用 testing.Benchmark;读过的源码与文档:src/regexp/backtrack.go 开头注释,go doc regexp',
     '没有验证:其它回溯引擎(PCRE、Java、.NET)的具体数字、onepass 与 NFA 引擎的选择条件、Go 正则在大模式(很多分支)下的内存、regexp/syntax 的解析细节、带捕获组数量很多时的线性常数'],
    'regexp 与 RE2')
