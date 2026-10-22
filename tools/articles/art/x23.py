from lib import *
S = SS('x23')
steps = [
    step("不同种类的方法通过 CGLIB 代理调用(Svc 只有一个带参构造器 Svc(String name),构造时 name = 真名)。open()(普通 public 方法):返回 open:真名,切面拦截 1 次。locked()(final 方法):返回 locked:null,切面拦截 0 次——final 方法不能被子类重写,代理没法拦截,于是在代理对象自己身上执行,而代理对象的字段没有初始化,所以读到 name 是 null。callHidden()(里面调 private 的 hidden()):返回 hidden:真名,切面只拦截了 callHidden 这 1 次,private 方法在目标对象里被正常调用。static 的 stat() 拦截 0 次。Svc 的构造器只被调用了 1 次(目标对象的那一次)。", t=tl(S(1)), mark=lidx(S(1), 'locked()(final 方法)', 'static stat()'), done=lidx(S(1), 'open()(普通 public 方法)', 'callHidden()', 'Svc.ctor'), b=bars([['open():拦截次数', 1, '1'], ['locked()(final):拦截次数', 0, '0,返回 locked:null'], ['callHidden():拦截次数', 1, '1'], ['static stat():拦截次数', 0, '0'], ['Svc 构造器调用次数', 1, '1']], 1, done=[0, 2, 4], mark=[1, 3]), kv=KV([['final 方法', '不拦截,在代理上执行,字段是 null'], ['private 方法', '在目标里正常执行,不单独拦截'], ['static 方法', '不拦截'], ['构造器', '只调用 1 次(目标对象)']], ['final 方法'])),
    step("构造器被调用几次。Plain 有 public 无参构造器,被切面匹配变成代理:默认(Spring 用 Objenesis 绕过构造器创建代理实例)构造器只被调用 1 次;设置 -Dspring.objenesis.ignore=true(不用 Objenesis,走构造器)构造器被调用 2 次(目标对象一次、代理对象一次)。构造器里有副作用(连接、线程、日志)的类,在不用 Objenesis 时会执行两遍。", t=tl(S(2)), mark=lidx(S(2), 'spring.objenesis.ignore = true'), done=lidx(S(2), 'spring.objenesis.ignore = (没设)'), b=bars([['默认:构造器调用次数', 1, '1'], ['objenesis.ignore=true:构造器调用次数', 2, '2']], 2, done=[0], mark=[1]), kv=KV([['默认', 'Objenesis 绕过构造器,调用 1 次'], ['spring.objenesis.ignore=true', '构造器调用 2 次'], ['多出来的那次', '代理对象的构造'], ['风险', '构造器有副作用时会重复']], ['风险'])),
    step("只有带参构造器的类,能不能被代理。默认(Objenesis):成功,构造器被调用 1 次。关掉 Objenesis(spring.objenesis.ignore=true):启动失败:BeanCreationException,原因是 NoSuchMethodException:demo.Main$Svc$$SpringCGLIB$$0.<init>(),因为生成的 CGLIB 子类找不到可用的构造器。只有带参构造器的类能被代理,是靠 Objenesis。", t=tl(S(3)), mark=lidx(S(3), 'NoSuchMethodException'), done=lidx(S(3), '成功,构造器被调用 1 次'), b=bars([['默认:只有带参构造器的类能代理', 1, '能'], ['关掉 Objenesis:能代理', 0, '不能(NoSuchMethodException)']], 1, done=[0], mark=[1]), kv=KV([['默认', 'Objenesis,成功'], ['关掉 Objenesis', 'NoSuchMethodException: <init>()'], ['异常', 'BeanCreationException'], ['含义', '带参构造器的类能代理靠 Objenesis']], ['含义'])),
    step("final 类被切面匹配。Fin 是 final 类,切面匹配它:启动失败,BeanCreationException,原因是 IllegalArgumentException:Cannot subclass final class demo.Main$Fin(消息里还提示了 Common causes of this problem include using a final class)。CGLIB 要继承目标类,final 类不能被代理。", t=tl(S(4)), mark=lidx(S(4), 'Cannot subclass final class'), b=bars([['final 类被代理', 0, '不能(IllegalArgumentException)']], 1, mark=[0]), kv=KV([['final 类', '不能继承,不能被 CGLIB 代理'], ['异常', 'BeanCreationException ← IllegalArgumentException'], ['消息', 'Cannot subclass final class'], ['办法', '去掉 final,或用接口加 JDK 代理']], ['办法'])),
]
A = mkartx('x23', 23, 'Spring,AOP,CGLIB,final,Objenesis,真实验证,动画演示',
    '实测 CGLIB 代理的限制:final 方法不被拦截而且在字段未初始化的代理上执行(读到 null);private 与 static 方法不单独拦截;靠 Objenesis 构造器只调用 1 次(关掉后调用 2 次,只有带参构造器的类会失败);final 类抛 Cannot subclass final class。',
    'CGLIB 代理有哪些不能做的事?final 方法为什么读到 null?构造器会不会被调用两次?final 类能不能被代理?这篇在 Spring Framework 7.0.9 上逐项验证。',
    [('locked:null', '通过 CGLIB 代理调用 final 方法时读到的字段值(目标对象里是真名)'), ('1 对 2', '默认(Objenesis)与 -Dspring.objenesis.ignore=true 下,构造器被调用的次数'), ('不能继承', 'final 类被切面匹配时的错误:Cannot subclass final class')],
    [('各种方法', '<p>final 方法不被拦截且在代理自身上执行;private 和 static 方法不单独拦截。</p>'),
     ('构造器', '<p>默认靠 Objenesis 不调用构造器,关掉后会调用两次。</p>'),
     ('只有带参构造器', '<p>能被代理是靠 Objenesis;关掉后找不到无参构造器就失败。</p>'),
     ('final 类', '<p>不能继承,无法代理。</p>')],
    steps,
    [ENV_X + '。用不带 Boot 的 Spring Framework 7.0.9 + AspectJ 注解,proxyTargetClass = true;spring.objenesis.ignore 通过 JVM 系统属性设置',
     '没有验证:Spring 在 final 方法上是否打印警告(没有看到 WARN 日志);Java 记录(record)与 sealed 类的代理;protected 方法与不同包下包可见方法的拦截;Kotlin 默认 final 类的 allopen 插件;GraalVM native image 下的 CGLIB 限制'],
    'CGLIB 代理的限制')
