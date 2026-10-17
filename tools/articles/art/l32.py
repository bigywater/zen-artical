from lib import *
S = SS('l32')
steps = [
    step("racy 的定义:index 条目里的 mtime ≥ index 文件自己的修改时间。含义:这个文件有可能是在 index 写出之后又被改过,而 mtime 恰好没变,所以 stat 一致不能保证内容没变。正常情况 a):文件是 60 秒前写的,mtime 早于 index 写出的时刻(文件早于 index:True)。racy 情况 b):用 os.utime 把文件 mtime 设到 60 秒后(模拟时钟不同步、解压出来的文件),文件 mtime 比 index 文件的修改时间还晚(文件早于 index:False)。两种情况 index 里记的 size 都是 6,和文件真实大小一致。", t=tl(S(1)), mark=lidx(S(1), 'b) racy', '文件早于 index: False'), done=lidx(S(1), 'a) 正常情况', '文件早于 index: True'), kv=KV([['racy', '条目 mtime ≥ index 文件的 mtime'], ['原因', 'index 写出之后文件可能又被改过'], ['后果', 'stat 一致也不可信,要比较内容']], ['racy'])),
    step("同一个“原地改写 + 恢复 mtime”(core.trustctime=false、core.checkStat=minimal,只比 mtime 和 size)。非 racy 的 a):git status --short 输出 A  a.txt,没有 M,看不出内容已经变了(工作区 blob e427984d 与 index blob ce013625 不同);racy 的 b):输出 AM a.txt,多出的 M 就是被发现的改动。git 对 racy 条目不信任 stat,直接比较内容,所以这种“恢复 mtime”的伪装对 racy 条目无效。", t=tl(S(2)), mark=lidx(S(2), 'AM a.txt'), done=lidx(S(2), 'a) 非 racy', 'b) racy'), kv=KV([['非 racy', 'stat 一致 → 认为没改'], ['racy', '不信 stat,比较内容 → 发现 M'], ['代价', '每次都要重读文件']], ['racy'])),
    step("racy 什么时候解除:1 万个文件,mtime 设在 20 秒之后(建仓库的 add 和 commit 就花了 8 秒,离 mtime 还剩 12 秒)。mtime 还没到时,git status 3 次都是约 209 ms(每次都重读内容);mtime 刚过去 0.3 秒之后,三次仍是 291 ms、210 ms、206 ms;mtime 过去 3 秒之后,第一次 git status 246 ms(重读内容并重写 index),之后降到 32 ms、30 ms、29 ms。刚过 0.3 秒时仍然 racy,说明比较的粒度不是纳秒,而是大约 1 秒。", t=tl(S(3)), mark=lidx(S(3), '246 ms', 'mtime 刚过去 0.3 秒'), done=lidx(S(3), 'mtime 还没到', '32 ms'), b=bars([['mtime 还没到', 209, '209 ms'], ['刚过 0.3 秒', 210, '210 ms'], ['过 3 秒后第一次', 246, '246 ms(重写 index)'], ['过 3 秒后第二次', 30, '30 ms']], 246, mark=[2], done=[0, 1, 3]), kv=KV([['mtime 到点前后', '一直 racy,每次重读内容'], ['过几秒之后', '第一次 status 重写 index,下一次快'], ['粒度', '约 1 秒,不是纳秒']], ['粒度'])),
    step("racy 的代价:1 万个文件,mtime 在 60 秒前(正常)时,git status 连续 5 次是 60 ms、30 ms、29 ms、29 ms、30 ms(第一次稍慢是缓存刚失效);mtime 在 2 分钟后(racy)时,5 次是 209 ms、207 ms、206 ms、207 ms、207 ms——每次都重读 1 万个文件的内容,约慢 7 倍,而且永远不会自己变快,直到时间追上文件的 mtime。", t=tl(S(4)), mark=lidx(S(4), '文件 mtime 在 2 分钟后'), done=lidx(S(4), '文件 mtime 在过去'), b=bars([['mtime 在过去:第 5 次', 30, '30 ms'], ['mtime 在 2 分钟后:第 5 次', 207, '207 ms']], 207, mark=[1], done=[0]), kv=KV([['正常', '约 30 ms'], ['racy', '约 207 ms,每次都慢'], ['常见原因', '时钟不同步、网络文件系统、解压出的未来时间戳']], ['常见原因'])),
]
A = mkarti('l32', 32, 'Git,racy git,index,mtime,git status,真实验证,动画演示',
    '验证 racy git:index 条目的 mtime ≥ index 文件的修改时间时,stat 一致不可信,git 会比较内容——同样“原地改写并恢复 mtime”的伪装,非 racy 条目看不出(A),racy 条目被发现(AM);racy 的粒度约为 1 秒;文件 mtime 在未来时,1 万个文件的 git status 每次 207 ms,正常只要 30 ms。',
    'git 靠 stat 判断文件有没有改,但如果文件恰好在 index 写出的同一时刻被改,mtime 一样怎么办?这是 racy git 问题。这篇用把 mtime 设到未来的办法造出 racy 条目,验证 git 不信任它们、改而比较内容,以及 racy 什么时候解除、代价有多大。',
    [('AM vs A', '同样的伪装改写,racy 条目的 git status 多出 M(被发现),非 racy 的没有'), ('≈ 1 秒', 'racy 判断的粒度:mtime 刚过去 0.3 秒,git status 仍然每次重读内容'), ('207 vs 30 ms', '1 万个文件,mtime 在 2 分钟后(racy)与在过去(正常)时 git status 的耗时')],
    [('问题', '<p>stat 缓存假设“文件内容变了,mtime(或 size、ctime)一定会变”。但如果文件在 index 写出的同一时刻之后被改,而 mtime 的精度又不足以区分,就会漏掉改动。这叫 racily clean。</p>'),
     ('判断', '<p>git 的办法:index 条目里的 mtime 不早于 index 文件自己的修改时间时,这个条目就是 racy,不再信任 stat,直接比较文件内容。所以哪怕伪装了 mtime 和 size,racy 条目里的改动也会被发现。</p>'),
     ('解除', '<p>等 index 文件的修改时间越过文件的 mtime(粒度约 1 秒),下一次 <code>git status</code> 重写 index 后条目不再 racy,之后又走快速路径。本例里 mtime 刚过去 0.3 秒仍然 racy,过去 3 秒后第一次 status 之后恢复。</p>'),
     ('代价', '<p>racy 的条目每次都要读文件内容。文件 mtime 在未来(时钟不同步、网络文件系统、压缩包里带未来时间戳)时,1 万个文件的 git status 要 207 ms,正常只要 30 ms,而且在 mtime 到点之前不会好转。</p>')],
    steps,
    [ENV_I_GIT + '。racy 条目用 os.utime 把 mtime 设到未来来造;“恢复 mtime 的原地改写”沿用上一篇的方法;耗时每组连续运行几次,含进程启动;本机 git 的 racy 比较粒度是从行为推断的(0.3 秒后仍 racy),没有读源码',
     '没有验证:git 在写出 index 时把 racy 条目的 size 记成 0(“smudge”)的传统机制——我在这台机器的 git 上没有观察到 index 里的 size 被改成 0,所以这里只描述了读取时的比较行为;Linux 上 mtime 精度为纳秒时 racy 判断的粒度;fsmonitor 打开时 racy 的处理;网络文件系统的情形'],
    'racy git')
