from lib import *
S = SS('x9')
steps = [
    step("扫描一个包的时间随 @Component 数量变化(脚本生成的类,每个规模 5 次取中位数)。100 个:scan() 41 ms,扫描期间新加载 205 个类,得到 105 个 BeanDefinition,随后 refresh() 实例化花 97 ms、新加载 471 个类。1000 个:144 ms,仍是 205 个类,refresh 274 ms、新加载 1371 个类。3000 个:220 ms,205 个类,refresh 551 ms、3371 个类。扫描期间加载的类数不随组件数增长,类是到实例化时才被加载。", t=tl(S(1)), mark=lidx(S(1), '3000  |', '1000  |'), done=lidx(S(1), '100  |'), b=bars([['100 个:scan() ms', 41, '41'], ['1000 个:scan() ms', 144, '144'], ['3000 个:scan() ms', 220, '220'], ['3000 个:refresh() ms', 551, '551']], 551, done=[0], cur=[1, 2], mark=[3]), kv=KV([['扫描时新加载的类', '三种规模都是 205'], ['refresh 时新加载的类', '471 / 1371 / 3371'], ['scan() 耗时', '41 / 144 / 220 ms'], ['结论', '类到实例化时才加载']], ['扫描时新加载的类'])),
    step("包里没有注解的普通类也要被读。固定 100 个 @Component,同一个包再放 0、2000、8000 个没有注解的普通类:scan() 分别是 44 ms、145 ms、401 ms,BeanDefinition 数始终是 105,扫描时新加载的类始终约 205 到 206 个。扫描范围里的每一个 .class 文件都有成本,不管它有没有注解;扫描一个大包或者整个 classpath(见第四节)会慢得多。", t=tl(S(2)), mark=lidx(S(2), '8000  |', '2000  |'), done=lidx(S(2), '0  |'), b=bars([['0 个普通类:scan() ms', 44, '44'], ['2000 个:scan() ms', 145, '145'], ['8000 个:scan() ms', 401, '401'], ['BeanDefinition 数(三种都一样)', 105, '105']], 401, done=[0], cur=[1], mark=[2, 3]), kv=KV([['普通类 0 / 2000 / 8000', 'scan() 44 / 145 / 401 ms'], ['BeanDefinition', '始终 105'], ['新加载的类', '始终约 205'], ['成本来自', '每个 .class 文件都要读']], ['成本来自'])),
    step("过滤器。useDefaultFilters = false,只包含名字匹配 .*Svc.* 的类,并排除 .*Svc9.* 的类,包里有 Svc0 到 Svc19 共 20 个 @Component(外加 3 个普通类):留下了 19 个 Bean(svc0 到 svc19,少了 svc9)。名字里有 Svc9 的 Svc9 被排除了,Svc19 里没有连续的 Svc9,所以留下。", t=tl(S(3)), mark=lidx(S(3), '[svc0, svc1'), b=bars([['包里的 @Component', 20, '20'], ['被排除的(Svc9)', 1, '1'], ['留下的 Bean', 19, '19']], 20, cur=[0], mark=[1], done=[2]), kv=KV([['includeFilters', '.*Svc.*'], ['excludeFilters', '.*Svc9.*'], ['留下', '19 个(少了 svc9)'], ['useDefaultFilters', 'false,不再要求有 @Component']], ['留下'])),
    step("默认包的陷阱。@SpringBootApplication 的主类放在默认包(没有 package 声明),组件扫描的范围变成整个 classpath:启动失败,BeanCreationException,原因是 ClassNotFoundException: org.aspectj.lang.annotation.Pointcut(扫到了 Spring 自己的某个 @Configuration 类,它需要 AspectJ,而 classpath 里没有)。同样的主类放进 demo 包:启动成功。", t=tl(S(4)), mark=lidx(S(4), '主类在默认包'), done=lidx(S(4), '主类在 demo 包'), b=bars([['主类在默认包', 0, '启动失败'], ['主类在 demo 包', 1, '启动成功']], 1, mark=[0], done=[1]), kv=KV([['默认包', '扫描范围 = 整个 classpath'], ['失败原因', 'ClassNotFoundException: org.aspectj.lang.annotation.Pointcut'], ['demo 包', '启动成功'], ['建议', '主类一定放在有名字的包里']], ['默认包'])),
    step("两个包里有同名的 @Component(都叫 Svc,默认的 Bean 名字都是 svc)。扫描 demo.p1 和 demo.p2:ConflictingBeanDefinitionException:Annotation-specified bean name 'svc' for bean class [demo.p2.Svc] conflicts with existing, non-compatible bean definition of same name and class [demo.p1.Svc]。要给其中一个起不同的名字(@Component(\"name\"))。", t=tl(S(5)), mark=lidx(S(5), 'ConflictingBeanDefinitionException'), b=bars([['同名的两个 @Component 扫描', 0, '失败(Conflicting...)']], 1, mark=[0]), kv=KV([['默认 Bean 名', '类名首字母小写:svc'], ['两个包里同名', 'ConflictingBeanDefinitionException'], ['办法', '@Component("别的名字")'], ['注意', '扫描的包不同,冲突仍然发生']], ['办法'])),
]
A = mkartx('x9', 9, 'Spring,组件扫描,ComponentScan,类元数据,真实验证,动画演示',
    '实测组件扫描:3000 个 @Component 的 scan() 是 220 ms,但扫描时新加载的类始终是 205 个(类到实例化时才加载);包里每多一个没有注解的普通类也要被读(8000 个比 0 个多花约 357 ms,401 减 44 算出的);主类放在默认包会扫描整个 classpath 导致启动失败;同名 @Component 抛 ConflictingBeanDefinitionException。',
    '组件扫描到底在做什么、代价在哪?它会加载类吗?过滤器怎么用?为什么主类不能放在默认包?两个包里同名的类会怎样?这篇在 Spring Framework 7.0.9 上用脚本生成的类逐项量出来。',
    [('205 个', '扫描 100、1000、3000 个 @Component 时,扫描期间新加载的类数(不随组件数增长)'), ('44 → 401 ms', '同一个包里的普通类从 0 个增加到 8000 个时 scan() 的耗时'), ('默认包', '@SpringBootApplication 的主类放在默认包时启动失败(扫描到 classpath 里的 AspectJ 相关配置)')],
    [('扫描不加载类', '<p>scan() 读 .class 的元数据而不加载类,扫描期间新加载的类数不随组件数增长;类在实例化时才加载。</p>'),
     ('范围决定耗时', '<p>耗时随扫描范围里的类文件数增长,与是否有注解无关。</p>'),
     ('过滤器', '<p>includeFilters / excludeFilters 控制留下哪些类。</p>'),
     ('默认包', '<p>主类放在默认包会让扫描范围变成整个 classpath,启动失败。</p>'),
     ('同名冲突', '<p>不同包里同名的 @Component 默认 Bean 名一样,会抛 ConflictingBeanDefinitionException。</p>')],
    steps,
    [ENV_X + '。类是脚本生成的;第一、二节每个规模各启动 5 个 JVM 取中位数,第一节第 3000 个那行的 scan 耗时每次运行在 200 到 230 ms 之间;第四节用 SpringApplication(WebApplicationType.NONE),类路径里有 spring-boot-starter-webmvc',
     '没有验证:@ComponentScan 的元数据读取是不是用 ASM(只观察到了“扫描时不加载类”这个现象);spring-context-indexer(已经被移除,没有测);多模块、多 jar 同包名时的扫描;默认包失败的完整原因链(只记录了根异常);AOT 模式下组件扫描在构建期完成的情形'],
    '组件扫描')
