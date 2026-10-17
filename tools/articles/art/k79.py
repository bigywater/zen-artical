from lib import *
S = SS('k79')
F1 = [['pause 持有', 'net / ipc / uts'], ['容器 a、b', '加入同样的 net / ipc / uts'], ['各自一份', 'pid / mnt / cgroup'], ['pause 本身', '/pause,504 kB,睡眠']]
F2 = [['b → localhost:8080', '访问到 a 的 httpd'], ['b 再监听 8080', 'Address already in use'], ['eth0 地址', 'a、b 相同'], ['文件系统 / 进程', '各自独立']]
F3 = [['停容器 a', '0.4 秒重启,IP 不变'], ['kill -9 pause', '2.9 秒新建沙箱'], ['Pod IP', '10.244.1.239 → 10.244.1.240'], ['Pod uid', '不变']]
PANELS = [('f', 'flow', '沙箱与容器'), ('t', 'term', '实测输出'), ('kv', 'kv', '要点')]
steps = [
    step("读 /proc/<PID>/ns/*:pause、容器 a、容器 b 的 net(4026534862)、ipc(4026534994)、uts(4026534993)命名空间编号完全一样,user 也都是节点的初始 user 命名空间;pid、mnt、cgroup 三个各不相同。pause 进程就是 /pause,State: S (sleeping),VmRSS 只有 504 kB;镜像 registry.k8s.io/pause:3.10 只有 268kB。这三个共享的命名空间是 pause 在沙箱里先创建出来的。", f=fl(F1, cur=[0, 1], mark=[2], done=[3]), t=tl(S(1), mark=lidx(S(1), 'net       ', 'pid       '), done=lidx(S(1), 'pause 进程', 'pause 镜像')), kv=KV([['共享', 'net、ipc、uts 来自沙箱'], ['不共享', 'pid、mnt、cgroup 默认各容器独立'], ['pause', '什么都不做,只是占着命名空间']], ['共享'])),
    step("同一个网络命名空间的后果:容器 b 用 127.0.0.1:8080 访问到容器 a 的 httpd(返回 hi);b 自己再监听 8080 失败(bind: Address already in use,退出码 1);a、b 看到同一个 eth0 地址 10.244.1.239/24。但文件系统各自独立(b 读不到 a 的 /tmp/a-file),进程也各自独立(b 里 ps 只有自己的 sleep 和 ps)。", f=fl(F2, cur=[0, 1], done=[2, 3]), t=tl(S(2), mark=lidx(S(2), 'localhost:8080', 'Address already in use'), done=lidx(S(2), '两个容器看到的 eth0', '文件系统各是各的', '进程各是各的')), kv=KV([['同一个 IP 和端口空间', '容器间用 localhost,端口不能冲突'], ['文件系统不共享', '要共享用卷'], ['进程不共享', '默认看不到彼此']], ['同一个 IP 和端口空间'])),
    step("只停容器 a(crictl stop):0.4 秒内 kubelet 把它重启,restartCount=1,Pod IP 10.244.1.239 → 10.244.1.239 没变,因为 pause 还活着,网络命名空间还在。直接 kill -9 沙箱的 pause 进程:2.9 秒内 kubelet 新建了沙箱(id d6856072… → 85e6b201…),Pod IP 变成 10.244.1.240,但 Pod uid 不变。", f=fl(F3, cur=[0, 1], done=[2, 3]), t=tl(S(3), mark=lidx(S(3), '只停容器 a', '直接 kill -9 pause'), done=lidx(S(3), 'Pod uid 不变')), kv=KV([['IP 绑定 pause', '容器重启不换 IP'], ['沙箱没了', '新沙箱=新 IP,容器全部重建'], ['Pod 对象不变', 'uid 还是原来的']], ['IP 绑定 pause'])),
]
A = mkartk('k79', 79, 'Kubernetes,pause 容器,沙箱,命名空间,Pod,containerd,真实验证,动画演示',
    '在 kind 节点上读 /proc/<PID>/ns:pause 与 Pod 里的两个容器共享同一个 net、ipc、uts 命名空间,pid、mnt、cgroup 各自独立;pause 进程只占 504 kB,镜像 268kB;同一网络命名空间让容器间用 localhost 互通且端口会冲突;只重启容器 IP 不变,杀掉 pause 沙箱重建 IP 就变(10.244.1.239 → .240)而 Pod uid 不变。',
    'Pod 里的容器为什么能用 localhost 互相访问?pause 容器到底在做什么?杀掉它会怎样?这篇在节点上读命名空间编号、做端口冲突实验、分别杀容器和杀 pause,把“Pod 就是一组共享命名空间的容器”落到实处。',
    [('3 个共享', 'pause 与容器共享 net / ipc / uts 命名空间编号;pid、mnt、cgroup 各不相同'), ('504 kB', 'pause 进程的常驻内存;镜像只有 268kB'), ('IP 换了 uid 不换', '杀掉 pause 沙箱后,Pod IP 变化而 Pod 的 uid 不变')],
    [('谁和谁共享', '<p>读 <code>/proc/&lt;PID&gt;/ns/*</code> 的编号:<code>pause</code>、容器 <code>a</code>、容器 <code>b</code> 的 <code>net</code>(4026534862)、<code>ipc</code>(4026534994)、<code>uts</code>(4026534993)完全一样;<code>pid</code>、<code>mnt</code>、<code>cgroup</code> 三个各不相同。<code>pause</code> 进程就是 <code>/pause</code>,状态 <code>S (sleeping)</code>,<code>VmRSS</code> 只有 504 kB;镜像 <code>registry.k8s.io/pause:3.10</code> 只有 268kB。共享的三个命名空间是它在沙箱里先创建出来、容器再加入的。</p>'),
     ('共享网络的后果', '<p>容器 <code>b</code> 用 <code>127.0.0.1:8080</code> 访问到容器 <code>a</code> 的 httpd(返回 <code>hi</code>);<code>b</code> 自己再监听 8080 则失败(<code>bind: Address already in use</code>,退出码 1);两个容器看到同一个 eth0 地址 10.244.1.239/24。但文件系统各自独立(<code>b</code> 读不到 <code>a</code> 的 <code>/tmp/a-file</code>),进程也各自独立(<code>b</code> 里 <code>ps</code> 只有自己的 <code>sleep</code> 和 <code>ps</code>)。共享文件要用卷,共享进程要 <code>shareProcessNamespace</code>(下一篇)。</p>'),
     ('IP 跟着 pause', '<p>只停容器 <code>a</code>(<code>crictl stop</code>):0.4 秒内 kubelet 就重启它,Pod IP 不变——pause 还活着,网络命名空间还在。直接 <code>kill -9</code> 沙箱的 pause 进程:2.9 秒内 kubelet 新建了沙箱(id 从 d6856072… 变成 85e6b201…),Pod IP 变成 10.244.1.240,但 Pod 的 uid 不变。所以“重启容器”和“重建沙箱”是两个层次:前者保留 IP,后者不保留。</p>')],
    steps,
    [ENV_K + '。三节点 kind 集群 kx-main(Kubernetes v1.37.0,pause 镜像 3.10);Pod 固定在 worker;PID 取自 crictl inspect / inspectp,命名空间编号取自节点上的 readlink /proc/<PID>/ns/*;kill -9 直接在节点上对 pause 的 PID 执行;每种情形各一次',
     '没有验证:pause 在 PID 命名空间共享时作为 init 回收僵尸进程的行为(下一篇涉及共享进程);hostNetwork Pod 是否仍有沙箱;kill pause 后 restartCount 的变化(实验中两个容器的 restartCount 都是 1,没有深入解释);沙箱重建时 CNI 的 DEL/ADD 顺序;其他运行时(Kata、gVisor)的沙箱模型;pause 镜像版本与 kubelet 的 --pod-infra-container-image 参数'],
    'pause 容器', PANELS)
