from lib import *
S = SS('x26')
steps = [
    step("默认的键怎么生成(ConcurrentMapCacheManager)。无参数:键是 SimpleKey []。一个参数 one(7):键就是这个参数本身 7(Integer)。两个参数 two(1, \"x\"):键是 SimpleKey [1, x]。同一个缓存 \"a\" 里无参方法和 one(7) 的结果并存:[7, SimpleKey []]。key 用 SpEL:key=\"#x + ':' + #y\" 得到 2:y,key=\"#root.methodName + #id\" 得到 named3。键冲突:默认键只由参数决定,不含方法名——one(1) 缓存了键 1(值 v1),另一个方法 inner(1) 在同一个缓存 \"a\" 里同样是单个参数 1,它的目标方法执行 0 次,直接拿到了 v1。不同的方法最好用不同的缓存名,或在 key 里带上方法名。", t=tl(S(1)), mark=lidx(S(1), '键冲突'), done=lidx(S(1), '无参数', '一个参数 one(7)', '两个参数 two', 'key="#x', 'key="#root.methodName'), b=bars([['one(1) 的目标方法执行', 1, '1 次'], ['inner(1) 的目标方法执行', 0, '0 次(拿到了 one(1) 的值)'], ['不同方法同缓存同参数是否冲突', 1, '冲突']], 1, done=[0], mark=[1, 2]), kv=KV([['无参数', 'SimpleKey []'], ['一个参数', '参数本身(7)'], ['多个参数', 'SimpleKey [1, x]'], ['不含方法名', '同一缓存、同参数的不同方法会冲突']], ['不含方法名'])),
    step("null 与条件。返回 null 的方法,没有 unless:连续调用 2 次,目标方法只执行 1 次,缓存里键 0 对应的是缓存起来的 null;加 unless=\"#result == null\":2 次调用目标方法执行 2 次(null 不缓存)。condition=\"#id > 10\":id=5 不满足条件,2 次调用执行 2 次(不缓存);id=50 满足,执行 1 次。", t=tl(S(2)), mark=lidx(S(2), '返回 null 的方法'), done=lidx(S(2), 'condition="#id > 10"'), b=bars([['null 结果,无 unless:执行次数', 1, '1(null 被缓存)'], ['null 结果,有 unless:执行次数', 2, '2'], ['condition 不满足(id=5):执行次数', 2, '2'], ['condition 满足(id=50):执行次数', 1, '1']], 2, done=[0, 3], mark=[1, 2]), kv=KV([['默认', 'null 也会被缓存'], ['unless', '按结果排除,例如 null'], ['condition', '按参数决定是否使用缓存'], ['缓存穿透', '缓存 null 可以挡住重复查不存在的键']], ['默认'])),
    step("并发取同一个键。8 个线程同时取同一个 key,加载要 200 ms。没有 sync:目标方法执行了 8 次,全部返回花了 207 ms。sync = true:目标方法只执行 1 次,全部返回 203 ms。默认情况下缓存没命中的多个并发请求会各自加载一遍(缓存击穿),sync = true 让其它线程等第一个加载完。", t=tl(S(3)), mark=lidx(S(3), '没有 sync'), done=lidx(S(3), 'sync = true:8 个线程'), b=bars([['没有 sync:目标方法执行次数', 8, '8'], ['sync = true:目标方法执行次数', 1, '1'], ['没有 sync:总耗时 ms', 207, '207'], ['sync = true:总耗时 ms', 203, '203']], 8, mark=[0], done=[1], cur=[2, 3]), kv=KV([['没有 sync', '8 个线程各加载一次'], ['sync = true', '只有 1 个线程加载,其它等待'], ['总耗时', '207 对 203 ms,差不多(都等一次加载的时间)'], ['保护', '后端只被打 1 次']], ['保护'])),
    step("@CachePut 与 @CacheEvict。one(5) 缓存后调用 @CachePut 的 put(5):方法执行,缓存值被覆盖成 put5。@CacheEvict 之后键清空;allEntries = true 清空整个缓存。方法抛异常时,默认(beforeInvocation = false)缓存没被清掉:evictFails(8) 之后键 [8] 还在;beforeInvocation = true 则在方法执行前就清了,之后键为空。", t=tl(S(4)), mark=lidx(S(4), '方法抛异常时'), done=lidx(S(4), '@CachePut', '@CacheEvict 之后', 'allEntries 之后', 'beforeInvocation = true'), b=bars([['@CachePut 之后的缓存值', 1, 'put5(被覆盖)'], ['evict 方法抛异常后键还在(默认)', 1, '在'], ['beforeInvocation = true 后键还在', 0, '没有了']], 1, done=[0], mark=[1], cur=[2]), kv=KV([['@CachePut', '总会执行方法并覆盖缓存'], ['@CacheEvict', '默认在方法成功后清除'], ['方法抛异常', '默认不清除(缓存和数据库可能不一致)'], ['beforeInvocation', '方法执行前就清除']], ['方法抛异常'])),
    step("缓存的是引用。缓存了一个可变 List:第一次拿到后往里 add 一个元素“被调用者改过”,第二次从缓存里拿到的是 [a, b, 被调用者改过],两次是同一个对象,目标方法只执行了 1 次。ConcurrentMapCacheManager 默认按引用存储,调用方改了返回值就改了缓存里的内容。", t=tl(S(5)), mark=lidx(S(5), '被调用者改过'), b=bars([['两次拿到同一个对象', 1, '是'], ['缓存内容被调用方改动', 1, '是'], ['目标方法执行次数', 1, '1']], 1, mark=[0, 1], done=[2]), kv=KV([['默认存储', '按引用'], ['调用方改返回值', '缓存里的内容跟着变'], ['办法', '缓存不可变对象,或返回副本'], ['外部缓存', 'Redis 等是序列化存的,不会这样']], ['默认存储'])),
    step("自调用。通过 callInner(同一个类里调 inner)连调 2 次:目标方法执行 2 次,缓存没生效;直接调 inner 连调 2 次:目标方法执行 1 次(第 1 次未命中、第 2 次命中)。@Cacheable 也是基于代理,类里的内部调用绕过了缓存(原因见自调用篇)。", t=tl(S(6)), mark=lidx(S(6), '通过 callInner'), b=bars([['经 callInner 调 2 次:执行次数', 2, '2(缓存没生效)'], ['直接调 inner 2 次:执行次数', 1, '1']], 2, mark=[0], done=[1]), kv=KV([['内部调用', '不经过代理,缓存失效'], ['外部调用', '命中缓存'], ['原因', '基于代理'], ['办法', '拆成两个 Bean,见自调用篇']], ['内部调用'])),
]
A = mkartx('x26', 26, 'Spring,Cache,Cacheable,CacheEvict,缓存,真实验证,动画演示',
    '实测 Spring 缓存抽象:默认键只由参数决定(不含方法名,同缓存同参数的不同方法会冲突);null 默认也被缓存;8 个线程并发取同一个键,没有 sync 目标方法执行 8 次、sync = true 只执行 1 次;@CacheEvict 在方法抛异常时默认不清缓存;ConcurrentMapCacheManager 缓存的是引用;自调用不走缓存。',
    '@Cacheable 的键是怎么生成的?会不会不同方法互相冲突?null 会不会被缓存?并发未命中时会不会重复加载?异常时 @CacheEvict 还清不清?这篇在 Spring Framework 7.0.9 上逐项验证。',
    [('8 对 1', '8 个线程并发取同一个键,没有 sync 与 sync = true 下目标方法执行的次数'), ('0 次', '同缓存、同参数的另一个方法 inner(1) 命中了 one(1) 的缓存,它自己的目标方法执行次数'), ('2 次', '经同一个类里的内部调用连调 2 次 @Cacheable 方法,目标方法执行的次数(缓存没生效)')],
    [('键的生成', '<p>默认键由参数决定,不含方法名;可以用 SpEL 自定义。</p>'),
     ('null 与条件', '<p>null 默认也被缓存,unless 与 condition 控制是否缓存。</p>'),
     ('并发加载', '<p>sync = true 让并发未命中的请求只加载一次。</p>'),
     ('更新与清除', '<p>@CachePut 总会执行并覆盖,@CacheEvict 在方法抛异常时默认不清除。</p>'),
     ('引用', '<p>进程内缓存存的是引用,调用方改动会污染缓存。</p>'),
     ('自调用', '<p>内部调用不经过代理,缓存不生效。</p>')],
    steps,
    [ENV_X + '。用不带 Boot 的 Spring Framework 7.0.9 的 @EnableCaching 加 ConcurrentMapCacheManager(进程内);Redis 等外部缓存的序列化与过期(见后面的 Spring Cache + Redis 篇)没有测;并发实验的 200 ms 是 Thread.sleep 模拟的加载时间',
     '没有验证:Caffeine 等其它 CacheManager 的行为;缓存过期;自定义 KeyGenerator;@Caching 组合注解;@CacheConfig;事务与缓存的先后顺序;AOP 代理类型对缓存的影响;sync = true 时的异常传播'],
    '@Cacheable')
