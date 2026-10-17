from lib import *
S = SS('c45')
steps = [
    step("默认容器的 /dev 里没有 /dev/fuse、/dev/net/tun、/dev/loop7(ENOENT),只有 /dev/zero 之类的基础设备。加 --device /dev/fuse --device /dev/net/tun:/dev/fuse(crw-rw-rw- 10:229)和 /dev/net/tun(10:200)出现,能以只读和只写打开;没有指定的 /dev/loop7 仍然不存在。", t=tl(S(1)), done=lidx(S(1), '--device /dev/fuse --device /dev/net/tun:', '/dev/fuse:crw-rw-rw- 10:229'), mark=lidx(S(1), '默认:'), kv=KV([['默认', 'fuse、tun、loop7 都不存在'], ['--device /dev/fuse', '设备文件出现,主次设备号 10:229'], ['没指定的设备', '仍然不存在']], ['--device /dev/fuse'])),
    step("权限后缀和改名:--device /dev/loop7:/dev/mydisk:r 把宿主的 loop7(块设备 7:7)映射成容器里的 /dev/mydisk,只读打开成功,以写方式打开 → EPERM;原来的 /dev/loop7 路径不存在。:rw 则以写方式打开也成功。--device /dev/zero:/dev/myzero 把 /dev/zero(1:5)改名成 /dev/myzero。", t=tl(S(2)), done=lidx(S(2), ':rw(读写', '/dev/myzero'), mark=lidx(S(2), ':r(只读)', 'O_WRONLY→EPERM'), kv=KV([['设备:/容器内路径', '可以改名,主次设备号不变'], [':r', '只读打开成功,写方式打开 EPERM'], [':rw', '读写都成功']], [':r'])),
    step("容器里自己 mknod 一个 /tmp/myfuse(c 10 229):默认(有 MKNOD capability)mknod 成功,但打开 → EPERM(读和写都不行);加 --device-cgroup-rule 'c 10:229 rwm',同样的设备文件读写都能打开;规则只给 r,读成功、写 EPERM。有 MKNOD 只能创建设备文件,能不能用要看 cgroup 的设备规则。", t=tl(S(3)), done=lidx(S(3), "'c 10:229 rwm'"), mark=lidx(S(3), '默认(有 MKNOD capability)', "'c 10:229 r'"), kv=KV([['mknod', '只创建文件,默认可以'], ['打开设备', '由设备 cgroup 规则决定'], ["--device-cgroup-rule 'c 10:229 r'", '读成功,写 EPERM']], ['打开设备'])),
    step("docker inspect 里记录:HostConfig.Devices 是 [{PathOnHost: /dev/fuse, PathInContainer: /dev/fuse, CgroupPermissions: rwm}, {PathOnHost: /dev/loop7, PathInContainer: /dev/mydisk, CgroupPermissions: r}],DeviceCgroupRules 是 [\"c 10:229 rwm\"]。", t=tl(S(4)), done=lidx(S(4), 'HostConfig.Devices', 'DeviceCgroupRules'), kv=KV([['Devices', '宿主路径、容器路径、权限(rwm / r)'], ['DeviceCgroupRules', 'c 10:229 rwm']], ['Devices'])),
]
A = mkartc('c45', 45, 'Docker,--device,设备直通,device-cgroup-rule,mknod,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测设备直通:--device /dev/fuse 才能在容器里看到并打开 fuse 设备;:r 后缀让写方式打开返回 EPERM,设备可以改名映射;容器里 mknod 只创建设备文件,打开仍被 EPERM,要靠 --device-cgroup-rule 放行。',
    '怎么把宿主机的设备交给容器用?--device 的 r/w/m 权限有什么用?容器里 mknod 出来的设备文件为什么打不开?这篇用 /dev/fuse、/dev/net/tun、/dev/loop7 实测。',
    [('ENOENT → 10:229', '默认容器里没有 /dev/fuse;加 --device 后出现,主次设备号 10:229'), (':r → EPERM', '以只读权限放进来的设备,用写方式打开得到 EPERM'), ('mknod 成功但 EPERM', '容器里自己 mknod 的设备文件,没有设备 cgroup 规则时打不开')],
    [('--device', '<p>只有显式 <code>--device</code> 的设备才会出现在容器的 /dev 里;没指定的(如 loop7)仍然不存在。设备在容器里的路径可以改名,主次设备号不变。</p>'),
     ('权限后缀', '<p>路径后面的 <code>:r</code>、<code>:rw</code> 是设备 cgroup 的权限:只读时,以写方式打开设备返回 EPERM。我这里只试了打开(open),没有真正读写块设备。</p>'),
     ('mknod 不等于能用', '<p>默认容器有 MKNOD capability,能创建设备文件;但设备 cgroup 没有放行这个主次设备号时,open 一律 EPERM。<code>--device-cgroup-rule \'c 10:229 rwm\'</code> 放行后才能打开。这也是为什么 --privileged 之外,想用某类设备时优先 --device。</p>'),
     ('inspect 里的样子', '<p><code>HostConfig.Devices</code> 记录宿主路径、容器路径和权限,<code>DeviceCgroupRules</code> 记录规则字符串。</p>')],
    steps,
    [ENV_C + '。设备是 Docker Desktop 虚拟机里已有的:/dev/fuse、/dev/net/tun、/dev/loop7(块设备,只做 open / close,没有读写数据);打开测试用 Python os.open;每种配置运行一次;实验后已删除容器和镜像',
     '没有验证:真实设备(GPU、串口、USB)的直通、--device 对设备节点属主与模式的影响、cgroup v1 devices 子系统、Docker Desktop 以外的 Linux 宿主机的设备、fuse 文件系统的实际挂载'],
    '设备直通')
