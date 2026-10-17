from lib import *
S = SS('m3')
steps = [
    step("同一个集合里放 int32、int64、double、Decimal128 各一个 1,再放一个字符串 \"1\":{v: 1} 查出前四个(int32、int64、double、decimal),字符串 \"1\" 不在其中;$type 依次是 int、long、double、decimal、string;用 NumberLong 的 1 去查结果相同。", t=tl(S(1)), mark=lidx(S(1), "{ _id: 'str', t: 'string' }", 'find({v: 1})'), done=lidx(S(1), "_id: 'int32'", "_id: 'int64'", "_id: 'double'", "_id: 'decimal'"), kv=KV([['数值相等', '1 / Long(1) / 1.0 / Decimal128(1) 互相匹配'], ['字符串 \"1\"', '不匹配'], ['$type', '能看出实际存的类型']], ['数值相等'])),
    step("大整数精度:集合里存了 long 2^53、long 2^53+1、double 2^53。查 9007199254740992 命中 long 2^53 和 double 2^53;用 NumberLong(\"9007199254740993\") 只命中 long 2^53+1,不会因为 double 精度凑巧相等;而在 mongosh 里直接写 JS 数字 9007199254740993,字面量已经变成 9007199254740992,命中的又是前两个。聚合里 $gt 比较 9007199254740992:long 2^53+1 为 true,另外两个为 false。", t=tl(S(2)), mark=lidx(S(2), '// JS 里这个字面量', 'gt: true'), done=lidx(S(2), 'NumberLong("9007199254740993")', 'gt: false'), kv=KV([['服务端比较', 'int64 与 double 按精确数值比'], ['JS 字面量', '超过 2^53 的整数先丢精度'], ['结论', '大整数一定用 NumberLong(\"…\")']], ['结论'])),
    step("Decimal128 与 double:{v: 0.1}(double)只命中存了 double 0.1 的文档,{v: Decimal128(\"0.1\")} 只命中 decimal 0.1;换成 0.5 就两种都命中(0.5 在二进制里是精确的)。0.1 + 0.2:double 是 0.30000000000000004,Decimal128 是 0.3。", t=tl(S(3)), mark=lidx(S(3), "double_sum", "[ 'double 0.1' ]", "[ 'decimal 0.1' ]"), done=lidx(S(3), "'decimal 0.5', 'double 0.5'"), kv=KV([['0.1', 'double 与 Decimal128 不相等'], ['0.5', '二进制精确,两种相等'], ['0.1 + 0.2', 'double 0.30000000000000004,Decimal128 0.3']], ['0.1'])),
    step("唯一索引把 1、1.0、NumberLong(1)、Decimal128(1) 当成同一个值:先插入 {v: 1},再插入 1.0、NumberLong(\"1\")、Decimal128(\"1\") 都报 E11000 duplicate key error ... dup key: { v: 1 };字符串 \"1\" 是另一个类型,插入成功(ok)。", t=tl(S(4)), mark=lidx(S(4), 'E11000'), done=lidx(S(4), '"1"', 'ok'), kv=KV([['唯一索引', '数值相等就算重复'], ['字符串 \"1\"', '不算重复']], ['唯一索引'])),
    step("类型提升:int32 的 2147483647 + 1 在 $add 里变成 Long('2147483648')(long);int32 + double 是 double,int32 + long 是 long,int32 + Decimal128 是 decimal。$group 里的 $sum:2147483647 与 1 相加得 Long('2147483648'),类型是 long;1 与 2 相加得 3,类型仍是 int。", t=tl(S(5)), mark=lidx(S(5), "int_plus_int", 'Long(\'2147483648\')'), done=lidx(S(5), "s: 3, t: 'int'", 'int_plus_decimal', 'int_plus_double'), kv=KV([['溢出', 'int32 → int64'], ['遇到 double', '结果 double'], ['遇到 Decimal128', '结果 decimal'], ['没溢出', '保持 int32']], ['溢出'])),
    step("$type: \"number\" 一次匹配 int、long、double、decimal 四种:命中 int32、int64、double、decimal(字符串 \"1\" 不命中);$type: [\"int\", \"long\"] 只命中 int32 与 int64。在 mongosh 里把 9007199254740993 写成 JS 数字存进去,实际存的是 9007199254740992,$type 是 double;写成 NumberLong(\"9007199254740993\") 才是 long 并保留原值。", t=tl(S(6)), mark=lidx(S(6), 'big: 9007199254740992', "t1: 'double'", "t2: 'long'"), done=lidx(S(6), "'int32', 'int64', 'double', 'decimal'", "'int32', 'int64' ]"), kv=KV([['\"number\"', '四种数值类型的别名'], ['JS 数字', '先变成 double'], ['NumberLong(\"…\")', '保留 64 位整数']], ['JS 数字'])),
]
A = mkartm('m3', 3, 'MongoDB,数字类型,int32,int64,double,Decimal128,真实验证,动画演示',
    '实测数字类型混用:int32、int64、double、Decimal128 的 1 在查询里互相相等;int64 与 double 精确比较;0.1 的 double 与 Decimal128 不相等;唯一索引把四种 1 当成同一个值;$add 与 $sum 的类型提升;mongosh 里超过 2^53 的 JS 数字会悄悄变成 double。',
    '同一个字段里有的存了 int,有的存了 long、double,甚至 Decimal128,查询时算不算相等?大整数会不会丢精度?这篇用真实的 mongod 把相等、比较、唯一索引和聚合的类型提升逐项验证。',
    [('4 种', '{v: 1} 同时命中 int32、int64、double、Decimal128 存的 1'), ('E11000', '唯一索引里已有 1 时,再插入 1.0、NumberLong(1)、Decimal128(1) 都报重复键'), ('2^53', 'mongosh 里 9007199254740993 这个 JS 数字存进去变成 9007199254740992(double)')],
    [('数值相等不看类型', '<p>查询 <code>{v: 1}</code> 会命中 int32、int64、double、Decimal128 存的 1,但不命中字符串 <code>"1"</code>。<code>$type</code> 可以看出实际存的类型。</p>'),
     ('大整数', '<p>服务端比较 int64 与 double 时按精确数值,不会因为 double 精度不够而相等。问题往往出在客户端:mongosh 里写超过 2^53 的 JS 数字,字面量本身已经丢精度,要用 <code>NumberLong("…")</code>。</p>'),
     ('Decimal128 与 double', '<p>0.1 的 double 不等于十进制的 0.1,所以两者互不命中;0.5 在二进制里精确,两种都命中。金额等需要十进制精确的场景用 Decimal128。</p>'),
     ('唯一索引', '<p>唯一索引按数值判断重复,1、1.0、NumberLong(1)、Decimal128(1) 是同一个值;字符串 <code>"1"</code> 是另一个类型。</p>'),
     ('类型提升', '<p>int32 加法溢出自动变 int64;遇到 double 结果是 double,遇到 Decimal128 结果是 decimal;没有溢出时保持 int32。</p>'),
     ('$type 别名', '<p><code>"number"</code> 是 int、long、double、decimal 的别名;也可以传数组列出几种类型。</p>')],
    steps,
    [ENV_M + '。命令来自真实的 mongosh;为避免 JS 数字精度,大整数一律用 NumberLong("…") 写',
     '没有验证:Decimal128 的 NaN、Infinity、-0 的比较;double 的 NaN 在索引与排序里的位置;驱动在其它语言里对整数的默认类型(pymongo 的 int 会按大小选 int32 或 int64,Java 的 Integer / Long 各不同);$avg、$multiply 等其它算术操作符的类型提升;索引键在不同数值类型下的存储形式'],
    '数字类型混用')
