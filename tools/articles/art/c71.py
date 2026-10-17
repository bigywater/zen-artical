from lib import *
S = SS('c71')
steps = [
    step("一个带环境变量、端口映射、命名卷、标签和内存限制的容器。docker inspect 返回一个 JSON 数组,容器对象有 24 个顶层键:AppArmorProfile、Args、Config、Created、Driver、ExecIDs、HostConfig、HostnamePath、HostsPath、Id、Image、ImageManifestDescriptor、LogPath、MountLabel、Mounts、Name、NetworkSettings、Path、Platform、ProcessLabel、ResolvConfPath、RestartCount、State、Storage。State 有 11 个键,Config 17 个,HostConfig 63 个,NetworkSettings 4 个。镜像对象只有 14 个顶层键:Architecture、Comment、Config、Created、Descriptor、Id、Identity、Metadata、Os、RepoDigests、RepoTags、RootFS、Size、Variant。", t=tl(S(1)), done=lidx(S(1), '容器 inspect 的顶层键', 'HostConfig 下有'), mark=lidx(S(1), '镜像 inspect 的顶层键', 'State 的键'), b=bars([['容器对象的顶层键', 24, '24'], ['镜像对象的顶层键', 14, '14'], ['HostConfig 的键', 63, '63']], 63, done=[0, 1], mark=[2]), kv=KV([['容器', '24 个顶层键,HostConfig 里 63 项配置'], ['镜像', '14 个顶层键'], ['State', '11 个键']], ['容器'])),
    step("--format 写法(Go 模板):{{.State.Pid}} 取 PID;{{json .Config.Env}} 得到 [\"MODE=demo\",\"PATH=…\"];{{json .Config.Labels}} 得到 {\"bwlab\":\"1\",\"role\":\"web\"};{{range .Mounts}}…{{end}} 遍历挂载;{{json .NetworkSettings.Ports}} 得到 {\"80/tcp\":[{\"HostIp\":\"127.0.0.1\",\"HostPort\":\"55001\"}]};取宿主机端口用 {{(index (index .NetworkSettings.Ports \"80/tcp\") 0).HostPort}};{{.HostConfig.Memory}} 是 67108864;{{printf \"%.12s\" .Id}} 截取 ID;IP 用 {{(index .NetworkSettings.Networks \"bridge\").IPAddress}}。写错字段名:退出码 1,报 map has no entry for key \"NoSuchField\"。", t=tl(S(2)), done=lidx(S(2), '取端口 80/tcp', '内存上限', '截取 ID'), mark=lidx(S(2), '不存在的字段', '端口映射'), kv=KV([['json', '把任意子树输出成 JSON'], ['index', '按键取 map 里的值'], ['range', '遍历列表'], ['错误字段名', '退出码 1']], ['index'])),
    step("-s 显示可写层大小:docker inspect -s 的 SizeRw 在写 10 MiB 文件前是 8192,写后是 10493952(≈ 10 MiB);SizeRootFs 从 9515008 变成 20000768。不带 -s 时输出里没有 SizeRw 字段。", t=tl(S(3)), done=lidx(S(3), 'SizeRw'), mark=lidx(S(3), '不带 -s'), b=bars([['SizeRw 写前 (字节)', 8192, '8192'], ['SizeRw 写后 (字节)', 10493952, '10493952']], 10493952, done=[0], mark=[1]), kv=KV([['SizeRw', '可写层大小,写 10 MiB 后约 10 MiB'], ['SizeRootFs', '整个根文件系统,同步增加'], ['不带 -s', '没有这两个字段']], ['SizeRw'])),
    step("同名对象:docker tag 出一个叫 bwlab-c71-dup 的镜像,又创建一个同名的容器。docker inspect bwlab-c71-dup 只返回 1 个对象,而且是容器;用 --type image 得到镜像(RepoTags 里有 bwlab-c71-dup:latest),--type container 得到容器(/bwlab-c71-dup)。对象不存在:退出码 1,输出 error: no such object。", t=tl(S(4)), done=lidx(S(4), '--type image'), mark=lidx(S(4), '容器和镜像都叫', '对象不存在'), kv=KV([['不指定 --type', '先匹配到容器'], ['--type image / container', '精确指定'], ['不存在', '退出码 1']], ['不指定 --type'])),
]
A = mkartc('c71', 71, 'Docker,docker inspect,Go模板,format,SizeRw,真实验证,动画演示',
    '在 Docker Engine 29.8.2 里实测 docker inspect:容器对象有 24 个顶层键(HostConfig 63 项),镜像对象 14 个;--format 的 json、index、range、printf 取出 PID、环境变量、标签、挂载、端口映射;-s 才有 SizeRw(写 10 MiB 后约 10493952 字节);容器和镜像同名时默认返回容器,要用 --type 区分。',
    'docker inspect 输出又长又杂,怎么只取需要的?哪些字段是容器的、哪些是镜像的?SizeRw 为什么不显示?这篇逐项实测结构和常用的 --format 写法。',
    [('24 个', '容器 inspect 对象的顶层键数(镜像只有 14 个)'), ('map has no entry', '--format 写了不存在的字段名时模板报的错,退出码 1'), ('10493952', '容器里写 10 MiB 后 docker inspect -s 的 SizeRw')],
    [('结构', '<p>容器对象有 Config(创建时的配置)、HostConfig(63 项运行时配置)、State(运行状态)、NetworkSettings、Mounts 等;镜像对象有 Config、RootFS、Size、RepoTags 等。同一个字段名(如 Config)在两者里含义不同。</p>'),
     ('Go 模板', '<p><code>--format</code> 用 Go 模板:<code>json</code> 输出子树的 JSON,<code>index</code> 按键取值(端口映射、网络都用得上),<code>range</code> 遍历,<code>printf</code> 格式化。模板里引用了不存在的键会报错而不是输出空。</p>'),
     ('-s', '<p><code>-s</code> 让 inspect 多算 SizeRw(可写层)和 SizeRootFs,会多花一点时间;默认不带这两个字段。</p>'),
     ('同名', '<p>容器名和镜像名相同时,inspect 默认先匹配容器,用 <code>--type image</code> 或 <code>--type container</code> 消除歧义。</p>')],
    steps,
    [ENV_C + '。键的个数用 Python 解析 docker inspect 的 JSON 得到;--format 输出直接取自 docker inspect;PID、宿主机端口、容器 ID 每次运行不同,文中取自最后一次运行;实验后已删除容器和卷',
     '没有验证:所有字段的含义(只看了常用的)、Swarm 服务和节点的 inspect、docker inspect 对 volume / network 对象、超长 inspect 输出的性能、旧版 Docker 的字段差异(比如我发现这个版本里容器的 NetworkSettings.IPAddress 是空的,IP 要从 Networks 里取,这一点没有专门做对照实验)'],
    'docker inspect')
