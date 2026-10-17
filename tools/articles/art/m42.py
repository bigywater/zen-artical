from lib import *
S = SS('m42')
steps = [
    step("$push 与修饰符:文档 {v: [3, 1]} 先 $push v: 2 变成 [3, 1, 2];$each: [9, 8] 加 $position: 0 插到最前面是 [9, 8, 3, 1, 2];再 $each: [7, 6] 加 $sort: -1、$slice: 4(追加后降序排序,只保留前 4 个)是 [9, 8, 7, 6];$each: [] 加 $slice: -2 只保留最后 2 个,得到 [7, 6]。", t=tl(S(1)), mark=lidx(S(1), '[ 9, 8, 7, 6 ]', '[ 7, 6 ]'), done=lidx(S(1), '[ 3, 1, 2 ]', '[ 9, 8, 3, 1, 2 ]'), kv=KV([['$each + $position', '插到指定位置'], ['$sort + $slice', '追加后排序并截断'], ['$slice: -2', '只留最后两个']], ['$each + $position'])),
    step("$addToSet 已存在的 \"x\" 不修改(modifiedCount 0),$each 加 y、z、w 后是 [x, y, z, w](y 已有,只加了 z 和 w);$pull: {n: {$gt: 7}} 把 [1,5,8,12,3] 变成 [1, 5, 3];$pullAll: {n: [1, 3]} 变成 [5];$pop: {n: 1} 删最后一个、$pop: {n: -1} 删第一个,[1,2,3,4] 剩 [2, 3]。", t=tl(S(2)), mark=lidx(S(2), '[ 1, 5, 3 ]', '[ 5 ]', '[ 2, 3 ]'), done=lidx(S(2), '0 / ["x","y"]', "'z', 'w'"), kv=KV([['$addToSet', '已有就不加'], ['$pull', '按条件删'], ['$pullAll', '按值删'], ['$pop', '1 删尾,-1 删头']], ['$addToSet'])),
    step("位置操作符:数组 g 里有 k 为 a、b、a 的三个元素,值都是 1。查询 {\"g.k\": \"a\"} 加 $set \"g.$.v\": 99 只改第一个匹配的:[a:99, b:1, a:1];$inc \"g.$[].v\": 10 改全部:[a:109, b:11, a:11];$set \"g.$[e].v\": 0 加 arrayFilters [{\"e.k\": \"a\"}] 改所有 k=a 的元素:[a:0, b:11, a:0]。查询里没有数组字段就用 $ 报错:The positional operator did not find the match needed from the query.", t=tl(S(3)), mark=lidx(S(3), "The positional operator", "'a:0', 'b:11', 'a:0'"), done=lidx(S(3), "'a:99', 'b:1', 'a:1'", "'a:109'"), kv=KV([['$', '第一个匹配的元素,需要查询里有数组条件'], ['$[]', '所有元素'], ['$[e] + arrayFilters', '满足条件的所有元素']], ['$[e] + arrayFilters'])),
    step("出错的情形:对字符串字段 $push 报 The field 's' must be an array but is of type string in document {_id: 1};字段不存在时 $push 会创建数组([1]);$pull 一个不存在的值不报错,modifiedCount 是 0。", t=tl(S(4)), mark=lidx(S(4), 'must be an array'), done=lidx(S(4), '[ 1 ]', '  0'), kv=KV([['字段不是数组', '$push 报错'], ['字段缺失', '$push 创建数组'], ['$pull 不存在的值', '不报错,不修改']], ['字段不是数组'])),
    step("$addToSet 比较子文档要求字段顺序一致:数组里已有 {a: 1, b: 2},$addToSet {b: 2, a: 1}(内容相同、字段顺序不同)后数组变成 2 个元素;再 $addToSet {a: 1, b: 2}(顺序相同)仍是 2 个元素,没有再加。", t=tl(S(5)), mark=lidx(S(5), '内容相同,字段顺序不同'), done=lidx(S(5), '顺序相同'), kv=KV([['字段顺序不同', '被当成不同的元素,加进去了'], ['字段顺序相同', '已存在,不再加']], ['字段顺序不同'])),
    step("原子性:8 个线程各向同一个文档的数组 $push 100 次,最终数组长度 800,一个都不丢;而“先读出来、拼上新值再 $set 写回去”的读-改-写做法,同样 8 × 100 次最终只剩 153 个,被并发覆盖了。", t=tl(S(6)), mark=lidx(S(6), '读-改-写'), done=lidx(S(6), '原子的 $push'), b=bars([['原子 $push', 800, '800 / 800'], ['读-改-写', 153, '153 / 800']], 800, mark=[1], done=[0]), kv=KV([['$push', '单文档内原子,不丢'], ['读-改-写', '并发下互相覆盖'], ['结论', '用更新操作符,别读出来再写回']], ['结论'])),
]
A = mkartm('m42', 42, 'MongoDB,数组更新,$push,$pull,$addToSet,位置操作符,arrayFilters,真实验证,动画演示',
    '实测数组更新操作符:$push 的 $each / $position / $sort / $slice,$addToSet / $pull / $pullAll / $pop 的语义;位置操作符 $、$[]、$[<id>] 加 arrayFilters;对非数组字段 $push 的报错;$addToSet 对子文档字段顺序敏感;8 线程各 100 次 $push 全部保留(800),读-改-写只剩 153。',
    '数组字段怎么更新?$push、$pull、$addToSet 各自做什么?$ 和 $[] 又怎么选?这篇逐个验证,并用 8 个线程对比原子 $push 和读-改-写。',
    [('800 对 153', '8 线程各 100 次追加后,原子 $push 与读-改-写最终保留的元素数'), ('$[e]', '配合 arrayFilters 更新所有满足条件的数组元素'), ('2 个元素', '$addToSet 遇到内容相同、字段顺序不同的子文档时数组的元素数')],
    [('$push 的修饰符', '<p><code>$each</code> 一次加多个,<code>$position</code> 指定插入位置,<code>$sort</code> 与 <code>$slice</code> 在追加后排序并截断,常用来保留最近 N 条。</p>'),
     ('删除与去重', '<p><code>$addToSet</code> 有集合语义,<code>$pull</code> 按条件删,<code>$pullAll</code> 按值删,<code>$pop</code> 删头或尾。</p>'),
     ('位置操作符', '<p><code>$</code> 只改查询匹配到的第一个元素(查询里必须有数组条件);<code>$[]</code> 改全部;<code>$[e]</code> 加 <code>arrayFilters</code> 改满足条件的所有元素。</p>'),
     ('出错情形', '<p>对非数组字段 <code>$push</code> 报错;字段缺失时 <code>$push</code> 会创建数组;<code>$pull</code> 不存在的值不报错。</p>'),
     ('子文档与顺序', '<p><code>$addToSet</code> 比较子文档要求字段顺序一致,内容相同但顺序不同的子文档会被当成新元素加进去。</p>'),
     ('原子性', '<p>单个文档内的 <code>$push</code> 是原子的,8 线程 800 次追加一个不丢;读出来再写回去的做法在并发下大量丢失。</p>')],
    steps,
    [ENV_M + '。读-改-写保留的元素数每次运行都不同(这次是 153)',
     '没有验证:$push 到嵌套数组与多层 $[] 的组合;arrayFilters 的多个条件;$addToSet 对嵌套文档字段顺序的处理细节;数组更新在副本集 oplog 里的表示(后面单独一篇);超大数组($push 到几万个元素)的性能'],
    '数组更新操作符')
