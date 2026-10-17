from lib import *
S = SS('c33')
steps = [
    step("容器里默认的 ulimit:nofile soft=1048576 hard=1048576;nproc soft=unlimited hard=unlimited;core soft=0 hard=unlimited;stack soft=8192 hard=unlimited;memlock soft=unlimited hard=unlimited。默认能打开的文件数是 104 万多个,进程数没有限制。", t=tl(S(1)), done=lidx(S(1), 'nofile', 'nproc'), mark=lidx(S(1), 'core', 'stack', 'memlock'), kv=KV([['nofile', '1048576 / 1048576'], ['nproc', 'unlimited'], ['core', '0 / unlimited'], ['stack', '8192 / unlimited']], ['nofile'])),
    step("--ulimit nofile 限制能打开的文件数:默认下 Python 一直 open /dev/null,打开了 1048573 个后报 No file descriptors available(errno 24);--ulimit nofile=64:64 → 打开了 61 个后失败(64 减去 stdin / stdout / stderr 的 3 个);nofile=64:1024(soft 64、hard 1024)同样 61 个,soft 才是生效的上限。", t=tl(S(2)), done=lidx(S(2), '默认:'), mark=lidx(S(2), 'nofile=64:64', 'nofile=64:1024'), b=bars([['默认 (个)', 1048573, '1048573'], ['nofile=64:64 (个)', 61, '61'], ['nofile=64:1024 (个)', 61, '61']], 1048573, done=[0], mark=[1, 2]), kv=KV([['默认', '打开 1048573 个后 EMFILE(errno 24)'], ['nofile=64:64', '61 个(减去 0、1、2)'], ['soft 64 / hard 1024', '仍是 61 个,soft 生效']], ['soft 64 / hard 1024'])),
    step("soft 与 hard:--ulimit nofile=64:128,root 把 soft 调到 200(超过 hard 128)→ 退出码 1,Invalid argument;调到 100 → 成功。uid 1000 的用户把 hard 调到 4096 → Operation not permitted,退出码 1;把 hard 降到 100 → 成功,再升回 128 → 又是 Operation not permitted。hard 只能降不能升(普通用户)。", t=tl(S(3)), done=lidx(S(3), '把 soft 调到 100', 'hard 降到 100'), mark=lidx(S(3), '把 soft 调到 200', 'hard 调到 4096', '再升回 128'), kv=KV([['soft > hard', 'Invalid argument'], ['普通用户调高 hard', 'Operation not permitted'], ['降低 hard', '可以,之后升不回去']], ['普通用户调高 hard'])),
    step("nproc 按用户(uid)在整个系统里数,不按容器:一个 --user 1000 --ulimit nproc=20 的容器能创建 19 个子进程(python 自己占 1 个)。另外起两个同样 uid 1000 的容器,各占了 7 个进程(共 14 个),再跑同样的测试只能创建 5 个。换成 uid 2000 仍是 19 个;清掉占位容器后 uid 1000 又是 19 个。", t=tl(S(4)), done=lidx(S(4), '换成 uid 2000', '清掉占位容器'), mark=lidx(S(4), '另外 2 个同样 uid 1000'), b=bars([['单独跑 (个)', 19, '19'], ['已有 14 个同 uid 进程 (个)', 5, '5'], ['uid 2000 (个)', 19, '19']], 19, done=[0, 2], mark=[1]), kv=KV([['单独 uid 1000', '19 个'], ['别的容器占了 14 个', '只剩 5 个'], ['uid 2000', '19 个,不受影响']], ['别的容器占了 14 个'])),
]
A = mkartc('c33', 33, 'Docker,ulimit,nofile,nproc,资源限制,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 --ulimit:默认 nofile 是 1048576、nproc 无限制;nofile=64 时只能再打开 61 个文件(扣掉 0/1/2);soft 不能超过 hard、普通用户的 hard 只能降不能升;nproc 按用户 uid 在系统范围内统计,两个同 uid 容器占掉 14 个进程后,新容器 nproc=20 只能再建 5 个。',
    '--ulimit 限制的是什么?默认值是多少,soft 和 hard 有什么区别,nproc 为什么会被别的容器影响?这篇逐项实测,包括 nproc 跨容器相互影响的现象。',
    [('1048573 vs 61', '默认和 nofile=64:64 时,Python 一直 open 能打开的文件个数'), ('只能降不能升', '普通用户(uid 1000)能降低 hard limit,不能再升回去'), ('19 → 5', '同 uid 的其它容器占了 14 个进程后,nproc=20 的容器还能创建的子进程数')],
    [('默认值', '<p>容器默认 nofile 是 1048576(soft 和 hard),nproc 不限制。Docker Desktop 上是这个值,Linux 宿主机上取决于 dockerd 的 systemd 配置,我没有测。</p>'),
     ('nofile', '<p><code>--ulimit nofile=64:64</code> 后能打开的文件只剩 61 个(64 减去标准输入输出错误)。soft 才是实际生效的值;hard 是 soft 能调到的上限。</p>'),
     ('soft 与 hard', '<p>soft 不能大于 hard(Invalid argument);普通用户不能把 hard 调高(Operation not permitted),只能调低,调低之后就升不回去了。</p>'),
     ('nproc 是 uid 级别的', '<p>nproc 限制的是同一个 uid 的进程总数,而且是在整个系统范围内数,不分容器。同 uid 1000 的另外两个容器占了 14 个进程后,新容器的 nproc=20 只剩 5 个可用;换成 uid 2000 不受影响。所以几个共用同一 uid 的容器设同一个 nproc,会互相挤占;限制容器内进程数更合适的是 <code>--pids-limit</code>(见后面的 pids 一篇)。</p>')],
    steps,
    [ENV_C + '。测试程序是 python:3.12-alpine 里的小脚本:循环 open(/dev/null) 直到失败、循环创建 sleep 子进程直到失败;ulimit 值取自容器里的 sh;nproc 实验里用 2 个占位容器(--user 1000,各 7 个进程);每种情形运行一次(现象是确定性的);实验后已删除容器',
     '没有验证:Linux 宿主机的默认值、--ulimit 与 systemd 的 LimitNOFILE 的关系、core 文件、memlock、rttime;root 用户(带 CAP_SYS_RESOURCE)时 nproc 的表现;user namespace 重映射下 nproc 的统计范围'],
    '资源限制 ulimit')
