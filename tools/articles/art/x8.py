from lib import *
S = SS('x8')
steps = [
    step("@Bean 方法互相调用:b1() 和 b2() 都在方法体里调用 a()。(a)默认的 @Configuration(full 模式):A 被构造 1 次,b1、b2 持有同一个 A,配置类被 CGLIB 子类替换。(b)proxyBeanMethods = false:A 被构造 3 次(容器里的 A 一个,b1 和 b2 方法体里各 new 一个),b1 和 b2 持有不同的 A。(c)@Component 里写 @Bean 也是同样的 lite 模式,3 次。(d)lite 模式但改用方法参数注入(b1(A a)):1 次,正确。(e)full 模式但 a() 是 static @Bean:3 次,static 方法不会被拦截。(f)final 的 @Configuration 类启动失败:BeanDefinitionParsingException:may not be final。", t=tl(S(1)), mark=lidx(S(1), '(b)@Configuration(proxyBeanMethods', '(c)@Component', '(e)full 模式', '(f)final'), done=lidx(S(1), '(a)@Configuration(默认', '(d)lite 模式但用方法参数注入'), b=bars([['(a)full:A 构造次数', 1, '1'], ['(b)lite:A 构造次数', 3, '3'], ['(c)@Component:A 构造次数', 3, '3'], ['(d)lite + 参数注入:A 构造次数', 1, '1'], ['(e)static @Bean:A 构造次数', 3, '3']], 3, done=[0, 3], mark=[1, 2, 4]), kv=KV([['full 模式', '拦截 @Bean 方法,多次调用得到同一个单例'], ['lite / @Component / static', '方法互调等于普通 Java 调用'], ['安全写法', '用方法参数注入依赖'], ['final 配置类', '启动失败']], ['安全写法'])),
    step("启动代价。300 个 @Configuration 类,每个 5 个 @Bean 方法(共 1500 个 Bean),只改 proxyBeanMethods,各启动 7 个 JVM 取中位数。proxyBeanMethods = true:refresh() 847 ms(826 到 995 ms),新加载 3196 个类;false:475 ms(468 到 497 ms),新加载 2022 个类。BeanDefinition 数都是 1805。full 模式多花约 372 ms(847 减 475 算出的),多加载 1174 个类(3196 减 2022 算出的),比 300 个子类多出很多,多出来的是什么我没有细查。@AutoConfiguration 的元注解里 proxyBeanMethods 是 false,spring-boot-autoconfigure 里登记了 12 个自动配置类。", t=tl(S(2)), mark=lidx(S(2), 'proxyBeanMethods = true(CGLIB 增强)'), done=lidx(S(2), 'proxyBeanMethods = false  |', '@AutoConfiguration 上的元注解'), b=bars([['full(true)refresh ms', 847, '847'], ['lite(false)refresh ms', 475, '475'], ['full 新加载的类', 3196, '3196'], ['lite 新加载的类', 2022, '2022']], 3196, mark=[0, 2], done=[1, 3]), kv=KV([['refresh 耗时', '847 对 475 ms'], ['新加载的类', '3196 对 2022'], ['BeanDefinition', '都是 1805'], ['@AutoConfiguration', 'proxyBeanMethods = false']], ['refresh 耗时'])),
]
A = mkartx('x8', 8, 'Spring,Configuration,CGLIB,proxyBeanMethods,Bean,真实验证,动画演示',
    '实测 @Configuration 的 full 模式与 lite 模式:@Bean 方法互相调用时 full 模式只构造 1 次 A、lite 模式构造 3 次;static @Bean 不被拦截;改用方法参数注入最安全;300 个配置类把 proxyBeanMethods 设成 false,refresh 从 847 ms 降到 475 ms、少加载 1174 个类。',
    '@Configuration 里一个 @Bean 方法调用另一个 @Bean 方法,为什么能拿到同一个单例?把 proxyBeanMethods 设成 false 又会怎样?什么时候会悄悄多创建对象?代价有多大?这篇在 Spring Framework 7.0.9 上逐项量出来。',
    [('1 对 3', '同样的互相调用,full 模式与 lite 模式里 A 被构造的次数'), ('847 → 475 ms', '300 个配置类(1500 个 Bean)把 proxyBeanMethods 设成 false 后 refresh 的中位数耗时'), ('1174 个', 'full 模式比 lite 模式 refresh 期间多加载的类(3196 对 2022)')],
    [('full 与 lite', '<p>full 模式里配置类被 CGLIB 子类替换,@Bean 方法互相调用被拦截成 getBean,单例语义保持;@Component 里的 @Bean、proxyBeanMethods = false、static @Bean 都是普通 Java 调用,会多构造对象,改用方法参数注入最安全。</p>'),
     ('启动代价', '<p>CGLIB 增强要为每个配置类生成并加载子类,300 个配置类多花约 372 ms、多加载 1174 个类。</p>')],
    steps,
    [ENV_X + '。用不带 Boot 的 Spring Framework 7.0.9;耗时是每种配置各启动 7 个 JVM 的中位数,括号里是最小和最大;第二节的类是用脚本生成的 300 个配置类,每类 5 个返回 new Object() 的 @Bean 方法',
     '没有验证:多出来的 1174 个类具体是什么;Boot 里组件扫描到的 @Configuration 与自动配置对 proxyBeanMethods 的不同处理;AOT 模式下配置类的处理;@Bean 方法互调在 Kotlin 或 Groovy 下的行为;proxyBeanMethods 对运行期内存占用的影响'],
    '@Configuration 的 CGLIB 增强')
