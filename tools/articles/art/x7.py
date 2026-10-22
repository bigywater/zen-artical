from lib import *
S = SS('x7')
steps = [
    step("单例里注入 prototype。(a)直接 @Autowired Proto:连续 3 次 use() 拿到的 id 都是 1,是创建 Naive 时注入的那一个,prototype 只在注入那一刻创建了一次。(b)ObjectProvider<Proto>.getObject():连续 3 次得到 2、3、4,每次都是新对象;直接 getBean(Proto) 两次得到 5、6。", t=tl(S(1)), mark=lidx(S(1), '(a) 单例 Naive'), done=lidx(S(1), '(b) ObjectProvider'), b=bars([['(a)直接注入:3 次 use() 的不同 id 数', 1, '1(1、1、1)'], ['(b)ObjectProvider:3 次的不同 id 数', 3, '3(2、3、4)']], 3, mark=[0], done=[1]), kv=KV([['直接注入', '3 次同一个对象,id 都是 1'], ['ObjectProvider', '每次新对象,2、3、4'], ['getBean', '5、6,也是新对象'], ['原因', '单例只在创建时注入一次']], ['直接注入'])),
    step("另外两种办法。(c)@Lookup:Spring 生成 CGLIB 子类(Main$LookupBean$$…)重写抽象方法,连续 3 次 use() 得到 1、2、3,每次一个新的 prototype。(d)prototype 加 scoped proxy(TARGET_CLASS):注入的是代理,连续 3 次 p.id() 得到 1、2、3,每一次方法调用都创建了新的目标对象,创建了 3 个。scoped proxy 加 prototype 意味着每个方法调用换一个对象,同一个业务流程里多次调用就拿不到同一个状态。", t=tl(S(2)), mark=lidx(S(2), '(d) prototype + scoped proxy'), done=lidx(S(2), '(c) @Lookup'), b=bars([['(c)@Lookup:3 次不同 id', 3, '3'], ['(d)scoped proxy:3 次方法调用创建的目标对象', 3, '3(made=3)']], 3, done=[0], mark=[1]), kv=KV([['@Lookup', 'CGLIB 子类重写方法,每次新对象'], ['scoped proxy + prototype', '每个方法调用换一个目标对象'], ['注入的是', '代理(AopUtils.isAopProxy = true)'], ['坑', '一个流程里多次调用拿不到同一个状态']], ['坑'])),
    step("自定义 thread 作用域(SimpleThreadScope)加 scoped proxy(INTERFACES)。单例 Holder 里的 ctx 是代理,实现了 ScopedObject。主线程连续 3 次 id 都是 1。另外 3 个线程各调用 2 次,拿到的 id 排序后是 2、2、3、3、4、4:每个线程内部稳定,线程之间不同;目标对象一共创建了 4 个(主线程 1 个、3 个线程各 1 个)。这才是单例持有“按线程变化的依赖”的正确形态。", t=tl(S(3)), mark=lidx(S(3), '另外 3 个线程各调用 2 次'), done=lidx(S(3), '单例 Holder 里的 ctx 是代理', '主线程连续 3 次 id'), b=bars([['主线程 3 次的不同 id', 1, '1'], ['另外 3 个线程拿到的不同 id', 3, '3(各 1 个)'], ['目标对象总数', 4, '4']], 4, done=[0], cur=[1], mark=[2]), kv=KV([['单例持有', '代理(ScopedObject)'], ['同一线程', '同一个目标对象'], ['不同线程', '不同的目标对象'], ['目标总数', '4(1 个主线程 + 3 个线程)']], ['同一线程'])),
    step("proxyMode=INTERFACES 的代理只实现接口,按具体类 ThreadCtx 注入:NoSuchBeanDefinitionException:No qualifying bean of type 'ThreadCtx' available。要按具体类注入就用 TARGET_CLASS(这里没有再验证)。", t=tl(S(4)), mark=lidx(S(4), 'proxyMode=INTERFACES'), b=bars([['按接口 Ctx 注入', 1, '成功(第三节)'], ['按具体类 ThreadCtx 注入', 0, '失败(NoSuchBean)']], 1, done=[0], mark=[1]), kv=KV([['INTERFACES', '代理只实现接口'], ['按具体类注入', 'NoSuchBeanDefinitionException'], ['想按类注入', '用 TARGET_CLASS'], ['TARGET_CLASS', '这篇没有验证它在 thread 作用域下的行为']], ['INTERFACES'])),
    step("单例的线程安全。一个单例里有 int 字段和 AtomicInteger,8 个线程各调用 200000 次,期望 1600000。int 字段 n++ 三次运行分别得到 407345、504079、581252,丢了 1192655、1095921、1018748 次;AtomicInteger 三次都是 1600000。单例被所有线程共享,里面的可变字段要自己保证线程安全。", t=tl(S(5)), mark=lidx(S(5), '期望 1600000'), b=bars([['期望', 1600000, '1600000'], ['int 字段 n++(第 1 次)', 407345, '407345'], ['int 字段 n++(第 2 次)', 504079, '504079'], ['int 字段 n++(第 3 次)', 581252, '581252'], ['AtomicInteger', 1600000, '1600000']], 1600000, done=[0, 4], mark=[1, 2, 3]), kv=KV([['int 字段 n++', '丢了约 110 万到 120 万次'], ['AtomicInteger', '1600000,不丢'], ['原因', '单例被所有线程共享'], ['结论', '单例里不要放可变状态']], ['int 字段 n++'])),
]
A = mkartx('x7', 7, 'Spring,作用域,prototype,scoped proxy,单例线程安全,真实验证,动画演示',
    '实测作用域:单例里直接注入 prototype 只在创建时注入一次(id 恒为 1);ObjectProvider、@Lookup 每次拿新对象;prototype 加 scoped proxy 是每次方法调用换一个对象;thread 作用域加 scoped proxy 才是按线程稳定;单例里的 int 字段 8 线程各 200000 次 n++ 丢了 100 万次以上。',
    '单例里注入 prototype 为什么拿到的总是同一个?ObjectProvider、@Lookup、scoped proxy 各自怎么解决?scoped proxy 的代理是什么样?单例里放可变状态到底会怎样?这篇在 Spring Framework 7.0.9 上逐项量出来。',
    [('1,1,1', '单例里直接 @Autowired 一个 prototype,连续三次拿到的 id'), ('4 个', 'thread 作用域加 scoped proxy 时,主线程加 3 个线程一共创建的目标对象数'), ('约 110 万', '单例里 int 字段 n++,8 线程各 200000 次(期望 1600000)平均丢失的次数')],
    [('直接注入 prototype', '<p>单例只在创建时注入一次,之后一直是同一个对象。</p>'),
     ('另外三种办法', '<p>ObjectProvider 和 @Lookup 每次新对象;prototype 加 scoped proxy 是每次方法调用换对象。</p>'),
     ('thread 作用域', '<p>scoped proxy 把按线程变化的依赖变成稳定的引用:同线程同目标,不同线程不同目标。</p>'),
     ('代理类型', '<p>INTERFACES 的代理不能按具体类注入。</p>'),
     ('单例的线程安全', '<p>单例被所有线程共享,可变字段会丢更新。</p>')],
    steps,
    [ENV_X + '。用不带 Boot 的 Spring Framework 7.0.9;thread 作用域用 Spring 自带的 SimpleThreadScope(它不会在线程结束时销毁目标对象);request / session 作用域需要 Web 环境,这篇没有测;int 字段丢失次数每次运行不同,三次分别是 1192655、1095921、1018748',
     '没有验证:request / session / application 作用域;scoped proxy 的 TARGET_CLASS 在 thread 作用域下的行为;@Lookup 在 @Bean 方法返回的对象上是否生效;SimpleThreadScope 的内存泄漏风险(线程池线程不退出时目标对象一直不释放);Boot 里 @RefreshScope 的作用域(见后面的 Cloud 篇)'],
    '作用域与单例的状态')
