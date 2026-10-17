from lib import *
S = SS('c67')
steps = [
    step("docker info 的 Plugins.Log 列出这个 Docker 内置的日志驱动:awslogs、fluentd、gcplogs、gelf、journald、json-file、local、splunk、syslog(none 是特殊的“不记录”)。", t=tl(S(1)), done=lidx(S(1), 'Plugins.Log'), kv=KV([['内置驱动', 'awslogs fluentd gcplogs gelf journald json-file local splunk syslog']], ['内置驱动'])),
    step("--log-driver none:容器照常运行,docker logs 退出码 1,报 Error response from daemon: configured logging driver does not support reading——什么日志都不保留。", t=tl(S(2)), done=lidx(S(2), 'docker logs 退出码'), kv=KV([['none', '不保留日志'], ['docker logs', '报 does not support reading']], ['none'])),
    step("用 --network host 的 Python 接收端当作远程日志服务(虚拟机的 127.0.0.1 上监听 UDP)。--log-driver gelf:接收端收到 2 个包,每个是一条 JSON(version 1.1、host docker-desktop、short_message hello-gelf 或 err-gelf、level 6 / 3、_container_id、_container_name、_command 等)。--log-driver syslog 配 rfc5424 和 tag=c67-demo:收到 2 个包,形如“<30>1 2026-10-10T13:36:36Z docker-desktop c67-demo 283 c67-demo - hello-syslog”(stdout 是 <30>,stderr 是 <27>)。两种驱动下 docker logs 仍然能读到 hello 和 err 两行,退出码 0。", t=tl(S(3)), done=lidx(S(3), '--log-driver gelf', '--log-driver syslog'), mark=lidx(S(3), 'docker logs bwlab-c67-gelf', 'docker logs bwlab-c67-syslog'), kv=KV([['gelf', 'UDP 发 JSON,level 6=stdout、3=stderr'], ['syslog(rfc5424)', 'UDP 发文本,stdout <30>、stderr <27>'], ['docker logs', '远程驱动下仍然可读(本地有缓存)']], ['docker logs'])),
    step("目标不可达:gelf-address=tcp://127.0.0.1:1(没人监听)时 docker run 退出码 125,报 failed to initialize logging driver: gelf: cannot connect to GELF endpoint——容器启动都失败;gelf 用 UDP 发往没人监听的端口,docker run 退出码 0——UDP 不管对方在不在。", t=tl(S(4)), done=lidx(S(4), 'UDP 发往没人监听'), mark=lidx(S(4), 'tcp://127.0.0.1:1'), kv=KV([['TCP 目标连不上', '容器起不来,退出码 125'], ['UDP 目标没人收', '容器正常启动,日志可能丢']], ['TCP 目标连不上'])),
]
A = mkartc('c67', 67, 'Docker,日志驱动,gelf,syslog,log-driver,双写日志,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测日志驱动:内置 awslogs、fluentd、gcplogs、gelf、journald、json-file、local、splunk、syslog;--log-driver none 后 docker logs 报不支持读取;gelf 与 syslog 能把日志发到 UDP 接收端(GELF 的 JSON、rfc5424 的 syslog 行),同时 docker logs 仍然可读;TCP 目标连不上时容器直接起不来(125)。',
    '想把容器日志发到别的地方,日志驱动怎么选、发出去的是什么格式、发不出去会怎样?这篇用一个监听在虚拟机里的 UDP 接收端,看 gelf 和 syslog 实际发出的包,并验证 docker logs 在远程驱动下还能不能用。',
    [('2 个 UDP 包', 'gelf / syslog 驱动下,两行输出(stdout 与 stderr 各一行)在接收端各收到的包数'), ('docker logs 仍可读', '日志发往 gelf 或 syslog 时,docker logs 依然读到两行'), ('125', 'gelf-address 指向没人监听的 TCP 端口时 docker run 的退出码')],
    [('驱动列表', '<p>这个 Docker 内置了九种驱动,<code>none</code> 则完全不保留日志(<code>docker logs</code> 报 <code>does not support reading</code>)。</p>'),
     ('发出去的是什么', '<p>GELF 是每行一个 JSON 包(version、host、short_message、level、_container_id、_container_name…),stderr 的 level 是 3、stdout 是 6;syslog 用 rfc5424 格式,stdout 的优先级是 &lt;30&gt;、stderr 是 &lt;27&gt;,tag 出现在 APP-NAME 位置。接收端是我自己写的 Python UDP 监听,不是真正的 Graylog 或 syslog 服务。</p>'),
     ('docker logs 还能用', '<p>日志发往 gelf 或 syslog 之后,<code>docker logs</code> 依然读到本地缓存的内容,说明 docker 在把日志发出去的同时也在本地保留了一份。缓存多大、保留多久,我没有测。</p>'),
     ('目标不可达', '<p>TCP 目标连不上,容器直接创建失败(125);UDP 因为不需要对方在线,容器能正常启动,但日志可能静默丢失。选驱动时要考虑这两种失败方式。</p>')],
    steps,
    [ENV_C + '。接收端是 --network host 的 python:3.12-alpine 容器(即虚拟机的 127.0.0.1),监听 UDP 并打印每个包;gelf 与 syslog 的参数分别是 gelf-address=udp://… 与 syslog-address=udp://… ;每个驱动运行一次;实验后已删除容器和镜像',
     '没有验证:fluentd、awslogs、splunk、journald、gcplogs 驱动、gelf 的压缩选项、syslog 的 TCP / TLS、网络恢复后丢失日志的补发、非阻塞模式 mode=non-blocking 与 max-buffer-size 的效果'],
    '日志驱动')
