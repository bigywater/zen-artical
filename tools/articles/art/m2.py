from lib import *
S = SS('m2')
steps = [
    step("同一个字段 v 里放 16 种类型的值(再加一个没有 v 的文档),升序排序的结果依次是:MinKey、null、字段缺失(与 null 并列)、数字(-1 的 long、5、5.5 的 double,不分具体数值类型)、字符串 \"a\"、\"b\"、对象、BinData、ObjectId、false、true、Date、Timestamp、正则、MaxKey。", t=tl(S(1)), mark=lidx(S(1), "'MinKey'", "'MaxKey'"), done=lidx(S(1), 'string', 'object', 'ObjectId', 'Date'), b=bars([['MinKey', 1, '最小'], ['null / 缺失', 2, ''], ['数字', 3, 'int / long / double / decimal'], ['字符串', 4, ''], ['对象', 5, ''], ['BinData → ObjectId', 6, ''], ['布尔 → 日期 → Timestamp → 正则', 7, ''], ['MaxKey', 8, '最大']], 8, mark=[0, 7], done=[1, 2, 3]), kv=KV([['顺序', 'MinKey < null < 数字 < 字符串 < 对象 < 数组 < BinData < ObjectId < 布尔 < 日期 < Timestamp < 正则 < MaxKey'], ['数字', '不区分 int / long / double / decimal']], ['顺序'])),
    step("比较运算只在同一类型括号内匹配:{v: {$gt: 5}} 只返回 number 5.5(字符串、日期等虽然排在数字后面也不返回);{v: {$lt: \"b\"}} 只返回字符串 \"a\"。MinKey 和 MaxKey 是例外——{v: {$gte: MinKey()}} 与 {v: {$lte: MaxKey()}} 都命中全部 17 个文档(包括没有 v 的那个)。", t=tl(S(2)), mark=lidx(S(2), '17 / 17'), done=lidx(S(2), "'number 5.5 (double)'", "'string \"a\"'"), kv=KV([['$gt / $lt', '只比较同一类型括号内的值'], ['MinKey / MaxKey', '例外:命中所有文档']], ['MinKey / MaxKey'])),
    step("null 与字段缺失:{v: null} 同时匹配值为 null 的文档和没有 v 的文档;{v: {$exists: false}} 只匹配缺失的;{v: {$type: \"null\"}} 只匹配真正存了 null 的;{v: {$in: [null]}} 与 {v: null} 一样匹配两种。", t=tl(S(3)), mark=lidx(S(3), "$exists", '$type'), done=lidx(S(3), '{v: null}', '$in'), kv=KV([['{v: null}', 'null 或缺失'], ['$exists: false', '只有缺失'], ['$type: \"null\"', '只有 null']], ['{v: null}'])),
    step("数组参与排序:数据是 [5,1]、[3]、[9,0]、2。升序用数组里最小的元素:[9,0](最小元素 0)、[5,1](1)、2、[3](3);降序用最大的元素:[9,0](9)、[5,1](5)、[3](3)、2。比较的是元素,不是整个数组。", t=tl(S(4)), mark=lidx(S(4), "'[9,0]'"), done=lidx(S(4), 'sort({v: 1})', 'sort({v: -1})'), kv=KV([['升序', '用数组里最小的元素'], ['降序', '用数组里最大的元素']], ['升序'])),
    step("子文档按字段逐个比较(类型、字段名、值):排序结果依次是 {}、{a:1}、{a:1,b:1}、{a:2}、{b:1}、{b:1,a:1}——先比第一个字段的名字,a 排在 b 前面,同名再比值;{b:1} 与 {b:1,a:1} 是不同的文档,字段多的排后面。", t=tl(S(5)), mark=lidx(S(5), "'{\"b\":1,\"a\":1}'", "'{\"b\":1}'"), done=lidx(S(5), "'{}'", "'{\"a\":1}'", "'{\"a\":1,\"b\":1}'", "'{\"a\":2}'"), kv=KV([['比较方式', '逐个字段:类型、字段名、值'], ['顺序', '字段顺序不同就是不同的文档']], ['比较方式'])),
    step("$cmp 用同一套顺序比较任意两个值:数字对字符串 -1、字符串对对象 -1、对象对数组 -1、数组对布尔 -1、null 对 0 是 -1;int 的 1 对 double 1.5 是 -1,long 的 2 对 1.5 是 1(数值类型不同也按数值大小比较)。", t=tl(S(6)), mark=lidx(S(6), 'long_vs_double', 'int_vs_double'), done=lidx(S(6), 'number_vs_string', 'string_vs_object', 'object_vs_array', 'array_vs_bool', 'null_vs_number'), kv=KV([['$cmp', '返回 -1 / 0 / 1'], ['跨类型', '按类型顺序'], ['数值类型不同', '按数值大小']], ['$cmp'])),
]
A = mkartm('m2', 2, 'MongoDB,BSON,比较顺序,排序,类型括号,真实验证,动画演示',
    '实测 BSON 跨类型的比较顺序:升序排序依次是 MinKey、null、数字、字符串、对象、BinData、ObjectId、布尔、日期、Timestamp、正则、MaxKey;比较运算只在同一类型括号内匹配,null 与字段缺失的差别,数组按最小或最大元素排序,子文档按字段逐个比较。',
    '一个字段里混着数字、字符串、日期、null,排序谁在前?{$gt: 5} 会不会把字符串也查出来?这篇把 16 种类型放进同一个字段,用 sort、比较运算和 $cmp 逐个验证。',
    [('16 种', '同一字段里混放的类型数;升序依次是 MinKey、null、数字、字符串、对象、BinData、ObjectId、布尔、日期、Timestamp、正则、MaxKey'), ('只返回 1 个', '{v: {$gt: 5}} 在 17 个混合类型文档里只匹配 5.5 一个数字'), ('17 / 17', '{v: {$gte: MinKey()}} 命中全部文档,包括没有 v 字段的')],
    [('跨类型排序', '<p>MongoDB 对不同类型有固定的排序:MinKey &lt; null &lt; 数字 &lt; 字符串 &lt; 对象 &lt; 数组 &lt; BinData &lt; ObjectId &lt; 布尔 &lt; 日期 &lt; Timestamp &lt; 正则 &lt; MaxKey。数字不区分 int、long、double、decimal,字段缺失与 null 并列。</p>'),
     ('类型括号', '<p><code>$gt</code>、<code>$lt</code> 只在同一类型括号内比较,所以 <code>{v: {$gt: 5}}</code> 不会返回字符串或日期,即使它们排在数字后面。MinKey 和 MaxKey 是例外。</p>'),
     ('null 与缺失', '<p><code>{v: null}</code> 匹配 null 和缺失两种;要区分用 <code>$exists</code> 或 <code>$type</code>。</p>'),
     ('数组排序', '<p>升序排序时数组用最小的元素参与比较,降序用最大的元素,所以 <code>[9,0]</code> 升序排最前、降序也排最前。</p>'),
     ('子文档', '<p>子文档逐个字段比较类型、字段名、值,字段顺序不同的两个子文档不相等,也排在不同的位置。</p>'),
     ('$cmp', '<p>聚合里的 <code>$cmp</code> 使用同一套顺序,可以用来快速验证任意两个值谁大;数值类型不同按数值大小比较。</p>')],
    steps,
    [ENV_M + '。每个类型只放了一两个样本值,排序结果用 mongosh 取回;文档的插入顺序打乱过',
     '没有验证:字符串在不同 collation 下的比较(见后面的 collation 一篇);数组整体比较(不带排序)的细节;BinData 不同子类型和长度的排序;Symbol、JavaScript、DBPointer 等已弃用类型;Decimal128 的 NaN 与 Infinity 的位置;索引键的比较是否与此完全一致'],
    '跨类型比较顺序')
