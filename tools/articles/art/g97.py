from lib import *
S = SS('g97')
steps = [
    step("没有包参数的 go test(本地目录模式)根本不缓存:go test -run TestSlow -v(TestSlow 睡 1.5 秒)连续跑两次,每次都是 1.8s 和 1.616s,没有 (cached)。go help test 写着:本地目录模式下缓存被禁用。", t=tl(S(1)), mark=lidx(S(1), '第 1 次', '第 2 次'), kv=KV([['无包参数', '本地目录模式,不缓存'], ['有包参数(如 .)', '包列表模式,才缓存']], ['无包参数'])),
    step("带上包参数 .(包列表模式)连续跑:第 1 次 1.607s;第 2 次什么都没改 → (cached),go test 整体只用 0.10 秒;第 3 次加 -count=1 → 1.612s,重新运行。", t=tl(S(2)), done=lidx(S(2), '(cached)'), mark=lidx(S(2), '第 1 次', '-count=1'), b=bars([['第 1 次:go test 耗时 (s)', 1.79, '1.79'], ['第 2 次:(cached)', 0.10, '0.10'], ['第 3 次:-count=1', 1.77, '1.77']], 1.79, mark=[0, 2], done=[1]), kv=KV([['第 2 次', '(cached),0.10 秒'], ['-count=1', '强制重跑']], ['第 2 次'])),
    step("哪些改动会让缓存失效(被测函数 Add 标了 noinline,测试用 len(os.Args) 当输入)。基线 → 再跑一次 (cached);只在 Add 前加一行注释 → 重新运行(0.298s);把 a + b 改写成 b + a → 重新运行(0.327s);加了 if a == 0 分支 → 重新运行(1.104s);再跑一次 (cached)。加 -race(不同的测试二进制)→ 重新运行(1.329s),再跑一次 (cached)。-short、-v、-timeout=5m 这些缓存允许的标志:各自第 1 次重新运行,第 2 次 (cached);-count=2:两次都重新运行。", t=tl(S(3)), done=lidx(S(3), '再跑一次', ':第 2 次'), mark=lidx(S(3), '只改了注释之后', 'b + a', 'if a == 0', '加 -race(不同', '-count=2'), kv=KV([['源码有任何改变', '测试二进制变了(连注释导致的行号变化也算)→ 重跑'], ['-race', '另一个二进制,有自己的缓存'], ['-short / -v / -timeout', '各有各的缓存条目,第 2 次命中'], ['-count=2', '不允许缓存']], ['源码有任何改变'])),
    step("测试读环境变量:FOO=a → 运行;FOO=a 再跑 → (cached);FOO=b → 重新运行;FOO=a 同时另设一个测试没读的 OTHER=x → (cached)。缓存只关心测试实际读过的环境变量。", t=tl(S(4)), done=lidx(S(4), '再跑', 'OTHER=x'), mark=lidx(S(4), 'FOO=b'), kv=KV([['读过的变量变了', '重跑'], ['没读的变量变了', '仍然 (cached)']], ['读过的变量变了'])),
    step("测试读文件:读模块内的 data.txt(v1)→ 运行;再跑一次 (cached);把 data.txt 改成 v2 → 重新运行。读模块外的文件(o1)→ 运行;再跑一次 (cached);把模块外的文件改成 o2 → 仍然 (cached),输出还是 outside=\"o1\"——缓存给出了过期的结果。", t=tl(S(5)), done=lidx(S(5), 'data.txt 改成 v2', '读模块内的'), mark=lidx(S(5), '改成 o2'), kv=KV([['模块内的文件', '改了就重跑'], ['模块外的文件', '改了也还是 (cached),结果是旧的']], ['模块外的文件'])),
    step("测试依赖时间,缓存会让结果“冻住”:TestClock 打印当前秒数的个位。第 1 次是 8,1.2 秒之后再跑一次 → (cached),仍然是 8——时间已经过去了,但输出没变。", t=tl(S(6)), mark=lidx(S(6), '第 1 次', '1.2 秒之后再跑一次'), kv=KV([['第 1 次', '秒数个位 = 8'], ['1.2 秒后', '(cached),仍是 8'], ['含义', '缓存的是上次的输出']], ['含义'])),
    step("go clean -testcache 清空测试缓存:之后第 1 次 → 重新运行(秒数个位 = 9);第 2 次 → (cached)(仍是 9)。", t=tl(S(7)), mark=lidx(S(7), 'go clean -testcache'), done=lidx(S(7), '第 2 次'), kv=KV([['go clean -testcache', '清空'], ['之后', '第一次重新运行,第二次又命中']], ['go clean -testcache'])),
    step("go help test 的缓存规则:匹配缓存要求运行的是同一个测试二进制、命令行标志全部来自“可缓存”的集合(-benchtime、-coverprofile、-cpu、-failfast、-fullpath、-list、-outputdir、-parallel、-run、-short、-skip、-timeout 和 -v);出现集合外的标志就不缓存;显式禁用缓存的惯用写法是 -count=1;在模块内打开文件或读取环境变量的测试,只在这些文件和环境变量未变时才命中缓存;缓存的结果视为耗时为零,因此成功的包测试结果会被缓存并复用,无视 -timeout 的设置。", t=tl(S(8)), done=lidx(S(8), 'The rule for a match in the cache'), kv=KV([['可缓存标志', '-run -short -timeout -v 等'], ['禁用缓存', '-count=1'], ['文件/环境变量', '模块内的文件、读过的环境变量参与判断']], ['禁用缓存'])),
]
A = mkartg('g97', 97, 'Go,go test,测试缓存,count=1,go clean -testcache,真实验证,动画演示',
    '在 Go 1.27.1 里验证 go test 缓存:没有包参数的 go test 根本不缓存;go test . 第 2 次直接 (cached),-count=1 强制重跑;源码任何改动、-race 会换测试二进制;-short、-v、-timeout 有各自的缓存条目,-count=2 不缓存;只有读过的环境变量变化才失效;读模块内的文件会被跟踪,模块外的文件改了结果仍是旧的;依赖时间的测试结果会被冻住。',
    'go test 的缓存让重复运行几乎免费,但“(cached)”也会让人踩坑:改了外部文件的测试没有重跑,依赖时间的测试结果被冻住,甚至根本没触发缓存的命令也有。这篇逐条实测哪些情况会命中、哪些会失效,并对照 go help test 的规则。',
    [('0.10 秒', '命中缓存时 go test 的整体耗时(不命中时 TestSlow 要 1.79 秒)'), ('模块外', '读模块外的文件,改了内容缓存仍命中,输出还是旧的 "o1"'), ('无包参数', '没有包参数的 go test 根本不缓存')],
    [('先看有没有缓存', '<p>不带包参数的 <code>go test</code>(本地目录模式)根本不缓存;带上 <code>.</code> 或 <code>./...</code>(包列表模式)才有缓存。我一开始就是用的无包参数的写法,怎么跑都没有 (cached),查了 <code>go help test</code> 才明白。</p>'),
     ('命中与强制重跑', '<p>什么都不改:(cached),整体只要 0.10 秒(不命中时这个 1.5 秒的测试要 1.79 秒);<code>-count=1</code> 强制重跑。</p>'),
     ('什么会让它失效', '<p>测试二进制变了就失效——连只在函数前加一行注释也会(行号信息变了);<code>-race</code> 是另一个二进制,有自己的缓存;<code>-short</code>、<code>-v</code>、<code>-timeout</code> 各有各的缓存条目,第一次运行、第二次命中;<code>-count=2</code> 不允许缓存,两次都重跑。</p>'),
     ('环境变量', '<p>只有测试真的读过的环境变量变了才失效:<code>FOO</code> 从 a 变 b 就重跑,多设一个没被读的 <code>OTHER</code> 仍然命中。</p>'),
     ('文件', '<p>读模块内的 <code>data.txt</code>,改了内容就重跑;读模块外的文件,内容从 o1 改成 o2,缓存仍然命中,打印的还是 <code>outside="o1"</code>——过期的结果。</p>'),
     ('时间', '<p>依赖当前时间的测试,1.2 秒后再跑,命中缓存,打印的秒数还是旧的:缓存的是上一次的输出。</p>'),
     ('清缓存', '<p><code>go clean -testcache</code> 清空所有测试缓存,之后第一次重跑,第二次又命中。</p>'),
     ('规则原文', '<p><code>go help test</code> 列出了 13 个可缓存标志,说明缓存的结果视为耗时为零,所以成功的结果会无视 <code>-timeout</code> 被复用;显式禁用缓存的惯用写法是 <code>-count=1</code>。</p>')],
    steps,
    [ENV_G + '。实验里的测试包是自己写的(Add 标了 noinline,用 len(os.Args) 当输入避免被折叠);每次实验开始前先 go clean -testcache;所有命令在模块里用 go test -run … .(包列表模式)运行;读过的文档:go help test',
     '没有验证:-coverprofile 与缓存的关系、-bench 的缓存、go vet 一起运行时的缓存、GOFLAGS 里设置 -count 的影响、远程缓存(GOCACHEPROG)、Linux 上的差异'],
    'go test 缓存')
