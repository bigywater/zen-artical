from lib import *
S = SS('p47')
steps = [
    step("同一张大表格(每行 <tr> 约 100 字节)分别用 5、25、100 MiB 的文件测,每种方式在独立子进程里跑,峰值内存取 ru_maxrss。整棵树解析(lxml.html.fromstring、lxml.html.parse)的净增内存约是文件大小的 18–19 倍(25 MiB 文件 459 MiB,100 MiB 文件 1122–1649 MiB);iterparse 不清理等同于整棵树(461 MiB / 1599 MiB),而且更慢(100 MiB 要 22.63 秒);iterparse 加 el.clear():25 MiB 净增 56 MiB(2.3 倍),100 MiB 217 MiB(2.2 倍);再加上删掉前面的兄弟:25 MiB 净增 30 MiB(1.2 倍),100 MiB 114 MiB(1.1 倍),耗时 3.04 秒(与整树的 3.05 秒相当)。selectolax Lexbor 整个文件读进内存,净增 1040 MiB,是文件的 10–27 倍;标准库 html.parser 分块 feed 内存很低(25 MiB 文件净增 22 MiB)但慢(25 MiB 要 3.99 秒,是 lxml 整树的 6 倍)。", t=tl(S(1)), done=lidx(S(1), '--- 文件 100 MiB', 'el.clear() + 删掉前面的兄弟'), mark=lidx(S(1), 'fromstring', 'iterparse(tag="tr"),不清理'), b=bars([['100 MiB:整树 净增 MiB', 1122, '1122'], ['100 MiB:iterparse 不清理', 1599, '1599'], ['100 MiB:+ clear()', 217, '217'], ['100 MiB:+ 删前面的兄弟', 114, '114']], 1650, mark=[0, 1], done=[2, 3]), kv=KV([['整棵树', '净增约文件的 11–19 倍'], ['iterparse + clear + 删兄弟', '净增约文件的 1.1 倍'], ['iterparse 不清理', '和整树一样大,还更慢']], ['iterparse + clear + 删兄弟'])),
    step("流式提取的写法:ET.iterparse(path, events=(\"end\",), tag=\"tr\", html=True),每个 <tr> 到达就取出字段,处理完调用 tr.clear() 并删掉前面的兄弟。这个文件没有声明编码,不传 encoding 时 libxml2 当成 Latin-1,\"¥\" 被读成 \"Â¥\",int() 直接报 ValueError;传 encoding=\"utf-8\" 后提取了 211278 行,价格合计 10140834,用时 1.17 秒。", t=tl(S(2)), done=lidx(S(2), '传 encoding="utf-8"'), mark=lidx(S(2), '不传 encoding'), kv=KV([['不传 encoding', '"¥" 变成 "Â¥",int() 报错'], ['encoding="utf-8"', '211278 行,合计 10140834,1.17 秒'], ['关键', 'clear() 加删前面的兄弟']], ['不传 encoding'])),
    step("验证流式的结果与整棵树一致:整棵树(lxml.html.parse 加 xpath)得到 211278 行、价格合计 10140834;流式得到 211278 行、价格合计 10140834;两者一致 True。内存从净增 459 MiB 降到约 30 MiB,结果没有变。", t=tl(S(3)), done=lidx(S(3), '两者一致'), b=bars([['整树:行数', 211278, '211278'], ['流式:行数', 211278, '211278']], 211278, done=[0, 1]), kv=KV([['整棵树', '211278 行,合计 10140834'], ['流式', '211278 行,合计 10140834'], ['结论', '结果一致,内存少一个数量级']], ['结论'])),
]
A = mkartp('p47', 47, '爬虫,流式解析,iterparse,lxml,内存,大页面,html.parser,selectolax,Python,真实验证,动画演示',
    '实测大 HTML 的解析内存:整棵树净增约文件的 11–19 倍(100 MiB 文件 1122–1649 MiB);iterparse 不清理等同整树且更慢(22.63 秒);iterparse 加 clear() 和删前面的兄弟只净增文件的约 1.1 倍(114 MiB),耗时 3.04 秒;给没声明编码的文件要传 encoding,否则「¥」变成「Â¥」。',
    '一个几十上百 MB 的列表页或数据文件,整棵树解析会把内存吃到文件的十几倍。lxml 的 iterparse 可以边读边处理边丢弃,但丢弃的写法有讲究。这篇在 5、25、100 MiB 的文件上量清楚内存、耗时和需要注意的坑。',
    [('1.1 对 11–19 倍', '100 MiB 文件:iterparse 清理并删前面的兄弟,与整棵树解析,各自的净增内存相对文件大小的倍数'), ('22.63 秒', 'iterparse 但不清理时解析 100 MiB 文件的耗时(清理后 3.04 秒)'), ('Â¥', '文件没声明编码、iterparse 又没传 encoding 时,“¥”读出来的样子')],
    [('内存与耗时', '<p>整棵树的内存大约是文件的 11–19 倍(这个数字随结构变化,我没有解释 100 MiB 文件上 fromstring 与 parse 差别为什么有 11.2 对 16.5 倍)。iterparse 如果不清理,元素都还留在树里,和整棵树一样占内存,在 100 MiB 的文件上还慢到 22.63 秒;只 <code>el.clear()</code> 清空了元素内容,空壳仍留在父节点里,净增 217 MiB;再把前面的兄弟从父节点里删掉才只剩 114 MiB。</p>'),
     ('其它选项', '<p>selectolax 的 Lexbor 解析器很快,但要把整个文件读进内存,净增是文件的 10–27 倍。标准库 <code>html.parser</code> 可以分块 feed,内存很低,但在这个测试里慢得多(25 MiB 要 3.99 秒)。</p>'),
     ('编码与正确性', '<p>流式解析的 <code>iterparse</code> 对没有声明编码的 HTML 同样把它当 Latin-1,所以要显式传 <code>encoding="utf-8"</code>(第 16 篇讲过类似的问题)。传了之后,流式提取的行数和价格合计与整棵树完全一致。</p>')],
    steps,
    [ENV_P + '。合成的表格 HTML,每行约 100 字节,5、25、100 MiB 三个文件;每种方式在独立子进程里跑,峰值内存取 resource.getrusage 的 ru_maxrss,净增=峰值减去刚导入库之后的内存;lxml 6.1.1,selectolax 1.0.0(Lexbor 后端,pip 装进临时目录),标准库 html.parser;每项只跑一次,耗时和内存供参考',
     '没有验证:真实网页(结构更复杂、不规则)的内存倍数;嵌套更深或 <tr> 不是直接重复单元时 iterparse 的清理写法;HTTP 下载流直接喂给 iterparse(边下边解析);Windows 或 Linux 上的 ru_maxrss 单位与表现;libxml2 的 push 解析器(etree.HTMLPullParser 等)与 iterparse 的区别;100 MiB 文件上 fromstring 与 parse 内存倍数不同的原因'],
    '大页面流式解析')
