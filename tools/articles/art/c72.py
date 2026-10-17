from lib import *
S = SS('c72')
steps = [
    step("容器里 sh 起了两个 sleep。docker top 的默认列是 UID PID PPID C STIME TTY TIME CMD:sh 的 PID 是 53711(PPID 53687)、两个 sleep 是 53725、53726。docker exec ps 看到的却是 PID 1、7、8(PPID 1)。同一个进程,docker top 给的是虚拟机里的 PID:docker inspect 的 State.Pid = 53711,/proc/53711/status 的 NSpid 是“53711 1”(虚拟机里 53711,容器里 1)。", t=tl(S(1)), done=lidx(S(1), '容器主进程在虚拟机里的 PID', 'sh -c sleep 300 & sleep 301 & wait'), mark=lidx(S(1), 'docker exec ps', 'docker top(默认列)'), kv=KV([['docker top', '虚拟机里的 PID(53711…)'], ['docker exec ps', '容器里的 PID(1、7、8)'], ['NSpid', '53711 1:同一个进程的两个编号']], ['docker top'])),
    step("docker top 把后面的参数交给虚拟机里的 ps:-o pid,ppid,user,comm 只显示这四列;aux 显示 USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND;-eo pid,nlwp,rss,etime,args 显示线程数、常驻内存、运行时间。都是退出码 0。", t=tl(S(2)), done=lidx(S(2), '-o pid,ppid,user,comm', 'aux', '-eo'), kv=KV([['-o 列', '自定义列'], ['aux', 'BSD 风格全部信息'], ['-eo', 'POSIX 风格自定义']], ['-o 列'])),
    step("用户名由虚拟机解析:容器用 --user 1,容器里的 /etc/passwd 里 uid 1 叫 bin,docker exec 里 id -un 也是 bin;虚拟机里 uid 1 叫 daemon,docker top 的 UID 列显示的是 daemon。docker top -o user,uid,comm 报错 Couldn't find PID field in ps output——docker top 要求输出里必须有 PID 列。", t=tl(S(3)), done=lidx(S(3), '虚拟机里 uid 1 的名字', 'docker top 显示'), mark=lidx(S(3), '容器里 uid 1 的名字', 'docker top -o user,uid'), kv=KV([['容器里 uid 1', 'bin'], ['虚拟机里 uid 1', 'daemon'], ['docker top 显示', 'daemon(虚拟机的解析)'], ['缺 PID 列', '报错']], ['docker top 显示'])),
    step("容器里没有 ps 也能用 docker top:scratch 镜像里只有一个静态 Go 程序 /app,docker exec ps 退出码 127(exec: \"ps\": executable file not found);同一个容器 docker top 照常列出 root 53xxx /app 这一行。docker top 用的是虚拟机的 ps,不依赖容器里有什么。", t=tl(S(4)), done=lidx(S(4), '同一个容器 docker top'), mark=lidx(S(4), 'scratch 镜像里'), kv=KV([['docker exec ps', '容器里没有 ps → 127'], ['docker top', '正常列出进程']], ['docker top'])),
]
A = mkartc('c72', 72, 'Docker,docker top,进程,PID,NSpid,scratch,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 docker top:它显示的是虚拟机里的 PID(53711),docker exec ps 里是容器里的 PID(1);参数交给虚拟机的 ps;用户名由虚拟机的 /etc/passwd 解析(uid 1 在容器里叫 bin、docker top 显示 daemon);必须含 PID 列;scratch 镜像里没有 ps 也能用 docker top。',
    'docker top 看到的 PID 为什么和容器里 ps 不一样?它怎么知道用户名?容器里没有 ps 怎么办?这篇逐项对比 docker top、docker exec ps 和 /proc 里的 NSpid。',
    [('53711 对 1', '同一个容器主进程:docker top 的 PID 与容器里的 PID'), ('daemon 对 bin', '容器里 uid 1 叫 bin,docker top 显示虚拟机里的名字 daemon'), ('127 对 正常', '没有 ps 的 scratch 镜像:docker exec ps 失败,docker top 正常')],
    [('两套 PID', '<p>docker top 在虚拟机里对容器 cgroup 里的进程跑 ps,所以 PID 是虚拟机的 PID;容器里的 ps 看到的是容器自己的 PID 命名空间。<code>/proc/&lt;PID&gt;/status</code> 的 <code>NSpid</code> 能把两个编号对上。</p>'),
     ('参数与列', '<p>docker top 后面的参数原样交给虚拟机里的 ps,可以自定义列、用 aux 等写法;输出里必须有 PID 列。</p>'),
     ('用户名', '<p>用户名是虚拟机的 ps 去解析的,容器里的 /etc/passwd 对它没用:同一个 uid 1,容器里叫 bin,docker top 显示的是虚拟机里的 daemon。</p>'),
     ('没有 ps 的镜像', '<p>distroless 或 scratch 镜像里没有 ps,<code>docker exec</code> 无计可施,<code>docker top</code> 仍然可用,是排查这类容器的少数办法之一。僵尸进程在 docker top 里看不到,见 c31。</p>')],
    steps,
    [ENV_C + '。docker top 与 docker exec ps 的输出在同一时刻取得;虚拟机里的 /proc 与 /etc/passwd 通过特权容器加 nsenter 读取(方法见 c19);scratch 镜像是用宿主机 go 交叉编译的静态程序;PID 每次运行不同,文中取自最后一次运行;实验后已删除容器和镜像',
     '没有验证:Linux 宿主机上 docker top 的 PID(与宿主机 PID 相同,我没有测)、有 user namespace 重映射时的用户名、docker top 在容器很多进程时的性能、Windows 容器'],
    'docker top')
