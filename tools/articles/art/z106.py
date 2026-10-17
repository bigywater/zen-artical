from lib import *
R = J('z106'); k = R['kill']; cf = R['cfg']
def S(x): return [l for l in out('z106').split('== ')[x].splitlines()[1:] if l.strip()]
steps = [
    step("启动一个 Spring Boot 3.3.5 + Spring Cloud 2023.0.4 的应用 demo-svc(依赖 spring-cloud-starter-zookeeper-discovery 与 -config),只配了 spring.cloud.zookeeper.connect-string:ZooKeeper 里出现 /services/demo-svc/<uuid>(临时节点)。数据是 Curator ServiceDiscovery 的 JSON:name、id、address、port、payload(类 ZookeeperInstance,metadata 里有 instance_status=UP)、registrationTimeUTC、serviceType=DYNAMIC、uriSpec。应用自己的 DiscoveryClient 看得到这个服务和实例。", t=tl(S(1)), done=[0], kv=KV([['注册路径', '/services/<应用名>/<uuid>(临时)'], ['数据', 'Curator ServiceInstance JSON']], ['注册路径'])),
    step(f"再起一个实例:两个应用的 DiscoveryClient 都看到 2 个实例。kill -9 其中一个:ZooKeeper 里的节点 {k['zk']:.1f} s 后才消失,另一个应用的 DiscoveryClient 同时(同一次轮询内)去掉它。会话协商超时是 20000 ms(cons 里两个 Spring 应用的会话都是 20000;tickTime=1000 时服务端上限 20 s),所以崩溃的发现延迟 ≈ 20 s —— 比第 101 篇里 Dubbo 的默认值是同一数量级。", t=tl(S(2)), mark=[3], b=bars([['节点消失', k['zk'], f"{k['zk']:.1f} s"], ['DiscoveryClient 去掉', k['app'], f"{k['app']:.1f} s"]], 25, done=[0, 1]), kv=KV([['kill -9 后实例消失', f"{k['zk']:.1f} s"], ['会话超时(协商)', '20000 ms']], ['kill -9 后实例消失'])),
    step(f"配置中心:/config/demo-svc/demo.msg 在应用启动后才建,/cfg 在 {cf['create_ms']:.0f} ms 内变成 v1;再改成 v2,{cf['set_ms']:.0f} ms 内生效(应用端 Environment 被 watcher 实时更新,没有重启也没有手动刷新)。配置的路径规则:/config/<上下文>/<属性名>,节点名就是属性名(demo.msg),节点数据是值。", t=tl(S(3)), done=[0, 1], kv=KV([['新建配置节点', f"{cf['create_ms']:.0f} ms 生效"], ['修改', f"{cf['set_ms']:.0f} ms 生效"]], ['新建配置节点'])),
    step("优先级:应用运行中新建全局默认 /config/application/demo.msg=GLOBAL,/cfg 仍是 v2,但这不能说明优先级(目录是启动后才有的,可能根本没有被监听)。重启应用后,GLOBAL 与 /config/demo-svc/demo.msg=v2 同时存在,/cfg 是 v2 —— 应用专属的配置压过全局的 application 默认配置。", t=tl(S(3)), mark=[len(S(3)) - 5 if len(S(3)) > 5 else 0], kv=KV([['优先级', '/config/<应用名> > /config/application']], ['优先级'])),
]
A = dict(
    n=106, series='zookeeper', tags='ZooKeeper,Spring Cloud,服务发现,配置中心,真实验证,动画演示',
    desc=f'真实运行 Spring Boot 3.3.5 + Spring Cloud 2023.0.4 的 ZooKeeper 服务发现与配置中心:/services/<应用>/<uuid> 临时节点与 JSON 内容;kill -9 后 {k["zk"]:.1f} s 才摘除(会话协商 20 s);配置节点 {cf["create_ms"]:.0f}/{cf["set_ms"]:.0f} ms 生效、应用专属配置压过全局默认。',
    lead='Spring Cloud 对 ZooKeeper 的支持只有两件事:服务注册发现(基于 Curator ServiceDiscovery)和配置中心(监听 /config 下的节点)。这篇真起 Spring Boot 应用,看它写了哪些节点、数据长什么样、实例消失与配置变化各要多久。',
    facts=[('/services/<应用>/<uuid>', 'Spring Cloud 的注册路径(临时节点,数据是 Curator JSON)'), (f'{k["zk"]:.0f} s', 'kill -9 后实例从 ZooKeeper 消失(会话协商 20 s)'), (f'{cf["set_ms"]:.0f} ms', '改一个 /config 节点后应用 Environment 的生效时间')],
    body=[
        sec('注册', '', term('', blk('z106', 1)), '<p>节点格式是 <a href="zookeeper-curator.html">Curator</a> 的 ServiceDiscovery 约定,和<a href="zookeeper-dubbo-registry-source.html">Dubbo 的 /dubbo、/services 布局</a>不是一回事(Dubbo 3 的应用级注册也用 <code>/services</code> 路径,但 JSON 的 payload 是 Dubbo 自己的类)。IP 已替换成 <code>&lt;本机局域网IP&gt;</code>。</p>'),
        sec('实例消失', '', term('', blk('z106', 2)), '<p>原因与<a href="zookeeper-service-discovery.html">服务发现</a>那篇相同:没有主动注销就靠会话过期。需要更快,要缩短 <code>spring.cloud.zookeeper.session-timeout</code>(我没有改它,没有验证改后的效果)。</p>'),
        sec('配置', '', term('', blk('z106', 3)), '<p>推送机制就是<a href="zookeeper-config-center.html">配置中心</a>那篇的 watch;Spring 在这之上做了属性源合并。</p>'),
        sec('分步演示', '', demo('Spring Cloud ZooKeeper', [('t', 'term', '输出'), ('b', 'bars', '时间'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。Spring Boot 3.3.5、Spring Cloud 2023.0.4(spring-cloud-zookeeper 4.1.x,经 Maven 代理下载)、ZooKeeper 3.9.6 客户端,OpenJDK 17;应用自己写了 /hello /cfg /instances 三个接口;输出里的本机局域网 IP 已替换为 <本机局域网IP>', '没有验证:session-timeout 等配置项改变后的效果、Spring Cloud LoadBalancer 在实例变化时的行为、/config 下 profile 后缀目录(demo-svc,prod)的规则、@RefreshScope Bean 的刷新、ZooKeeper 不可用时应用的启动行为(fail-fast)'],
)
