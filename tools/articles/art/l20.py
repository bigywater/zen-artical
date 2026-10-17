from lib import *
S = SS('l20')
steps = [
    step("默认配置下(全局配置里不含 gc.auto,用 git 自己的默认值)git config --get gc.auto 没有输出,所以用默认值 6700。git gc --auto 并不数全部松散对象,只数 .git/objects/17 这一个目录里的文件,和 (6700 + 255) // 256 = 27 比较:超过 27 个才触发。用一个目录的数量乘 256 来估计总数。", t=tl(S(1)), mark=lidx(S(1), '(6700 + 255) // 256 = 27'), done=lidx(S(1), 'gc.auto 未设置'), kv=KV([['gc.auto', '默认 6700'], ['阈值', '(6700+255)//256 = 27'], ['怎么数', '只看 objects/17 这一个目录']], ['怎么数'])),
    step("往 objects/17 里放(不可达的)松散对象:26 个时 git gc --auto 没有输出;27 个时仍然没有输出;28 个时输出 Auto packing the repository for optimum performance,并警告 too many unreachable loose objects。27 不触发、28 触发,恰好是“超过 27”。", t=tl(S(2)), mark=lidx(S(2), 'objects/17 里 28 个'), done=lidx(S(2), 'objects/17 里 26 个', 'objects/17 里 27 个'), b=bars([['26 个', 26, '没有触发'], ['27 个', 27, '没有触发'], ['28 个', 28, '触发']], 28, mark=[2], done=[0, 1]), kv=KV([['≤ 27', 'gc --auto 什么也不做'], ['≥ 28', '开始自动打包'], ['依据', '只数 objects/17']], ['依据'])),
    step("随机分布的松散对象,每行一个新仓库:5,000 个时 objects/17 里 14 个,没触发;6,000 个时 27 个,没触发(恰好卡在阈值);6,500 个时 33 个,触发;6,700 个时只有 17 个,没触发;7,000 个时 32 个,触发;7,500 个时 35 个、8,000 个时 29 个都触发。因为只用一个目录估计总数,有随机误差——精确的 6,700 个对象反而没有触发,6,500 个却触发了。", t=tl(S(3)), mark=lidx(S(3), '6,700', '6,500'), done=lidx(S(3), '5,000', '6,000', '7,000', '7,500', '8,000'), b=bars([['5,000 个对象', 14, 'objects/17: 14,不触发'], ['6,000 个', 27, '27,不触发'], ['6,500 个', 33, '33,触发'], ['6,700 个', 17, '17,不触发'], ['7,000 个', 32, '32,触发'], ['8,000 个', 29, '29,触发']], 35, mark=[3], done=[0, 1, 2, 4, 5]), kv=KV([['估计方法', 'objects/17 的数量 × 256'], ['误差', '6,700 个对象时只有 17 个(期望约 26)'], ['含义', '触发点是个大概的数,不是精确的 6700']], ['误差'])),
    step("触发之后不可达的松散对象仍在:第一次 gc --auto 之后 objects/17 里还有 28 个,再执行两次 git gc --auto,每次都输出 Auto packing the repository…、Nothing new to pack. 和 warning: There are too many unreachable loose objects; run 'git prune' to remove them.,两次之后仍是 28 个。这些对象不可达,gc 的打包碰不到它们,下次自动 gc 还是会触发(这里为了观察设了 gc.autoDetach=false,同步运行)。", t=tl(S(4)), mark=lidx(S(4), 'Nothing new to pack', 'warning: There are too many'), done=lidx(S(4), '第一次触发之后', '两次之后'), kv=KV([['不可达的松散对象', 'gc 打包不会处理它们'], ['结果', '每次 gc --auto 仍然触发,仍然警告'], ['处理', 'git prune 或等对象过期(见 prune 一篇)']], ['结果'])),
    step("另一个触发条件:pack 数超过 gc.autoPackLimit(默认 50)。50 个 pack 时 git gc --auto 没有输出,pack 数仍是 50;再多一个变成 51 个 pack,git gc --auto 输出 Auto packing…,打包后只剩 1 个 pack。", t=tl(S(5)), mark=lidx(S(5), '再多一个', 'pack 数 1'), done=lidx(S(5), '现在有 50 个 pack', 'git gc --auto → (没有输出)'), b=bars([['50 个 pack', 50, '不触发'], ['51 个 pack', 51, '触发,合并成 1 个']], 51, mark=[1], done=[0]), kv=KV([['gc.autoPackLimit', '默认 50'], ['> 50 个 pack', '触发整理'], ['结果', '合并成 1 个']], ['gc.autoPackLimit'])),
]
A = mkarti('l20', 20, 'Git,gc,gc.auto,松散对象,autoPackLimit,真实验证,动画演示',
    '在真实仓库里验证 git gc --auto 的触发条件:默认 gc.auto=6700,只数 objects/17 一个目录并与 27 比较,27 个不触发、28 个触发;随机分布的 6,700 个对象因为 objects/17 里只有 17 个而没触发,6,500 个却触发了;不可达的松散对象不会被清掉,下次仍触发;pack 数超过 50 也触发。',
    '松散对象多到多少才会自动 gc?文档说 6700,但 git 并不真的数 6700 个。这篇用精确构造的 26、27、28 个对象和随机分布的几千个对象,把触发点测出来,再看 gc 之后还会不会再触发,以及 pack 数量这个另一条触发条件。',
    [('28', 'objects/17 里松散对象达到 28 个(超过 27)才触发 git gc --auto'), ('6,700 不触发', '随机分布的 6,700 个松散对象,objects/17 里只有 17 个,没有触发;6,500 个反而触发了'), ('51', 'pack 数超过 gc.autoPackLimit(50)也会触发,打包后合并成 1 个')],
    [('怎么数', '<p><code>git gc --auto</code> 不去数全部松散对象——那太贵。它只数 <code>.git/objects/17</code> 一个目录里的文件,和 <code>(gc.auto + 255) / 256</code> 比较,默认 gc.auto 是 6700,阈值 27,超过才触发。因为对象 hash 均匀分布,一个目录约占 1/256。</p>'),
     ('精确的边界', '<p>人为往 objects/17 里放 26、27、28 个对象:27 个仍不触发,28 个触发。这证实了是“超过 27”。</p>'),
     ('估计有误差', '<p>随机分布的对象让 objects/17 的个数上下波动:6,000 个对象时 27 个(没触发),6,700 个时只有 17 个(没触发),6,500 个时 33 个(触发)。所以“松散对象 6700 个触发”只是个大概的数。</p>'),
     ('触发之后', '<p>自动 gc 会打包可达对象,但<b>不可达</b>的松散对象不满过期时间是不会被清理的,于是 objects/17 里的数量不变,下一次 <code>gc --auto</code> 又会触发并警告 <code>too many unreachable loose objects</code>。要清理它们得 <code>git prune</code> 或等它们过期。</p>'),
     ('pack 数', '<p>另一个条件是 pack 数量:超过 <code>gc.autoPackLimit</code>(默认 50)就会触发,把它们合并成一个。</p>')],
    steps,
    [ENV_I_GIT + '。这一篇的实验用一份不含 gc.auto 与 maintenance.auto 的全局配置,以便用 git 的默认值;为了观察输出,gc --auto 以 -c gc.autoDetach=false 同步运行;松散对象用 git hash-object -w --stdin-paths 写入(不可达);“objects/17 里 28 个”是用 SHA-1 前缀为 17 的内容构造的',
     '没有验证:默认 autoDetach 时在后台运行及 gc.log 的写入与 1 天内不再重试的行为;gc.auto 设为其它值时阈值的变化(只验证了默认值);git commit 之后触发 maintenance run --auto 的完整流程(见后面 maintenance 一篇);gc.autoPackLimit 设为其它值;Windows 上的行为'],
    'gc.auto 阈值')
