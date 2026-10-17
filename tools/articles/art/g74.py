from lib import *
S = SS('g74')
steps = [
    step("time.Now() 带着单调时钟读数:t.String() 的结尾是 m=+0.000114459(进程启动以来的单调时间);同一个值 Round(0) 之后完整输出是 2026-10-10 13:55:29.982922 +0800 CST,没有 m=;之前是 2026-10-10 13:55:29.982922 +0800 CST m=+0.000114459。", t=tl(S(1)), done=lidx(S(1), 'Round(0) 之后'), mark=lidx(S(1), 'm=+0.000114459', 'Round(0) 之前'), kv=KV([['time.Now()', '带 m=+…(单调读数)'], ['Round(0)', '去掉 m=,墙钟时间不变']], ['Round(0)'])),
    step("哪些操作会去掉单调读数:time.Now() 和 t.Add(time.Hour) 保留(有 m=);t.AddDate、t.Round(time.Second)、t.Truncate(time.Second)、t.Round(0)、t.UTC()、t.Local()、t.In(time.UTC) 都去掉(无 m=);time.Unix(…)、time.Date(…) 构造出来的本来就没有。", t=tl(S(2)), done=lidx(S(2), 'time.Now():有 m=', 't.Add(time.Hour):有 m='), mark=lidx(S(2), '无 m='), b=bars([['保留单调读数的操作', 2, '2 个'], ['去掉的操作', 9, '9 个']], 9, done=[0], mark=[1]), kv=KV([['保留', 'time.Now()、t.Add'], ['去掉', 'AddDate/Round/Truncate/UTC/Local/In 等'], ['构造函数', 'Date、Unix 本来就没有']], ['保留'])),
    step("== 与 Equal 不一样:t == t.Round(0) 是 false,t.Equal(t.Round(0)) 是 true。经过 JSON 序列化再反序列化:t == u 是 false,t.Equal(u) 是 true,t.Sub(u) = 0s。用 time.Time 当 map 的 key:用 t 查得到,用 t.Round(0) 查不到(同一个时刻!)。同一时刻、不同时区的 d == l 是 false,d.Equal(l) 是 true。", t=tl(S(3)), done=lidx(S(3), 'Equal(t.Round(0)):true', 't.Equal(u):true', 'd.Equal(l):true'), mark=lidx(S(3), 't == t.Round(0):false', 't == u:false', 't.Round(0) 查 false', '用 time.Time 当 map 的 key', 'd == l:false'), kv=KV([['==', '比较时刻、时区和单调读数'], ['Equal', '只比较时刻'], ['map key', '同一时刻可能是不同的 key']], ['map key'])),
    step("成本:time.Now() 32 ns/次;time.Since(t) 15 ns/次;t.Round(0) 2 ns/次。", t=tl(S(4)), mark=lidx(S(4), 'time.Now() 32'), b=bars([['time.Now() (ns)', 32, '32'], ['time.Since(t)', 15, '15'], ['t.Round(0)', 2, '2']], 32, done=[0, 1, 2]), kv=KV([['Now', '32 ns'], ['Since', '15 ns'], ['Round(0)', '2 ns']], ['Round(0)'])),
    step("文档原文:wall clock 用来报时,monotonic clock 用来量时;strip 单调读数的标准写法是 t = t.Round(0);如果 t 和 u 都带单调读数,After/Before/Equal/Compare/Sub 只用单调读数、忽略墙钟读数,只要有一个没有单调读数就退回墙钟;在有些系统上休眠时单调时钟会停;Go 的 == 不仅比较时刻,还比较 Location 和单调读数。", t=tl(S(5)), done=lidx(S(5), 'general rule is that the wall clock', 'canonical way to strip'), mark=lidx(S(5), 'If Times t and u both contain', 'goes to sleep', 'Go == operator compares'), kv=KV([['量时间', '用单调读数'], ['去掉', 't = t.Round(0)'], ['休眠', '单调时钟可能停']], ['量时间'])),
]
A = mkartg('g74', 74, 'Go,time,单调时钟,monotonic,Equal,真实验证,动画演示',
    '在 Go 1.27.1 里验证 time.Time 的单调时钟读数:time.Now() 的 String 带 m=+…;Add 保留、AddDate/Round/Truncate/UTC/Local/In 都去掉;t == t.Round(0) 是 false 而 Equal 是 true,JSON 往返、map key、不同时区都有类似的坑;time.Now() 32 ns,time.Since 15 ns;并摘录文档里关于何时用单调读数的规则。',
    'time.Now() 返回的 Time 里藏着第二个时钟:单调时钟。它让 Sub 和 Since 不受系统时间调整影响,却也让 == 比较、map key 变得出人意料。这篇用实验验证哪些操作保留它、哪些去掉它,以及后果。',
    [('m=+0.000114459', 'time.Now().String() 尾部的单调读数,Round(0) 之后消失'), ('false / true', 't == t.Round(0) 与 t.Equal(t.Round(0))'), ('2 个 vs 9 个', '实验里保留单调读数的操作(Now、Add)与去掉它的操作')],
    [('单调读数是什么', '<p><code>time.Now()</code> 返回的 <code>Time</code> 同时有墙钟读数和单调读数。打印出来尾部的 <code>m=+…</code> 就是后者;文档说墙钟用来报时,单调时钟用来量时。<code>Sub</code>、<code>Since</code> 等在两边都有单调读数时只用它,所以系统时间被校正也不会算出负的耗时。</p>'),
     ('谁会去掉它', '<p><code>Add</code> 保留,<code>AddDate</code>、<code>Round</code>、<code>Truncate</code>、<code>UTC</code>、<code>Local</code>、<code>In</code> 去掉,<code>Date</code> 和 <code>Unix</code> 构造的值本来就没有。想去掉的标准写法是 <code>t.Round(0)</code>。</p>'),
     ('比较和 map key', '<p><code>==</code> 比较的不只是时刻,还有时区和单调读数:<code>t == t.Round(0)</code> 是 false,而 <code>Equal</code> 是 true;用 <code>time.Time</code> 当 map 的 key,用同一时刻去掉单调读数的值就查不到。JSON 往返之后也是 <code>==</code> 不等、<code>Equal</code> 相等。比较时刻永远用 <code>Equal</code>,不要用 <code>==</code>;做 map key 前先 <code>Round(0)</code> 或者转成 Unix 时间。</p>'),
     ('成本', '<p><code>time.Now()</code> 约 32 ns,<code>time.Since</code> 约 15 ns,<code>Round(0)</code> 约 2 ns。对绝大多数程序不是问题。</p>'),
     ('我没法验证的部分', '<p>要证明“系统时间被调整时 Sub 仍然正确”,需要真的修改系统时钟,这需要管理员权限,我没有做,所以这一条只引用文档。休眠时单调时钟停止的说法同样来自文档。</p>')],
    steps,
    [ENV_G + '。所有输出来自单独的小程序;成本用 testing.Benchmark;文档引自 go doc time 的 Monotonic Clocks 一节(逐句核对过原文存在)',
     '没有验证:系统时钟被调整时 Sub/Since 的行为(需要管理员权限修改时钟)、休眠对单调时钟的影响、Linux 与 macOS 的差别、time.Time 在 gob/protobuf 等序列化中的行为'],
    'time 的单调时钟')
