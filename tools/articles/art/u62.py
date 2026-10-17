from lib import *
S = SS('u62')
steps = [
    step("只写 v.iter().map(|x| { println!(...); x * 2 }) 而不消费:程序运行后没有任何「闭包执行了」的输出。编译器给出 warning: unused `Map` that must be used,note 写明「iterators are lazy and do nothing unless consumed」。", t=tl(S(1)), mark=lidx(S(1), 'unused `Map`', 'lazy'), done=lidx(S(1), '没有任何'), kv=KV([['只构建 map', '不执行闭包'], ['编译器', 'unused_must_use 警告']], ['只构建 map'])),
    step("(1..=4) → inspect → filter(偶数) → map(×10) → collect:输出是交错的 —— 源产出 1,filter 1 → false;源产出 2,filter 2 → true,map 2 → 20;再回到源产出 3……。每个元素走完整条链才轮到下一个,不存在「先把所有元素 filter 完再 map」。", t=tl(S(2)), done=lidx(S(2), '源      产出', 'filter', 'map'), mark=lidx(S(2), 'map     2', 'map     4'), kv=KV([['执行顺序', '逐个元素穿过整条链'], ['结果', '[20, 40]']], ['执行顺序'])),
    step("短路用计数器验证:filter(%3==0).take(3) 得 [3,6,9],源只产出 9 个(而不是 100 万个);find(==7) 产出 7 个;any(>100) 产出 101 个;take(5).count() 产出 5 个;take_while(<4).sum() 得 6,源产出 4 个(第 4 个用来发现条件不满足)。", t=tl(S(3)), done=lidx(S(3), 'take(3)', 'find', 'any', 'take(5)', 'take_while'), b=bars([['filter+take(3)', 9, '9'], ['find(==7)', 7, '7'], ['any(>100)', 101, '101'], ['take(5).count()', 5, '5'], ['take_while(<4)', 4, '4']], 101, done=[0, 1, 2, 3, 4]), kv=KV([['源共 100 万个', '最多只产出 101 个']], ['源共 100 万个'])),
    step("惰性让无穷序列可用:1u64.. 上 filter(偶数).map(平方).take(5) 得 [4,16,36,64,100]。链本身是嵌套结构体,type_name 显示 Map<Filter<Range<i32>, 闭包>, 闭包>,大小只有 12 字节(Range<i32> 8 字节 + map 捕获的 k 4 字节)。", t=tl(S(4)), done=lidx(S(4), '无穷序列', '类型', 'size_of(这条链)'), kv=KV([['类型', 'Map<Filter<Range<i32>,闭包>,闭包>'], ['大小', '12 字节']], ['类型'])),
    step("在 100 万元素的 Vec 上建 map+filter 链,size_of 只有 16 字节:链只保存迭代状态(一个切片迭代器),不复制元素。", t=tl(S(4)), done=lidx(S(4), '100 万元素'), kv=KV([['100 万元素上的链', '16 字节']], ['100 万元素上的链'])),
    step("代价一:链借用的数据必须活到消费为止 —— 在内层作用域里 v.iter().map(...) 赋给外面的 it,作用域结束后 collect 报 error[E0597]: `v` does not live long enough。", t=tl(S(5)), mark=lidx(S(5), 'error[E0597]'), kv=KV([['链引用的数据', '必须活到消费']], ['链引用的数据'])),
    step("代价二:闭包的副作用在消费时才发生。map 闭包往 log 里 push,建好链时 log 还是空的(此时闭包仍借着 log,不能读),count() 消费之后 log = [1, 2, 3]。", t=tl(S(5)), done=lidx(S(5), '消费之后'), kv=KV([['副作用时机', '消费点才执行']], ['副作用时机'])),
]
A = mkart('u62', 62, 'Rust,Iterator,惰性求值,闭包,真实验证,动画演示',
    '用真实运行验证 Iterator 的惰性:只 map 不消费时闭包不执行(unused_must_use 警告);inspect/filter/map 链逐元素交错执行;take/find/any/take_while 短路时源只产出 9/7/101/5/4 个元素;无穷序列可用;链类型是嵌套结构体、100 万元素上的链仅 16 字节;代价是借用必须活到消费(E0597)与副作用时机延后。',
    '「迭代器是惰性的」这句话该怎么验证?这篇用带 println 的闭包、计数器和 size_of,把「不消费不执行」「逐个元素穿过整条链」「短路后源不再产出」「链只是一个小结构体」都直接测出来。',
    [('0 次', '只调用 map 不消费时闭包的执行次数'), ('9 个', 'filter(%3==0).take(3) 从 100 万个元素的源里实际拉取的个数'), ('16 字节', '在 100 万元素 Vec 上的 map+filter 链的 size_of')],
    [('不消费就不执行', None), ('逐个元素穿过整条链', '<p>Iterator 的基本协议见<a href="rust-iterator-trait.html">Iterator Trait</a>。</p>'), ('短路', None), ('链就是嵌套的结构体', '<p>自定义适配器见<a href="rust-custom-iterator.html">自定义 Iterator</a>。</p>'), ('惰性的代价', None)],
    steps, [ENV_U, '没有验证:并行迭代器(rayon)的惰性、DoubleEndedIterator 的 rev 与惰性、链在 release 下被内联后的汇编(性能放在「Iterator 链的性能」一篇)、try_fold 与短路的细节'], 'Iterator 惰性')
