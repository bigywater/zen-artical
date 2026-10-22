from lib import *
S = SS('x32')
steps = [
    step("@Transactional 不生效的场景(CGLIB 代理,方法先 insert 一行再抛异常,表里 0 行 = 生效,1 行 = 没生效)。生效的:(0)对照 public 方法 0 行;(2)package-private 方法 0 行;(3)protected 方法 0 行;(11)经接口类型 Api 调用类上的方法 0 行。没生效的:(1)自调用 1 行;(4)private 方法 1 行;(5)final 方法 1 行;(6)方法里 catch 吞掉异常 1 行;(7)在事务里开线程做 insert,主线程之后抛异常,线程里那一行提交了 1 行;(8)事务管理器绑定 A 库、方法却写 B 库 1 行;(9)MyISAM 表(不支持事务)1 行;(10)自己 new 出来的对象 1 行。在 Spring 7 的 CGLIB 代理下,package-private 和 protected 的 @Transactional 方法是生效的。", t=tl(S(1)), mark=lidx(S(1), '(1)自调用', '(4)private', '(5)final', '(6)方法里', '(7)在 @Transactional', '(8)事务管理器', '(9)表是 MyISAM', '(10)自己 new'), done=lidx(S(1), '(0)对照', '(2)package-private', '(3)protected', '(11)注解写在类'), b=bars([['生效的场景个数', 4, '4:(0)(2)(3)(11)'], ['没生效的场景个数', 8, '8:(1)(4)(5)(6)(7)(8)(9)(10)']], 8, done=[0], mark=[1]), kv=KV([['生效', 'public / package-private / protected、经接口调用'], ['自调用 / private / final', '没生效(代理拦截不到)'], ['吞异常 / 开线程 / 错的事务管理器 / MyISAM', '没生效(事务不知道或管不到)'], ['new 出来的对象', '不是 Spring 管理,没有代理']], ['生效'])),
    step("默认的 JDK 代理(Svc 实现了接口 Api,没有设 proxyTargetClass):Bean 的类是 $Proxy19,getBean(Svc.class) 抛 NoSuchBeanDefinitionException(只能按接口 Api 取);通过接口调用接口里声明的 viaInterface(),抛异常后表里 0 行,事务生效。JDK 代理只能拦截接口里声明的方法,按具体类注入会失败。", t=tl(S(2)), mark=lidx(S(2), 'getBean(Svc.class) → NoSuchBeanDefinitionException'), done=lidx(S(2), '通过接口调用 viaInterface()'), b=bars([['按具体类 Svc 取 Bean', 0, '失败(NoSuchBean)'], ['通过接口调用接口方法:表里剩余行数', 0, '0(回滚了)']], 1, mark=[0], done=[1]), kv=KV([['JDK 代理', '只代理接口里声明的方法'], ['按具体类取', 'NoSuchBeanDefinitionException'], ['接口方法', '事务生效'], ['办法', 'proxyTargetClass = true']], ['办法'])),
]
A = mkartx('x32', 32, 'Spring,事务,失效,自调用,真实验证,动画演示',
    '实测 @Transactional 不生效的场景:自调用、private、final、吞掉异常、事务里开线程、事务管理器绑错数据库、MyISAM 表、new 出来的对象都不回滚;Spring 7 的 CGLIB 代理下 package-private 与 protected 的方法是生效的;默认 JDK 代理只能按接口取 Bean。',
    '@Transactional 加了却没回滚,到底是哪里出了问题?哪些写法会让事务悄悄失效?这篇列出十几个场景,每个都在 Spring Framework 7.0.9 和 MySQL 26.7.0 上跑一遍,看表里是不是真的回滚。',
    [('8 个', '十二个场景里事务没生效的个数(自调用、private、final、吞异常、开线程、错的事务管理器、MyISAM、new 出来的对象)'), ('protected 也生效', 'Spring 7 的 CGLIB 代理下 package-private 和 protected 的 @Transactional 方法回滚了'), ('JDK 代理', '默认代理下 getBean(Svc.class) 抛 NoSuchBeanDefinitionException')],
    [('十二个场景', '<p>生效与不生效的场景逐个对照:不生效的八个各有原因,代理拦不到、事务不知道、事务管不到、没有事务能力。</p>'),
     ('JDK 与 CGLIB', '<p>默认的 JDK 代理只拦截接口方法且只能按接口取 Bean。</p>')],
    steps,
    [ENV_X + '。用不带 Boot 的 Spring Framework 7.0.9 的 @EnableTransactionManagement + DataSourceTransactionManager + 自己起的 MySQL 26.7.0(innodb,以及一张 MyISAM 表);第七个场景里线程里的 insert 用另一个连接,所以主线程抛异常也留下 1 行;“package-private 与 protected 生效”只测了 CGLIB 代理、调用者与目标同包的情形',
     '没有验证:JDK 代理下 protected 与 package-private 方法(接口方法本来都是 public);@Transactional 放在接口方法上时 CGLIB 是否识别;Kotlin 默认 final;JTA 事务管理器;事务内异步(@Async)的更多情形;多数据源 @Transactional(transactionManager = ...) 的写法'],
    '事务失效的场景')
