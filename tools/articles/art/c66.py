from lib import *
S = SS('c66')
steps = [
    step("Docker Desktop 的默认日志驱动不是 json-file:docker info 的 Logging Driver = local;虚拟机里 daemon.json 配了 \"log-driver\":\"local\"、\"log-format\":\"json\"。容器的 HostConfig.LogConfig = {Type: local, Config: {}},LogPath 是空的;容器目录下的日志文件是 local-logs/container.log,前 48 个字节是 00 00 00 1c 0a 06 73 74 64 6f 75 74 …(含 stdout、stderr 字样的二进制记录),不是 JSON 文本。docker logs 照常能读到 line-one 和 err-line。", t=tl(S(1)), done=lidx(S(1), '容器目录下的日志相关文件', 'docker logs 仍然能读'), mark=lidx(S(1), 'Logging Driver', 'HostConfig.LogConfig', 'local 日志文件'), kv=KV([['默认驱动', 'local(Docker Desktop 的 daemon.json 配置)'], ['日志文件', 'local-logs/container.log,二进制'], ['LogPath', '空']], ['默认驱动'])),
    step("显式 --log-driver json-file:LogPath = /var/lib/docker/containers/<容器ID>/<容器ID>-json.log,文件里每行一条 JSON:{\"log\":\"line-one\\n\",\"stream\":\"stdout\",\"time\":\"…\"} 和 {\"log\":\"err-line\\n\",\"stream\":\"stderr\",…}——字段是 log、stream、time。我还输出了一段不带换行的 no-newline,日志里没有出现它(容器仍在运行,是否要等换行或进程退出才写出,我没有验证)。", t=tl(S(2)), done=lidx(S(2), '"stream":"stdout"', '"stream":"stderr"'), mark=lidx(S(2), 'LogPath'), kv=KV([['每行一条 JSON', 'log、stream、time 三个字段'], ['stdout / stderr', '用 stream 字段区分'], ['没有换行的输出', '运行期间没有出现']], ['每行一条 JSON'])),
    step("json-file 对超长的一行会拆开:输出一行 40000 个字符,日志文件里是 3 条记录,每条 log 字段长度是 16384、16384、7233;docker logs 读出来仍是 1 行。16384 字节是单条记录的上限。", t=tl(S(3)), done=lidx(S(3), '3 条记录', 'docker logs 读出来'), b=bars([['第 1 条 (字节)', 16384, '16384'], ['第 2 条 (字节)', 16384, '16384'], ['第 3 条 (字节)', 7233, '7233']], 16384, done=[0, 1, 2]), kv=KV([['40000 个字符的一行', '拆成 16384 + 16384 + 7233'], ['docker logs', '拼回 1 行']], ['40000 个字符的一行'])),
    step("轮转:--log-opt max-size=10k --log-opt max-file=3,脚本输出 1000 行,日志目录里只有 json.log(6477 字节)、json.log.1(10033)、json.log.2(10033)三份;docker logs 只能读到 209 行,从 line 791 到 line 999。不设 --log-opt 的 json-file 没有上限:一个 126890 字节的 json.log 文件,docker logs 读到全部 1000 行。(目录里的 config.v2.json 和 hostconfig.json 是容器配置,不是日志。)", t=tl(S(4)), done=lidx(S(4), 'max-size=10k', '脚本一共输出 1000 行'), mark=lidx(S(4), '不设 --log-opt'), b=bars([['轮转后 docker logs 的行数', 209, '209'], ['不设上限 docker logs 的行数', 1000, '1000']], 1000, done=[1], mark=[0]), kv=KV([['max-size=10k, max-file=3', '只保留最近 209 行(line 791~999)'], ['默认 json-file', '无上限,126890 字节,1000 行都在']], ['max-size=10k, max-file=3'])),
    step("容器删除后日志跟着删:docker rm -f 之后 /var/lib/docker/containers/<容器ID> 目录已删除,日志随之消失。", t=tl(S(5)), done=lidx(S(5), '已删除'), kv=KV([['docker rm', '容器目录(含日志)被删除']], ['docker rm'])),
]
A = mkartc('c66', 66, 'Docker,日志,json-file,local日志驱动,日志轮转,docker logs,真实验证,动画演示',
    '在 Docker Engine 29.8.2(Docker Desktop)里实测容器日志:默认驱动是 local(二进制文件 local-logs/container.log,没有 LogPath);显式 json-file 时每行 JSON 带 log / stream / time,超长行按 16384 字节拆开;max-size=10k max-file=3 把 1000 行轮转成只剩 209 行;json-file 默认无上限;容器删除后日志也被删。',
    '容器的日志存在哪里、什么格式、会不会无限增长?Docker Desktop 的默认日志驱动和常见文档里的 json-file 不一样。这篇逐项实测 local 和 json-file 的文件、格式、拆分与轮转。',
    [('local 不是 json-file', 'Docker Desktop 的 daemon.json 把默认日志驱动设成了 local,日志文件是二进制'), ('16384 字节', 'json-file 单条记录的字节上限:40000 个字符被拆成 16384 + 16384 + 7233'), ('209 / 1000 行', 'max-size=10k max-file=3 轮转后 docker logs 剩下的行数,对比不设上限的 1000 行')],
    [('默认是 local', '<p>很多文章说默认的日志文件是 <code>&lt;容器ID&gt;-json.log</code>,但在 Docker Desktop 里默认驱动是 <code>local</code>,日志在 <code>local-logs/container.log</code>,是二进制格式,<code>docker logs</code> 能正常读取。Linux 宿主机 Docker 的默认驱动是 json-file,这是我的了解,没有在 Linux 上验证。</p>'),
     ('json-file 的格式', '<p>显式 <code>--log-driver json-file</code> 后,日志是每行一条 JSON:log(内容,带换行)、stream(stdout 或 stderr)、time。</p>'),
     ('长行', '<p>一行 40000 个字符被拆成 3 条记录(16384、16384、7233),<code>docker logs</code> 读出来再拼成一行。</p>'),
     ('轮转', '<p>json-file 默认不限制大小,一个只输出 1000 行的小脚本就有 126890 字节;设置 <code>max-size</code> 与 <code>max-file</code> 后轮转成 .1、.2 文件,<code>docker logs</code> 只能读到保留下来的部分(209 行)。local 驱动的默认轮转限制我没有测。</p>'),
     ('删除', '<p>容器一删,日志目录就没了,要保留日志得用日志驱动转发到别处(见下一篇)。</p>')],
    steps,
    [ENV_C + '。日志文件取自虚拟机里 /var/lib/docker/containers/<容器ID>/(特权容器加 nsenter 只读读取,方法见 c19);local 驱动只看了文件头的十六进制;轮转实验输出 1000 行(每行约 60 字节);每种情形运行一次;实验后已删除容器',
     '没有验证:local 驱动的默认轮转(max-size / max-file / compress)、日志文件里部分行(partial)的标记、无换行输出在进程退出后是否写出、日志文件被外部截断的行为、Linux 宿主机默认值'],
    '容器日志文件')
