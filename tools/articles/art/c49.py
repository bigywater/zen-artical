from lib import *
S = SS('c49')
steps = [
    step("-p 9780:8000:docker port 显示 0.0.0.0:9780 和 [::]:9780,docker ps 的 PORTS 列是“0.0.0.0:9780->8000/tcp, [::]:9780->8000/tcp”;Mac 访问 127.0.0.1:9780 得到 hello from container,用局域网地址访问也成功。-p 127.0.0.1:9790:8000:docker port 只有 127.0.0.1:9790;Mac 访问 127.0.0.1:9790 成功,用局域网地址访问 → Connection refused(Errno 61)。写上 127.0.0.1 才能只让本机访问。", t=tl(S(1)), done=lidx(S(1), '-p 9780:8000', 'Mac 访问 127.0.0.1:9780', '局域网地址访问 <本机局域网IP>:9780'), mark=lidx(S(1), '-p 127.0.0.1:9790:8000', '<本机局域网IP>:9790'), kv=KV([['-p 9780:8000', '0.0.0.0 和 [::],局域网也能访问'], ['-p 127.0.0.1:9790:8000', '只绑定 127.0.0.1,局域网地址被拒绝']], ['-p 127.0.0.1:9790:8000'])),
    step("-P(大写)把镜像里 EXPOSE 的端口都映射到随机的宿主机端口:docker port 是“8000/tcp -> 0.0.0.0:55000 ; 9000/udp -> 0.0.0.0:55000”(TCP 和 UDP 用了同一个端口号 55000,在 32768 以上),Mac 访问 127.0.0.1:55000 成功。", t=tl(S(2)), done=lidx(S(2), '随机的宿主机端口'), mark=lidx(S(2), 'docker port →'), kv=KV([['-P', '映射所有 EXPOSE 的端口'], ['宿主机端口', '随机,这里是 55000(TCP 与 UDP 同号)']], ['-P'])),
    step("UDP:-p 9800:9000/udp,Mac 发 UDP “ping” 到 127.0.0.1:9800,收到 udp-echo:ping。只写 -p 9800:9000 不带 /udp 时,映射的是 TCP(docker port 显示 9000/tcp -> 0.0.0.0:9810)。", t=tl(S(3)), done=lidx(S(3), 'udp-echo:ping'), mark=lidx(S(3), '不带 /udp'), kv=KV([['-p 9800:9000/udp', 'UDP 来回通'], ['不写 /udp', '默认是 TCP']], ['不写 /udp'])),
    step("Mac 上是谁在监听这个映射端口:lsof -iTCP:9780 -sTCP:LISTEN 显示进程名 com.docke…(com.docker.backend 的缩写);虚拟机里同一个端口 9780 也在 0.0.0.0 监听。也就是说,Mac 上监听的是 Docker Desktop 自己的进程,再转发到虚拟机里的映射。", t=tl(S(4)), done=lidx(S(4), 'lsof'), mark=lidx(S(4), '虚拟机里有这个端口'), kv=KV([['Mac 上的监听者', 'com.docker.backend(lsof 里被截成 com.docke)'], ['虚拟机里', '0.0.0.0:9780 也在监听']], ['Mac 上的监听者'])),
    step("同一个宿主机端口映射两次:第二个 docker run 退出码 125,报 failed to set up container networking: driver failed programming external connectivity on endpoint…;失败的容器状态是 created——容器已创建但没有启动。", t=tl(S(5)), done=lidx(S(5), '失败的容器处于什么状态'), mark=lidx(S(5), '同一个宿主机端口再映射一次'), kv=KV([['端口冲突', '退出码 125'], ['失败的容器', 'Status=created']], ['失败的容器'])),
]
A = mkartc('c49', 49, 'Docker,端口映射,-p,-P,UDP,Docker Desktop,真实验证,动画演示',
    '在 Docker Desktop(macOS)上实测端口映射:-p 9780:8000 同时绑定 0.0.0.0 和 [::],局域网也能访问,写上 127.0.0.1 后局域网地址被拒绝;-P 把 EXPOSE 的 8000/tcp 和 9000/udp 映射到随机的 55000;不写 /udp 默认是 TCP;Mac 上监听端口的是 com.docker.backend;宿主机端口冲突时退出码 125、容器停在 created。',
    '-p 的几种写法到底差在哪?只想让本机访问怎么写?-P 的随机端口从哪来?映射的端口在 Mac 上是谁在监听?这篇逐项实测,包括端口冲突时容器的状态。',
    [('Connection refused', '-p 127.0.0.1:9790:8000 时,用 Mac 的局域网地址访问的结果'), ('55000', '-P 为 8000/tcp 和 9000/udp 随机选中的宿主机端口(同一个号码)'), ('com.docker.backend', 'Mac 上监听映射端口的进程(lsof 里显示为 com.docke…)')],
    [('绑定地址', '<p><code>-p 9780:8000</code> 没写地址就是所有地址(0.0.0.0 和 [::]),局域网里的其它机器也能访问;<code>-p 127.0.0.1:9790:8000</code> 只在本机回环地址上监听,用局域网地址访问被拒绝。要对外暴露还是只给本机,在这里决定。</p>'),
     ('-P', '<p>-P 把 Dockerfile 里 <code>EXPOSE</code> 声明的所有端口映射到随机的宿主机端口(这次 TCP 和 UDP 拿到了同一个 55000)。<code>docker port</code> 能查到。</p>'),
     ('UDP', '<p>UDP 要写 <code>/udp</code>,否则按 TCP 映射。回显测试证实 UDP 可以双向通。</p>'),
     ('谁在监听', '<p>在 macOS 的 Docker Desktop 上,Mac 里监听映射端口的是 Docker Desktop 自己的进程(lsof 显示 <code>com.docke…</code>),虚拟机里的 0.0.0.0:9780 也在监听,请求经这两层转发给容器。Linux 宿主机上通常是 docker-proxy 或 iptables 规则,我没有测。</p>'),
     ('端口冲突', '<p>宿主机端口已被占用时,docker run 以 125 退出,容器停在 <code>created</code> 状态,需要手动删除。</p>')],
    steps,
    [ENV_C + '。HTTP / UDP 服务是 python:3.12-alpine 里的小脚本;访问用 Python urllib 和 socket;端口从 9780 起挑空闲的;局域网地址已在输出中替换为 <本机局域网IP>;lsof 的进程名被 lsof 截成 com.docke,文中据此写作 com.docker.backend,是我的推断;实验后已删除容器',
     '没有验证:IPv6 地址访问、端口范围写法(-p 9830-9840:8000-8010)、iptables / pf 规则、Linux 上的 docker-proxy、--publish-all 与 Compose 的 ports、端口映射的吞吐开销'],
    '端口映射')
