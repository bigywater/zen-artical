from lib import *
S = SS('c28')
steps = [
    step("程序自己决定的退出码:sh -c 'exit 0' → 0,'exit 3' → 3。要运行的命令不存在 → 127;文件存在但不可执行(/etc/hostname)→ 126——这两种 docker run 的退出码就是 127 和 126,但容器的 Status 是 created,没有真正启动;而 sh -c 里调用不存在的命令 → 127,容器是 exited。", t=tl(S(1)), done=lidx(S(1), 'exit 0', 'exit 3'), mark=lidx(S(1), '命令不存在', '不可执行', 'sh -c 里'), kv=KV([['exit N', '退出码 N'], ['命令不存在', '127,容器 Status=created'], ['存在但不可执行', '126,容器 Status=created'], ['sh -c 里命令不存在', '127,容器 exited']], ['命令不存在'])),
    step("docker run 自己出错(不存在的选项 --foo)→ 退出码 125,没有创建出容器。所以 125 是 docker 本身的错误,126、127 是容器要运行的命令的错误。", t=tl(S(2)), done=lidx(S(2), '--foo'), kv=KV([['docker 自己出错', '125,没有容器'], ['命令无法执行 / 找不到', '126 / 127']], ['docker 自己出错'])),
    step("被信号杀死的进程退出码是 128 加信号编号:在 PID 1 的 sh 里依次起子 sh 让它向自己发信号,$? 分别是 TERM→143、INT→130、ABRT→134、SEGV→139、KILL→137。docker kill → 137;docker stop -t 2(PID 1 是 sleep)→ 137,因为 SIGTERM 被忽略,等满超时后被 SIGKILL;--init 下 docker stop → 143;--init 下 docker kill -s INT → 130。docker kill -s TERM 给 PID 1 的 sleep,容器仍是 running——PID 1 没装处理程序时 TERM 不起作用。python 里 ctypes 访问地址 0 → 139;python 的 os.abort() 我预期 134,实际也是 139,没有查原因。", t=tl(S(3)), done=lidx(S(3), 'TERM -> 143', '--init 下 docker stop', '--init 下 docker kill -s INT'), mark=lidx(S(3), 'docker kill(默认 SIGKILL)', 'docker stop -t 2', 'docker kill -s TERM', 'os.abort()'), b=bars([['TERM → 143', 143, '143'], ['KILL → 137', 137, '137'], ['SEGV → 139', 139, '139'], ['ABRT → 134', 134, '134'], ['INT → 130', 130, '130']], 143, done=[0, 4], mark=[1, 2, 3]), kv=KV([['128 + 信号', 'TERM 143、KILL 137、SEGV 139、ABRT 134、INT 130'], ['PID 1 没处理程序', 'docker stop 等满超时后 137;--init 下 143'], ['os.abort()', '实测 139(预期 134,未查原因)']], ['128 + 信号'])),
    step("同样是 137,怎么区分是被 OOM 杀死还是被 kill:内存限制 20m、python 不停申请内存 → docker run 退出码 137,State.ExitCode=137,OOMKilled=True;docker kill 得到的也是 137,但 OOMKilled=False。", t=tl(S(4)), done=lidx(S(4), '内存限制 20m'), kv=KV([['OOM 杀死', 'ExitCode 137,OOMKilled=True'], ['docker kill', 'ExitCode 137,OOMKilled=False']], ['OOM 杀死'])),
]
A = mkartc('c28', 28, 'Docker,退出码,137,143,139,信号,OOMKilled,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里逐个复现容器退出码:127(命令不存在)、126(不可执行)、125(docker 自己出错)、128 加信号编号(TERM 143、INT 130、ABRT 134、SEGV 139、KILL 137);PID 1 没处理程序时 docker stop 得到 137 而 --init 得到 143;137 要靠 OOMKilled 区分 OOM 与 kill。',
    '容器退出码 137、143、139 分别是什么意思?这篇逐个把它们复现出来,并说明哪些是程序自己返回的、哪些是被信号杀死的、哪些是 docker 本身报的错,以及如何区分同样是 137 的 OOM 和手动 kill。',
    [('128 + N', '被信号 N 杀死的进程的退出码,如 TERM 15 → 143、KILL 9 → 137、SEGV 11 → 139'), ('137 vs OOMKilled', '同样的 137,OOM 杀死时 OOMKilled=True,docker kill 时为 False'), ('125 / 126 / 127', 'docker 自己出错 / 命令不可执行 / 命令不存在')],
    [('程序自己的退出码', '<p>exit N 就是 N。命令找不到是 127,找到但不能执行是 126——这两种情况容器根本没有真正启动,Status 是 <code>created</code>。在 <code>sh -c</code> 里调用不存在的命令,也是 127,但容器已经启动并 exited。</p>'),
     ('125', '<p>docker run 自己的错误(例如不存在的选项)是 125,不会创建容器。</p>'),
     ('信号', '<p>被信号杀死的进程的退出码是 128 加信号编号。PID 1 是特殊的:没有安装信号处理程序时,内核不会让它被 TERM 杀死,<code>docker stop</code> 要等满超时后用 KILL,于是得到 137;加 <code>--init</code> 后由 init 转发,子进程被 TERM 杀死,得到 143。python 的 os.abort() 我预期是 134,实际得到 139,原因我没有查。</p>'),
     ('OOM', '<p>137 既可能是 OOM,也可能是 kill。看 <code>docker inspect</code> 的 <code>State.OOMKilled</code>:内存限制下被杀是 True,docker kill 是 False。</p>')],
    steps,
    [ENV_C + '。每种情形运行一次(退出码是确定性的);信号用 docker kill、sh 内的 kill 和 python 触发;--init 使用 Docker 内置的 init;实验后已删除容器',
     '没有验证:Windows 容器的退出码、被内核之外的 OOM(如 cgroup v1)杀死的表现、退出码超过 255、docker wait 与 docker events 里的 exitCode、os.abort() 为什么是 139'],
    '容器退出码')
