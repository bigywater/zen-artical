from lib import *
S = SS('l61')
steps = [
    step("客户端只是落后(服务端多了 50 个提交,客户端没有任何本地提交):一轮就结束——一个 want(服务端的新 main)和第一批 have。但第一批并不是一个 have,而是 16 个:客户端沿着自己的历史一次发出 16 个已有的提交,服务端回 ACK 找到共同点,协商结束。fetch 之后 origin/main 有 1050 个提交,和服务端一致。", t=tl(S(1)), mark=lidx(S(1), '16 个', 'want 1 个'), done=lidx(S(1), 'origin/main 现在的提交数: 1050'), kv=KV([['want', '服务端的新末端 1 个'], ['have', '第一批 16 个'], ['轮数', '1 轮 fetch 命令']], ['have'])),
    step("客户端另有 500 个服务端不认识的本地提交(而且时间比服务端任何提交都新),服务端也有 50 个新提交。默认算法(fetch.negotiationAlgorithm 没设置,等于 consecutive)沿着本地历史一个个往前发 have,先把 500 个本地独有的提交都发一遍才碰到共同点:发出 1008 个 have、6 轮 fetch 命令,对象库增加 15 KB。skipping 跳着发,间隔越来越大:16 个 have、1 轮就找到了共同点,同样增加 15 KB。noop 一个 have 都不发(0 个、1 轮),服务端不知道客户端有什么,把想要的提交可达的所有对象都发过来:对象库增加 350 KB。", t=tl(S(2)), mark=lidx(S(2), '(未设置)', 'consecutive', 'skipping', 'noop'), done=lidx(S(2), '1008 个', '16 个'), b=bars([['默认(consecutive)', 1008, '1008 个 have,6 轮'], ['skipping', 16, '16 个 have,1 轮'], ['noop', 0, '0 个 have,多下载 350 KB']], 1008, mark=[0], done=[1, 2]), kv=KV([['consecutive(默认)', '沿着历史一个个发,本地独有的提交越多越慢'], ['skipping', '跳跃式,少量 have 就找到共同点'], ['noop', '不协商,可能多下载很多(partial clone 用)']], ['skipping'])),
    step("--negotiation-tip=origin/main:告诉 git 只从 origin/main 出发协商,而不是所有本地分支。本地有 500 个独有提交的分支 local 不再参与,客户端只发 16 个 have、1 轮 fetch 命令。适合分支很多、但只关心跟踪分支同步的场合。", t=tl(S(3)), mark=lidx(S(3), '--negotiation-tip=origin/main'), done=lidx(S(3), '16 个', '1 轮'), kv=KV([['--negotiation-tip', '指定协商的起点'], ['效果', '本地独有的提交不参与协商'], ['用途', '本地分支很多的大仓库']], ['--negotiation-tip'])),
    step("服务端只发缺的对象,并且尽量用 delta:一个 213 KB 的文件只改了一行并提交。fetch 时服务端打包的摘要是 Total 3 (delta 1)——3 个新对象(commit、tree、blob),其中 blob 是 delta。模拟服务端 git pack-objects --revs --thin --stdout:thin pack 只有 308 字节(可以引用客户端已有的 v1 blob 做基础);不用 thin(对象必须自包含)是 136,125 字节,与整个文件压缩后的 135,860 字节几乎一样。thin pack 让小改动的传输几乎是零成本。", t=tl(S(4)), mark=lidx(S(4), '308 字节', '136,125 字节'), done=lidx(S(4), 'Total 3 (delta 1)'), b=bars([['thin pack', 308, '308 字节'], ['非 thin(自包含)', 136125, '136,125 字节']], 136125, mark=[0], done=[1]), kv=KV([['thin pack', '可以对客户端已有的对象做 delta'], ['小改动', '308 字节 vs 136,125 字节'], ['客户端', '收到后补全(fix thin)']], ['thin pack'])),
]
A = mkarti('l61', 61, 'Git,fetch,协商,have,negotiation,thin pack,真实验证,动画演示',
    '实测 fetch 的协商:落后的客户端第一批发 16 个 have、1 轮;客户端有 500 个本地独有提交时默认的 consecutive 算法发 1008 个 have、6 轮,skipping 只要 16 个 have、1 轮,noop 一个都不发但多下载 350 KB;--negotiation-tip 限制协商起点;对 213 KB 文件改一行的 fetch,thin pack 只有 308 字节,非 thin 要 136,125 字节。',
    'git fetch 怎么知道只需要下载哪些对象?客户端的 have 要发多少个?本地分支多的时候协商会不会很慢?这篇在 1000 个提交的历史上实测 consecutive、skipping、noop 三种协商算法,以及 thin pack 如何让小改动几乎零传输。',
    [('1008 vs 16', '客户端有 500 个本地独有提交时,默认(consecutive)与 skipping 算法发出的 have 数'), ('350 KB', 'noop 算法不协商,对象库多增加的大小(其它算法只增加 15 KB)'), ('308 vs 136,125', '213 KB 文件改一行后,thin pack 与非 thin pack 的字节数')],
    [('have 和 want', '<p>客户端用 <code>want</code> 说想要什么,用 <code>have</code> 说已经有什么;服务端回 <code>ACK … common</code>,找到共同点就只打包缺的对象。纯落后的客户端第一批发 16 个 have,一轮就结束。</p>'),
     ('三种算法', '<p><code>fetch.negotiationAlgorithm</code>:默认(consecutive)沿着本地历史一个一个往前发 have,本地独有的提交越多越慢(500 个独有提交时发出 1008 个 have、6 轮);<code>skipping</code> 跳跃式发送,16 个 have、1 轮就找到共同点;<code>noop</code> 完全不发 have,适合 partial clone 等不需要协商的场景,代价是服务端不知道你有什么,会多发很多(本例多下载 350 KB)。</p>'),
     ('--negotiation-tip', '<p>限制协商只从指定的提交出发,本地的其它分支(哪怕有几百个独有提交)不参与,协商变成 16 个 have、1 轮。</p>'),
     ('thin pack', '<p>服务端发的 pack 可以是 thin 的——引用客户端已有的对象做 delta。对 213 KB 文件改一行,thin pack 只有 308 字节,自包含的 pack 要 136,125 字节。客户端收到后会把 thin pack 补全。</p>')],
    steps,
    [ENV_I_GIT + '。服务端是本机裸仓库(file://);协商用 GIT_TRACE_PACKET 数 have 与 command=fetch 的行数;本地独有的 500 个提交的时间比服务端任何提交都新(协商按时间从新到旧走,这样才会暴露 consecutive 的代价);thin pack 的字节数是手动调用 git pack-objects --thin 得到的模拟值,不是线上抓的包',
     '没有验证:真实网络上多轮协商的往返延迟;fetch.negotiationRestrict 与 negotiation 的其它调节项;push 时的协商(receive-pack 的 have 来自服务端);服务端 hook;分支数以万计时的 skipping 表现'],
    'fetch 的协商')
