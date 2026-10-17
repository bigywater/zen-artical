from lib import *
S = SS('c92')
steps = [
    step("--ulimit nofile=200:200,一个每隔 0.01 秒 open 一次 /etc/hostname 且从不 close 的 Python 程序:第 198 次 open 失败,[Errno 24] No file descriptors available: '/etc/hostname'(加上 0、1、2 号标准流,共 200 个);普通写法的程序在处理这个错误时又去读 /proc/self/fd,同样需要一个 fd,于是又抛出异常,容器 exited、ExitCode=1——到了上限,连报错和诊断代码都可能跑不起来。换成出错后先关掉 20 个再汇报的写法:日志同样是第 198 次失败,汇报的 fd 数 181;docker exec 数 /proc/1/fd 是 180 个,按目标分组:/etc/hostname×177、pipe×2、/dev/null×1。", t=tl(S(1)), done=lidx(S(1), '出错后先关掉 20 个', 'docker exec 数 /proc/1/fd'), mark=lidx(S(1), '普通写法的泄漏程序', '这些 fd 指向什么'), b=bars([['nofile 上限', 200, '200'], ['泄漏到失败时的 fd 数', 198, '198']], 200, done=[0], mark=[1]), kv=KV([['普通写法', '处理错误也要 fd → 再次失败,容器退出 (1)'], ['留出余地的写法', '能汇报:180 个 fd,177 个指向 /etc/hostname'], ['定位', '看 /proc/1/fd 里的链接目标分组']], ['定位'])),
    step("没有上限时(默认 nofile 约 104 万)泄漏不会停:1 秒时 97 个 fd,3 秒时 286 个,约每秒 94 个(每 0.01 秒开一个)。虚拟机的 /proc/sys/fs/file-nr(已分配的文件句柄数,全局)3858 → 3 秒后 4160(+302);删掉泄漏的容器后回落到 3576。这个计数是整台虚拟机里所有容器共享的。", t=tl(S(2)), done=lidx(S(2), '默认 nofile 上限', '删掉泄漏的容器后'), mark=lidx(S(2), '虚拟机的 /proc/sys/fs/file-nr', '再过 3 秒'), b=bars([['1 秒时 fd 数', 97, '97'], ['3 秒时 fd 数', 286, '286']], 286, done=[0], mark=[1]), kv=KV([['泄漏速度', '约 94 个/秒'], ['file-nr(全局)', '3858 → 4160,删容器后 3576']], ['file-nr(全局)'])),
    step("socket 泄漏:容器里的服务端接受连接后立刻关闭,客户端连了 60 个、一个都不 close。/proc/net/tcp 各状态的连接数:LISTEN 1、FIN_WAIT2 60(服务端已发 FIN,等客户端)、CLOSE_WAIT 60(客户端收到 FIN 却没 close);客户端的 fd 里 socket 有 61 个(60 个连接加监听的)。看到大量 CLOSE_WAIT,就是应用没有关闭收到对端关闭的连接。", t=tl(S(3)), done=lidx(S(3), '各状态的连接数', 'fd 里 socket'), mark=lidx(S(3), '日志'), b=bars([['CLOSE_WAIT', 60, '60'], ['FIN_WAIT2', 60, '60'], ['LISTEN', 1, '1']], 60, done=[2], mark=[0, 1]), kv=KV([['CLOSE_WAIT', '60 个:对端已关,本端没 close(客户端泄漏的特征)'], ['FIN_WAIT2', '60 个:本例中服务端等客户端关闭']], ['CLOSE_WAIT'])),
    step("不装 lsof 也能查:/proc/1/limits 的 Max open files 是 300 300 files(刚好是 --ulimit 设的值);/proc/1/fdinfo/<fd> 给出位置和标志(pos 0、flags 02400000、mnt_id、ino);已经泄漏到上限附近,/proc/1/fd 里有 280 个 fd。", t=tl(S(4)), done=lidx(S(4), 'Max open files', 'fdinfo'), mark=lidx(S(4), '各 fd 的数量'), kv=KV([['/proc/<pid>/limits', '看上限'], ['/proc/<pid>/fd', '看每个 fd 指向谁'], ['/proc/<pid>/fdinfo', '看位置与标志']], ['/proc/<pid>/fd'])),
]
A = mkartc('c92', 92, 'Docker,文件描述符,fd泄漏,ulimit,CLOSE_WAIT,/proc,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里复现文件描述符泄漏:nofile=200 时第 198 次 open 报 No file descriptors available,普通写法的程序处理错误时又要 fd 而再次失败(容器退出 1);无上限时每秒泄漏约 94 个且虚拟机全局的 file-nr 同步增长(3858 → 4160);socket 泄漏表现为 60 个 CLOSE_WAIT;用 /proc/PID/fd 的链接目标分组就能定位,不需要 lsof。',
    '服务跑着跑着报 Too many open files,怎么确认是 fd 泄漏、泄漏的是什么、从容器外怎么查?这篇用故意泄漏文件和 socket 的程序复现,并给出不装 lsof 的排查办法。',
    [('第 198 次', 'nofile=200 下泄漏程序 open 失败的次数(0、1、2 号标准流占去 3 个)'), ('60 个 CLOSE_WAIT', '客户端连了 60 个、服务端关闭后客户端不 close,容器里 /proc/net/tcp 的 CLOSE_WAIT 数'), ('约 94 个/秒', '无上限时 fd 泄漏的速度(每 0.01 秒开一个)')],
    [('到上限', '<p>错误是 <code>[Errno 24] No file descriptors available</code>(EMFILE,有些地方显示 Too many open files)。要小心的是:处理这个错误的代码本身也需要 fd,没留余地时诊断、写日志都会失败,进程可能直接崩掉。</p>'),
     ('全局影响', '<p>泄漏的 fd 对应内核里已分配的文件句柄,<code>/proc/sys/fs/file-nr</code> 是整台机器共享的计数(上限是 fs.file-max,全局参数,容器不能改,见 c90)。一个容器泄漏会占用所有容器共享的额度;容器删除后句柄被回收。这里的变化里还混有虚拟机里别的活动,所以只能看趋势。</p>'),
     ('socket', '<p>对端关闭而本端不 close 的连接停在 CLOSE_WAIT,数量等于泄漏的连接数,是应用忘了关连接的典型迹象。看状态可以直接读 <code>/proc/net/tcp</code>(第 4 列 08 是 CLOSE_WAIT)。</p>'),
     ('怎么查', '<p><code>/proc/&lt;pid&gt;/limits</code> 看上限,<code>/proc/&lt;pid&gt;/fd</code> 里每个符号链接指向文件、socket 或 pipe,按目标分组统计就能看出泄漏的是什么(这里 177 个都指向 /etc/hostname);fdinfo 给出位置和标志。容器里没有 lsof 也不影响,docker exec 进去读 /proc 即可。</p>')],
    steps,
    [ENV_C + '。泄漏程序是 python:3.12-alpine 里的小脚本(文件模式每 0.01 秒 open 一次不 close;socket 模式连本地服务端 60 次不 close);上限用 --ulimit nofile 设置;全局计数读自虚拟机的 /proc/sys/fs/file-nr(特权容器加 nsenter,方法见 c19),期间虚拟机里别的活动会让数字有噪声;状态码读自 /proc/net/tcp;实验后已删除容器',
     '没有验证:真实服务(Nginx、Java)的 fd 泄漏、fs.file-max 被耗尽时的全局故障(不做)、epoll 与 inotify 实例的上限(fs.inotify.max_user_instances)、fd 泄漏与线程数的关系、lsof / ss 的输出对照'],
    '文件描述符泄漏')
