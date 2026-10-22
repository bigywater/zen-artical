from lib import *
S = SS('x22')
steps = [
    step("普通的自调用。一个切面拦截带 @Counted 的方法 b(),类里的 a() 内部用 this.b() 调用它。从外部直接调 b():被拦截 1 次。经过 a() 间接调 b():拦截 0 次——切面没有生效。原因:a() 是在目标对象上执行的,this.b() 调用的是目标对象自己,不经过代理;在目标方法里打印 this,AopUtils.isAopProxy(this) 是 false,类是 Svc(不是代理)。", t=tl(S(1)), mark=lidx(S(1), '(a)普通的自调用'), done=lidx(S(1), 'this 是代理?false'), b=bars([['外部直接调 b():拦截次数', 1, '1'], ['经过 a() 间接调 b():拦截次数', 0, '0'], ['目标方法里的 this 是代理', 0, 'false']], 1, done=[0], mark=[1, 2]), kv=KV([['外部调用', '经过代理,被拦截'], ['this.b()', '直接调目标对象,不经过代理'], ['目标里的 this', '是目标对象,不是代理'], ['后果', '切面在内部调用上失效']], ['后果'])),
    step("三种办法都能让内部调用被拦截,拦截次数从 0 变成 1。(b)注入自己的代理(@Autowired @Lazy self,然后 self.b()):外部调用拦截 1 次,经过 a() 也拦截 1 次。(c)AopContext.currentProxy() 配 @EnableAspectJAutoProxy(exposeProxy = true):同样 1 次;没有开 exposeProxy(或者对象根本不是代理)时 AopContext.currentProxy() 抛 IllegalStateException:Cannot find current proxy: Set 'exposeProxy' property on Advised to 'true'。(d)拆成两个 Bean,Other 里调用注入的 svc.b():经过代理,1 次。", t=tl(S(2)), mark=lidx(S(2), '没有 exposeProxy=true'), done=lidx(S(2), '(b)注入自己的代理', '(c)AopContext.currentProxy()', '(d)拆成两个 Bean'), b=bars([['(b)注入自己:经 a() 的拦截次数', 1, '1'], ['(c)AopContext:经 a() 的拦截次数', 1, '1'], ['(d)拆成两个 Bean:经 a() 的拦截次数', 1, '1'], ['(a)普通自调用:经 a() 的拦截次数', 0, '0']], 1, done=[0, 1, 2], mark=[3]), kv=KV([['注入自己', '@Lazy 避免循环依赖'], ['AopContext', '要 exposeProxy = true'], ['拆成两个 Bean', '最干净'], ['AspectJ 织入', '这篇没有测']], ['拆成两个 Bean'])),
    step("代理对象上读 public 字段。通过 CGLIB 代理读 s.field 得到 null,而目标对象里这个字段是“字段值”(直接在目标对象上读才是字段值)。CGLIB 代理是目标类的子类实例,它自己的字段没有被初始化,方法调用被转给目标对象,但字段访问不会。Bean 的类是 Main$Svc·CGLIB,AopUtils.isAopProxy 是 true。通过代理读字段会得到错误的值,要用 getter。", t=tl(S(3)), mark=lidx(S(3), '通过代理读 public 字段 s.field = null'), done=lidx(S(3), '目标对象上读 field = 字段值'), b=bars([['通过代理读字段', 0, 'null'], ['在目标对象上读字段', 1, '字段值']], 1, mark=[0], done=[1]), kv=KV([['代理的字段', '没有被初始化(null)'], ['目标对象的字段', '字段值'], ['方法调用', '转给目标对象'], ['建议', '通过 getter 读,别直接读字段']], ['建议'])),
]
A = mkartx('x22', 22, 'Spring,AOP,自调用,代理,AopContext,真实验证,动画演示',
    '实测自调用失效:同一个类里 a() 调用 this.b(),切面对 b() 拦截 0 次(外部调用才是 1 次),因为 this 是目标对象不是代理;注入自己的代理、AopContext.currentProxy()(要开 exposeProxy)、拆成两个 Bean 都能把拦截次数变成 1;通过 CGLIB 代理读 public 字段得到 null。',
    '为什么同一个类里的方法互相调用,AOP 切面和事务就不生效了?怎么修?代理对象上的字段为什么是 null?这篇在 Spring Framework 7.0.9 上逐项验证。',
    [('0 对 1', '自调用与外部调用时,切面对同一个方法的拦截次数'), ('3 种', '让内部调用被拦截的办法:注入自己、AopContext.currentProxy()、拆成两个 Bean'), ('null', '通过 CGLIB 代理读目标对象 public 字段得到的值')],
    [('为什么失效', '<p>内部调用的 this 是目标对象,不经过代理。</p>'),
     ('怎么修', '<p>注入自己的代理、AopContext.currentProxy() 或者拆成两个 Bean。</p>'),
     ('字段的陷阱', '<p>代理对象的字段不会被初始化,读字段要通过 getter。</p>')],
    steps,
    [ENV_X + '。用不带 Boot 的 Spring Framework 7.0.9 + AspectJ 注解,proxyTargetClass = true;切面用 @annotation(Counted) 拦截;注入自己的写法需要 @Lazy 才能避免构造时循环',
     '没有验证:AspectJ 编译期或加载期织入(能拦截自调用,没有测);JDK 代理下自调用的行为(原理相同,没有单独测);@Transactional 与 @Async 的自调用(见后面的事务与 @Async 篇);Spring 6.2 之后对某些自调用场景的变化(没有查)'],
    '自调用失效')
