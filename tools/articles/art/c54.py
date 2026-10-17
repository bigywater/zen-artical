from lib import *
S = SS('c54')
steps = [
    step("容器里的 /etc/resolv.conf 是一个单文件 bind mount:mountinfo 里它来自 /docker/containers/<容器ID>/resolv.conf(设备 /dev/vda1,rw);docker inspect 的 ResolvConfPath 是 /var/lib/docker/containers/<容器ID>/resolv.conf。虚拟机里这个文件的内容是 nameserver 192.168.65.7,和虚拟机自己的 /etc/resolv.conf、容器里读到的都一样。", t=tl(S(1)), done=lidx(S(1), 'ResolvConfPath', '容器里的 /etc/resolv.conf'), mark=lidx(S(1), 'mountinfo 里的', '虚拟机自己的'), kv=KV([['容器里', '单文件 bind mount,rw'], ['来源', '/var/lib/docker/containers/<容器ID>/resolv.conf'], ['内容', 'nameserver 192.168.65.7,与虚拟机相同']], ['来源'])),
    step("在容器里追加一行 nameserver 9.9.9.9:容器里变成两行,虚拟机里对应的文件也变了(是同一个文件)。docker restart 之后只剩 nameserver 192.168.65.7;docker stop 再 start 之后同样只有一行——每次启动都会重新生成,手动改的内容不保留。", t=tl(S(2)), done=lidx(S(2), 'docker restart 之后', 'docker stop 再 start'), mark=lidx(S(2), '追加 nameserver 9.9.9.9', '虚拟机里对应文件也变了吗'), kv=KV([['容器里改', '虚拟机里的对应文件同步变化'], ['restart / stop+start', '重新生成,改动丢失']], ['restart / stop+start'])),
    step("不同模式下生成的内容:--network host 和 --network none 都是 nameserver 192.168.65.7;--dns 9.9.9.9 --dns-search corp.test --dns-opt timeout:1 → nameserver 9.9.9.9、search corp.test、options timeout:1;默认 bridge + 两个 --dns → nameserver 9.9.9.9 与 nameserver 1.1.1.1 两行。", t=tl(S(3)), done=lidx(S(3), '--dns 9.9.9.9 --dns-search', '默认 bridge + --dns'), mark=lidx(S(3), '--network host', '--network none'), kv=KV([['--network host / none', '继承 192.168.65.7'], ['--dns / --dns-search / --dns-opt', '逐项写进文件'], ['多个 --dns', '每个一行 nameserver']], ['--dns / --dns-search / --dns-opt'])),
    step("守护进程层面:虚拟机里的 /run/config/docker/daemon.json 里没有 dns 配置,所以默认来源就是虚拟机自己的 /etc/resolv.conf(也就是 Docker Desktop 的 DNS 地址 192.168.65.7)。", t=tl(S(4)), done=lidx(S(4), 'daemon.json'), kv=KV([['daemon.json', '没有 dns 配置'], ['默认来源', '虚拟机的 /etc/resolv.conf']], ['默认来源'])),
]
A = mkartc('c54', 54, 'Docker,resolv.conf,DNS,--dns,--dns-search,容器启动,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测容器的 /etc/resolv.conf:它是来自 /var/lib/docker/containers/容器ID/resolv.conf 的单文件 bind mount,默认复制虚拟机的 nameserver 192.168.65.7;在容器里改它会同步到那个文件,但 restart 或 stop 再 start 后被重新生成;--dns、--dns-search、--dns-opt 逐项写入;daemon.json 里没有 dns 配置。',
    '容器里的 /etc/resolv.conf 从哪来?改了它能保存吗?--network host、--network none、--dns 各会生成什么?这篇读 mountinfo 和 docker inspect,逐项实测。',
    [('每次启动重新生成', '在容器里追加的 nameserver 在 docker restart 和 stop 后再 start 之后都不见了'), ('192.168.65.7', '默认来源:虚拟机自己的 /etc/resolv.conf'), ('单文件 bind mount', 'resolv.conf 来自虚拟机里的 /var/lib/docker/containers/&lt;容器ID&gt;/')],
    [('文件从哪来', '<p>容器的 <code>/etc/resolv.conf</code> 是 bind mount 的单个文件,docker inspect 的 <code>ResolvConfPath</code> 指出了它在虚拟机里的位置。默认复制虚拟机自己的 resolv.conf。</p>'),
     ('改了会怎样', '<p>容器里改它是可写的,改动同步到虚拟机里的那个文件,但容器 restart(或 stop 后 start)时 docker 会重新生成,改动丢失。所以别在容器里手改,用 <code>--dns</code> 等参数。至于容器运行期间虚拟机自己的 resolv.conf 变了会不会同步给容器,我没有测。</p>'),
     ('各种选项', '<p>--dns、--dns-search、--dns-opt 逐项写入;多个 --dns 就是多行 nameserver。自定义网络里的 127.0.0.11 见 c48。</p>'),
     ('守护进程', '<p>daemon.json 里没有 dns 字段(我是读虚拟机里的 /run/config/docker/daemon.json 确认的),所以默认来源就是虚拟机自己。在 Docker Desktop 里这个配置由 Docker Desktop 管理,我不修改。</p>')],
    steps,
    [ENV_C + '。容器里的内容用 grep 去掉注释和空行后列出;虚拟机侧文件用特权容器加 nsenter 只读读取(方法见 c19);容器 ID 在输出中已替换为 <容器ID>;每种情形运行一次;实验后已删除容器',
     '没有验证:虚拟机的 resolv.conf 在容器运行期间变化后是否同步、容器内 systemd-resolved 的情形、Linux 宿主机上回环地址的 nameserver 被过滤的行为、daemon.json 里加 dns 的效果(不修改配置)、--dns 对 IPv6 的支持'],
    'resolv.conf 的生成')
