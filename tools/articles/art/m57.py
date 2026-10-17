from lib import *
S = SS('m57')
steps = [
    step("oplog 里的 update 条目不是 $set 命令,也不是整个新文档,而是 diff(o 带 $v: 2):$set {a: 2} 记成 {'diff': {'u': {'a': 2}}};$set {b: 'y', a: 3} 记成 u: {a: 3, b: 'y'};$unset keep 记成 d: {keep: False};$inc a 加 10 记成 u: {a: 13}(记录的是结果值 13,不是增量 10);新增字段 brand_new 记成 i: {brand_new: 1};$rename 记成 d 加 i。", t=tl(S(1)), mark=lidx(S(1), "'a': 13", "'d': {'keep': False}", "'i': {'brand_new': 1}"), done=lidx(S(1), "'u': {'a': 2}", "'a': 3, 'b': 'y'"), kv=KV([['u', '改变或新增后的值'], ['d', '删除的字段 → false'], ['i', '新插入的字段'], ['$inc', '记结果值 13,不是增量 10']], ['$inc'])),
    step("子文档用 s<字段名> 递归:$set \"n.p\": 2 记成 {'sn': {'u': {'p': 2}}};$set \"n.q.r\": 6 两层嵌套记成 {'sn': {'sq': {'u': {'r': 6}}}};同时改子文档和顶层字段记成 {'u': {'a': 4}, 'sn': {'u': {'p': 3}}}。", t=tl(S(2)), mark=lidx(S(2), "'sq'", "'u': {'a': 4}, 'sn'"), done=lidx(S(2), "'sn': {'u': {'p': 2}}"), kv=KV([['s<字段>', '对子文档递归给出 diff'], ['两层嵌套', 'sn → sq → u']], ['s<字段>'])),
    step("数组:$set \"arr.1\": 20 记成 {'sarr': {'a': True, 'u1': 20}}(a: True 表示是数组 diff,u1 是下标 1);$push arr 4 记成 u3: 4(新元素的下标);$push tags $each [c, d] 记成 u2: 'c'、u3: 'd';但 $pop 和 $pull 记成整个数组的替换:u: {arr: [1, 20, 3]}、u: {tags: ['b', 'c', 'd']}。", t=tl(S(3)), mark=lidx(S(3), "'arr': [1, 20, 3]", "'tags': ['b', 'c', 'd']"), done=lidx(S(3), "'a': True, 'u1': 20", "'u3': 4", "'u2': 'c'"), kv=KV([['改元素 / 追加', 'a: True + u<下标>'], ['$pop / $pull', '整个数组替换']], ['$pop / $pull'])),
    step("文档约 100,031 字节、只改一个字段:$inc v 的 oplog 条目 o = {'$v': 2, 'diff': {'u': {'v': 1}}},整个条目只有 165 字节;replace_one 的 oplog 条目要存整个新文档,100,157 字节——差了约 600 倍。", t=tl(S(4)), mark=lidx(S(4), '165 字节', '100,157 字节'), done=lidx(S(4), '文档约 100,031 字节'), b=bars([['$inc 一个字段', 165, '165 字节'], ['replace_one', 100157, '100,157 字节']], 100157, mark=[1], done=[0]), kv=KV([['update + 操作符', '165 字节'], ['replace_one', '100,157 字节'], ['复制量', '小改动用 $set / $inc,别整个替换']], ['复制量'])),
    step("没有实际变化的 update 不写 oplog:把 a 设成它已有的值,matched 1、modified 0,oplog 新增 0 条;update_many 修改 5 个文档,oplog 新增 5 条(每个文档一条,各自的 o2 是 {_id: 0} … {_id: 4}),每条的 diff 都是 u: {v: 1}。", t=tl(S(5)), mark=lidx(S(5), 'oplog 新增 0 条', 'oplog 新增 5 条'), done=lidx(S(5), 'update_many 修改 5 个文档'), kv=KV([['没改动', '不写 oplog'], ['update_many', '每个被修改的文档一条']], ['没改动'])),
    step("聚合管道形式的 update 也是 diff:[{$set: {a: {$add: [\"$a\", 1]}}}] 记成 u: {a: 5};[{$unset: \"b\"}] 记成 d: {b: False};但 [{$replaceWith: {...}}] 把整个文档换掉,oplog 条目是整个新文档 {'_id': 1, 'x': 1, 'y': 2},没有 diff。", t=tl(S(6)), mark=lidx(S(6), "'_id': 1, 'x': 1, 'y': 2", '没有 diff'), done=lidx(S(6), "'u': {'a': 5}", "'d': {'b': False}"), kv=KV([['管道 $set / $unset', 'diff'], ['$replaceWith', '整个文档替换']], ['$replaceWith'])),
]
A = mkartm('m57', 57, 'MongoDB,oplog,update,diff,复制,$set,真实验证,动画演示',
    '实测 $set 一个字段时 oplog 里存的是 diff:{$v: 2, diff: {u: …}},u 是新值、d 是删除、i 是新增、s<字段> 递归子文档与数组;$inc 记结果值;$pop 和 $pull 记整个数组;100 KB 文档改一个字段的 oplog 条目只有 165 字节,replace_one 要 100,157 字节;没有变化的 update 不写 oplog。',
    '$set 一个字段,oplog 里存的是什么?$inc 存增量还是结果?改数组呢?这篇逐个操作符读 local.oplog.rs,看 diff 的记法,再比较 100 KB 文档改一个字段与整个替换的 oplog 大小。',
    [('165 对 100,157 字节', '100 KB 的文档上 $inc 一个字段与 replace_one 的 oplog 条目大小'), ('u: {a: 13}', '$inc a 加 10 在 oplog 里记的是结果值 13,不是增量'), ('0 条', '没有实际变化的 update 写进 oplog 的条数')],
    [('diff 的记法', '<p>update 条目的 <code>o</code> 带 <code>$v: 2</code> 和 <code>diff</code>:<code>u</code> 是新值,<code>d</code> 是删除的字段,<code>i</code> 是新增的字段,<code>s&lt;字段&gt;</code> 对子文档或数组递归。</p>'),
     ('记结果值', '<p><code>$inc</code> 记录的是结果值(13),不是增量(10)。</p>'),
     ('子文档与数组', '<p>嵌套路径逐层 <code>s</code>;数组改元素或追加用 <code>a: true</code> 加 <code>u&lt;下标&gt;</code>;<code>$pop</code> 与 <code>$pull</code> 记整个数组。</p>'),
     ('大小', '<p>只改一个字段,100 KB 文档的 oplog 条目 165 字节;整个替换要 100,157 字节,复制和 oplog 窗口都受影响。</p>'),
     ('没变化与批量', '<p>没有实际修改的 update 不写 oplog;<code>update_many</code> 每个被修改的文档一条。</p>'),
     ('管道 update', '<p>管道形式的 <code>$set</code>、<code>$unset</code> 同样是 diff,<code>$replaceWith</code> 换掉整个文档则整文档替换。</p>')],
    steps,
    [ENV_M + '。单节点副本集;直接读 local.oplog.rs',
     '没有验证:关闭 diff 格式回到 $set 记法(想用隐藏参数 internalQueryEnableLoggingV2OplogEntries 关,在这个版本上该参数不存在);diff 在 secondary 上的应用过程;嵌套数组里子文档的 diff;diff 比整个文档更大时是否回退为整文档(没有构造出这种情形);change stream 的 updateDescription 与 oplog diff 的关系'],
    'oplog 里的 update diff')
