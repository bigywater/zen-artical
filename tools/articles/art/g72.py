from lib import *
S = SS('g72')
steps = [
    step("多个 case 同时就绪时 select 怎么选:两个 channel 总是同时就绪,select 100 万次:选中第一个 499725 次,第二个 500275 次(50.0% / 50.0%)——均匀随机。", t=tl(S(1)), mark=lidx(S(1), '499725'), b=bars([['第一个被选中', 499725, '499725'], ['第二个被选中', 500275, '500275']], 500275, done=[0, 1]), kv=KV([['第一个', '499725 次(50.0%)'], ['第二个', '500275 次(50.0%)'], ['含义', '源码顺序不是优先级']], ['含义'])),
    step("想要优先级怎么办:高、低优先级 channel 总是同时就绪,各 100 万次:普通 select 选中低优先级 499630 次(约一半);先单独试高优先级、再兜底的嵌套 select(外层 select 带 default,里面再 select 两个)选中低优先级 0 次。", t=tl(S(2)), done=lidx(S(2), '嵌套 select'), mark=lidx(S(2), '普通 select'), b=bars([['普通 select 选中低优先级', 499630, '499630'], ['嵌套 select', 0, '0']], 499630, mark=[0], done=[1]), kv=KV([['普通 select', '低优先级被选中约 50%'], ['嵌套 select', '0 次'], ['写法', '先单独 select 高优先级(带 default),再兜底']], ['写法'])),
    step("结果和超时撞车:定时器已经到期、结果也已放进 channel,两者同时就绪,10 万次:选中“结果” 50017 次,选中“超时” 49983 次。也就是说这种情形下,是否报告超时是抛硬币。", t=tl(S(3)), mark=lidx(S(3), '50017'), b=bars([['选中结果', 50017, '50017'], ['选中超时', 49983, '49983']], 50017, done=[0], mark=[1]), kv=KV([['结果', '50017 次'], ['超时', '49983 次'], ['含义', '边界上谁先被报告没有保证']], ['含义'])),
    step("已关闭的 channel 在 select 里一直就绪:a 很快关闭,b 要 200 ms 后才有数据。关闭后不处理,select 一直选中已关闭的 a,循环了 3000001 次(我在 300 万次时人为中断),CPU 时间 0.115 秒;关闭后把 a 置为 nil:循环了 12 次,CPU 时间 0.000 秒——nil channel 永远不会就绪,这个 case 被禁用了。", t=tl(S(4)), done=lidx(S(4), '置为 nil'), mark=lidx(S(4), '不处理'), b=bars([['不处理:循环次数', 3000001, '3000001'], ['置为 nil:循环次数', 12, '12']], 3000001, mark=[0], done=[1]), kv=KV([['不处理', '空转 300 万次(被我中断),CPU 0.115 s'], ['置为 nil', '12 次,CPU 0.000 s']], ['置为 nil'])),
    step("select + default 的忙等待 300 ms:循环 8167784 次,CPU 时间 0.300 秒(整个 300 ms 都在占 CPU);阻塞的 <-ch 等 300 ms:CPU 时间 0.000 秒。", t=tl(S(5)), mark=lidx(S(5), 'select + default'), done=lidx(S(5), '阻塞的 <-ch'), b=bars([['忙等待 CPU (ms)', 300, '300'], ['阻塞等待 CPU', 0, '0']], 300, mark=[0], done=[1]), kv=KV([['忙等待', '300 ms 占满一个核'], ['阻塞', '0 CPU']], ['忙等待'])),
    step("语言规范原文:If one or more of the communications can proceed, a single one that can proceed is chosen via a uniform pseudo-random selection. Otherwise, if there is a default case, that case is chosen. 以及:Since communication on nil channels can never proceed, a select with only nil channels and no default case blocks forever.", t=tl(S(6)), done=lidx(S(6), 'uniform pseudo-random selection'), mark=lidx(S(6), 'nil channels can never proceed'), kv=KV([['多个就绪', '均匀伪随机选一个'], ['都不就绪', '有 default 走 default,否则阻塞'], ['nil channel', '永远不就绪']], ['nil channel'])),
]
A = mkartg('g72', 72, 'Go,select,超时,优先级,nil channel,真实验证,动画演示',
    '在 Go 1.27.1 里实测 select:两个 channel 都就绪时 100 万次选择 50.0%/50.0%;普通 select 会让低优先级被选中约一半,嵌套 select 为 0;结果和超时同时就绪时 10 万次里结果 50017 次、超时 49983 次;已关闭的 channel 不置 nil 会空转,置为 nil 后只循环 12 次;select+default 忙等待占满 CPU。',
    'select 的几条规则决定了很多并发代码的行为:多个就绪时随机选、已关闭的 channel 一直就绪、nil channel 永远阻塞。这篇逐条用实验验证,并给出实现优先级和动态禁用 case 的写法。',
    [('50.0% / 50.0%', '两个 channel 总是同时就绪时,select 选中各自的比例'), ('0 次', '嵌套 select 让高优先级先走时,低优先级被选中的次数(普通 select 约一半)'), ('12 次', '已关闭的 channel 置为 nil 后,合并循环的迭代次数(不置 nil 空转 300 万次)')],
    [('就绪时是随机选', '<p>两个 channel 同时就绪,100 万次 select 里各被选中约一半。写在前面的 case 没有优先权,规范说是均匀伪随机选一个。</p>'),
     ('优先级要自己写', '<p>想让高优先级先走,先单独做一次带 <code>default</code> 的 select 试高优先级,没有再进入同时等两个的 select。实验里这个写法让低优先级一次都没被选中;普通 select 则选中了约一半。副作用是低优先级可能饿死。</p>'),
     ('超时撞车', '<p>结果和超时同时就绪时,谁被选中是抛硬币(10 万次里 50017 对 49983)。如果业务上“结果到了就算成功”,要在超时分支里再检查一次结果 channel。</p>'),
     ('关闭的 channel 与 nil', '<p>已关闭的 channel 一直就绪(读到零值和 ok=false)。合并循环里不处理它,会一直空转(我在 300 万次时中断,CPU 0.115 秒);把变量置为 <code>nil</code> 后这个 case 永远不就绪,循环只走了 12 次。</p>'),
     ('忙等待', '<p>select 加 <code>default</code> 的循环 300 ms 占满一个核(CPU 0.300 秒),而阻塞等待是 0。只有真的需要“不阻塞地试一下”才用 <code>default</code>。</p>'),
     ('规范怎么说', '<p>两条规则都在语言规范里:多个就绪均匀随机选一个;只含 nil channel 又没有 default 的 select 永远阻塞。</p>')],
    steps,
    [ENV_G + '。每个实验是单独的小程序;公平性、优先级各 100 万次,撞车 10 万次;CPU 时间由 syscall.Getrusage 读自己;不处理已关闭 channel 的那次在 300 万次迭代时被代码中断;规范引用来自本机 $GOROOT/doc/go_spec.html,确认原文存在',
     '没有验证:select 随机选择的具体算法(没有读运行时源码)、case 很多时的开销、select 与 context 超时的组合代价(参见 time.After 的另一篇)、发送 case 的随机性、不同 GOMAXPROCS 下的差别'],
    'select 的行为')
