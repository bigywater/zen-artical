from lib import *
S = SS('m30')
steps = [
    step("数据:300,000 个随机小写字母单词(每 4 个首字母大写),name 上有普通索引,另放 6 个固定词。各正则命中数:/^abc/ 16 个,/^abc$/ 1 个,/abc/ 123 个,/^abc.*/ 16 个,/^(abc|abd)/ 27 个,/^abc/i 23 个。", t=tl(S(1)), mark=lidx(S(1), '/abc/:', '/^abc/i:'), done=lidx(S(1), '/^abc/:', '/^abc$/:'), kv=KV([['/^abc/', '16 个'], ['/abc/', '123 个'], ['/^abc/i', '23 个']], ['/^abc/'])),
    step("前缀锚定的 /^abc/ 走索引范围:检查 17 个键、返回 16 个(1 ms);/^abc.*/ 同样 17 个键;不锚定的 /abc/、不区分大小写的 /^abc/i、^ 后面是 .* 的 /^.*abc/ 都要扫整个索引:检查 300,006 个键,只 FETCH 命中的 123 / 23 / 123 个文档(104 ~ 118 ms)。", t=tl(S(2)), mark=lidx(S(2), 'keysExamined: 300006'), done=lidx(S(2), 'keysExamined: 17'), b=bars([['/^abc/', 17, '17 个键 / 1 ms'], ['/^abc.*/', 17, '17 个键 / 0 ms'], ['/abc/', 300006, '300,006 个键 / 111 ms'], ['/^abc/i', 300006, '300,006 个键 / 104 ms'], ['/^.*abc/', 300006, '300,006 个键 / 118 ms']], 300006, mark=[2, 3, 4], done=[0, 1]), kv=KV([['锚定前缀', '索引范围 [\"abc\", \"abd\")'], ['不锚定 / /i / ^.*', '扫整个索引,在键上匹配正则'], ['FETCH', '只取命中的文档']], ['锚定前缀'])),
    step("indexBounds:/^abc/ 是 [\"abc\", \"abd\") 加一个正则范围;/^abc$/ 也是 [\"abc\", \"abd\");/^(abc|abd)/ 带分支的是整个 [\"\", {});不锚定的 /abc/ 和 /^abc/i 也是 [\"\", {}),再加正则 [/abc/, /abc/]——只有简单的前缀能收窄成字符串范围。", t=tl(S(3)), mark=lidx(S(3), '[\\"\\", {})'), done=lidx(S(3), '[\\"abc\\", \\"abd\\")'), kv=KV([['/^abc/', '[\"abc\", \"abd\")'], ['/^(abc|abd)/', '[\"\", {}) 整个索引'], ['/abc/、/i', '[\"\", {}) 整个索引']], ['/^abc/'])),
    step("大小写不敏感的前缀要换办法:另存一个小写副本 name_lc 并建索引,find({name_lc: /^abc/}) 只检查 24 个键,返回 23 个——与 /^abc/i 的 23 个一致;用带 collation 的索引(strength 2)加 /^abc/i,正则不使用 collation,计划是 COLLSCAN,检查 100,000 个文档。", t=tl(S(4)), mark=lidx(S(4), 'COLLSCAN', 'docsExamined: 100000'), done=lidx(S(4), 'IXSCAN(name_lc_1)', 'keysExamined: 24', '命中 23 个'), kv=KV([['小写副本字段', '前缀范围,24 个键'], ['collation 索引 + 正则', '正则不用 collation,全表']], ['小写副本字段'])),
    step("耗时(9 次中位数):/^abc/ 0.2 ms,/^abc$/ 0.2 ms,{name: \"abc\"} 等值 0.2 ms,name_lc 的 /^abc/ 0.3 ms;不锚定的 /abc/ 100 ms,/^abc/i 98 ms。", t=tl(S(5)), mark=lidx(S(5), '/abc/(不锚定)', '/^abc/i'), done=lidx(S(5), '/^abc/ ', 'name_lc'), b=bars([['/^abc/', 0.2, '0.2 ms'], ['name_lc /^abc/', 0.3, '0.3 ms'], ['/abc/ 不锚定', 100, '100 ms'], ['/^abc/i', 98, '98 ms']], 100, mark=[2, 3], done=[0, 1]), kv=KV([['能用前缀范围', '0.2~0.3 ms'], ['扫整个索引', '约 100 ms']], ['能用前缀范围'])),
    step("$in 里放多个正则:find({name: {$in: [/^abcd/, /^abce/]}}) 每个正则各自是前缀范围,检查 3 个键、返回 2 个;而写成 /^(abcd|abce)/ 的分支正则,indexBounds 是整个 [\"\", {})。", t=tl(S(6)), mark=lidx(S(6), '[\\"\\", {})'), done=lidx(S(6), 'keysExamined: 3', 'nReturned: 2'), kv=KV([['$in: [/^abcd/, /^abce/]', '每个都是前缀范围'], ['/^(abcd|abce)/', '整个索引']], ['$in: [/^abcd/, /^abce/]'])),
]
A = mkartm('m30', 30, 'MongoDB,正则,前缀,索引,regex,真实验证,动画演示',
    '实测正则能否用上前缀索引:/^abc/ 收窄成 ["abc", "abd") 只检查 17 个键;不锚定的 /abc/、/^abc/i、/^.*abc/、带分支的 /^(abc|abd)/ 扫整个索引 300,006 个键(约 100 ms);小写副本字段、$in 里分开写正则是可行办法;正则不使用 collation。',
    '什么样的正则能用上前缀索引?/i 为什么慢?这篇用 30 万个词和 explain 的 indexBounds 逐个验证,并给出大小写不敏感前缀查询的办法。',
    [('17 对 300,006', '/^abc/ 与 /abc/ 检查的索引键数'), ('0.2 对 100 ms', '锚定前缀与不锚定的正则查询耗时'), ('24 个键', '用小写副本字段做不区分大小写的前缀查询检查的键数')],
    [('前缀锚定', '<p>简单的 <code>/^abc/</code> 被收窄成字符串范围 <code>["abc", "abd")</code>,只检查命中的少数键;<code>/^abc.*/</code> 同样。</p>'),
     ('不能收窄的写法', '<p>不锚定的 <code>/abc/</code>、不区分大小写的 <code>/^abc/i</code>、<code>/^.*abc/</code>、带分支的 <code>/^(abc|abd)/</code> 的范围都是整个索引 <code>["", {})</code>,在每个键上匹配正则;只有命中的文档才会 FETCH。</p>'),
     ('indexBounds', '<p>explain 的 <code>indexBounds</code> 里能直接看出范围有没有被收窄成字符串区间。</p>'),
     ('大小写不敏感', '<p>另存一个小写副本字段并建索引,用小写前缀查询,只检查 24 个键;正则不使用 collation,带 collation 的索引帮不上忙。</p>'),
     ('耗时', '<p>能收窄的写法 0.2~0.3 ms,扫整个索引的写法约 100 ms。</p>'),
     ('$in 与分支', '<p>把多个前缀分开写进 <code>$in</code>,每个都是前缀范围(检查 3 个键);写成一个带分支的正则就退化成整个索引。</p>')],
    steps,
    [ENV_M + '。30 万个随机词(固定种子);耗时是 pymongo 的 9 次中位数',
     '没有验证:UTF-8 多字节字符的前缀范围;正则带 m、s、x 选项时的收窄;复合索引上的正则(正则字段不是第一个时);$text 与 Atlas Search 作为替代;$regex 在聚合 $match 里的表现;PCRE 对灾难性回溯的保护'],
    '正则查询与前缀索引')
