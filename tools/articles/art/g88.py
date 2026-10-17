from lib import *
S = SS('g88')
steps = [
    step("不同输入形状下的排序耗时(100 万个 int,每格 5 次取最小;列顺序 slices.Sort / sort.Ints / sort.Slice / sort.SliceStable)。随机:60.8 / 61.1 / 102.5 / 334.0 ms;已排序:0.6 / 0.6 / 2.1 / 2.9 ms;逆序:0.9 / 0.9 / 3.2 / 58.9 ms;全部相等:0.6 / 0.6 / 2.0 / 2.9 ms;只有 10 种取值:9.8 / 9.8 / 18.9 / 129.0 ms;管风琴形(先升后降):17.9 / 17.8 / 48.7 / 47.8 ms;已排序但末尾 1% 乱序:37.9 / 37.8 / 89.7 / 17.5 ms。", t=tl(S(1)), done=lidx(S(1), '已排序  ', '逆序', '全部相等', '只有 10 种取值'), mark=lidx(S(1), '随机', '末尾 1% 乱序', '管风琴形'), b=bars([['随机:slices.Sort (ms)', 60.8, '60.8'], ['随机:sort.Slice', 102.5, '102.5'], ['随机:SliceStable', 334.0, '334.0'], ['已排序:slices.Sort', 0.6, '0.6']], 334, mark=[0, 1, 2], done=[3]), kv=KV([['已排序/逆序/全相等', '0.6–0.9 ms:模式被识别,接近线性'], ['随机', 'slices.Sort 60.8 ms,sort.Slice 慢约 1.7 倍,SliceStable 慢约 5.5 倍'], ['几乎有序(末尾 1% 乱序)', '稳定排序 17.5 ms 反而比不稳定的 37.9 ms 快']], ['几乎有序(末尾 1% 乱序)'])),
    step("稳定性:10 万条记录,100 种键。sort.Slice(不稳定)之后,键相等的相邻记录里原始顺序颠倒的有 49962 对(约一半);slices.SortFunc(不稳定)同样 49962 对;sort.SliceStable 与 slices.SortStableFunc 之后都是 0 对。", t=tl(S(2)), mark=lidx(S(2), '49962'), done=lidx(S(2), 'SliceStable', 'SortStableFunc'), b=bars([['sort.Slice:颠倒对数', 49962, '49962'], ['slices.SortFunc', 49962, '49962'], ['sort.SliceStable', 0, '0'], ['slices.SortStableFunc', 0, '0']], 49962, mark=[0, 1], done=[2, 3]), kv=KV([['不稳定排序', '相等键的相对顺序约一半被打乱'], ['稳定排序', '0 对'], ['注意', '“不稳定”不是“偶尔乱”,是几乎一定乱']], ['注意'])),
    step("源码与文档:sort 包的 pdqsort_func 的注释说明 limit 是回退到堆排序前允许的“坏的(很不平衡的)枢轴”个数,函数里 maxInsertion = 12,长度不超过 12 的片段用插入排序,limit 用完调用 heapSort_func;slices 包里 zsortordered.go 的注释:算法基于模式击败快速排序(pdqsort),但没有 BlockQuicksort 的优化;sort.Slice 的文档:排序不保证稳定,相等的元素可能被颠倒,需要稳定排序请用 SliceStable。", t=tl(S(3)), done=lidx(S(3), 'limit is the number', 'maxInsertion', 'heapSort_func'), mark=lidx(S(3), 'pattern-defeating quicksort', 'not guaranteed to be stable'), kv=KV([['短片段', '≤ 12 个元素用插入排序'], ['最坏情况', '坏枢轴用完回退到堆排序'], ['稳定性', '文档明确不保证']], ['最坏情况'])),
]
A = mkartg('g88', 88, 'Go,排序,pdqsort,sort.Slice,slices.Sort,稳定排序,真实验证,动画演示',
    '在 Go 1.27.1 里实测排序:100 万个随机 int,slices.Sort 60.8 ms、sort.Slice 102.5 ms、sort.SliceStable 334.0 ms;已排序、逆序、全相等的输入只要 0.6–0.9 ms(pdqsort 识别模式);几乎有序的输入稳定排序反而更快(17.5 对 37.9 ms);不稳定排序会把一半的相等键对顺序打乱(49962 对),稳定排序是 0 对。',
    'Go 的 sort 和 slices 包用的是 pdqsort,它会识别已排序、逆序、全相等这些模式。这篇用七种输入形状、四种排序函数各排 100 万个整数,看速度差别,再验证“不稳定”到底有多不稳定,并读源码里的 12 个元素阈值与堆排序兜底。',
    [('0.6 ms vs 60.8 ms', 'slices.Sort 排 100 万个已排序的 int 与随机 int'), ('5.5 倍', 'sort.SliceStable 比 slices.Sort 排随机数据慢的倍数(334.0 对 60.8 ms)'), ('49962 对', '10 万条记录、100 种键,不稳定排序后相等键之间顺序被颠倒的相邻对数')],
    [('识别模式,以及选哪个函数', '<p>已排序、逆序、全部相等的输入,<code>slices.Sort</code> 只要 0.6–0.9 ms,接近线性扫描一遍;只有 10 种取值也只要 9.8 ms,约为随机的六分之一。这就是 pdqsort 的“模式击败”。同样排随机数据:<code>slices.Sort</code> 60.8 ms 与 <code>sort.Ints</code> 61.1 ms 一样快,<code>sort.Slice</code> 要 102.5 ms(比较函数通过闭包调用),<code>sort.SliceStable</code> 要 334.0 ms。能用 <code>slices.Sort</code> 就用它。</p>'),
     ('稳定性', '<p>不稳定排序之后,相等键的相邻记录有 49962 对(接近一半)顺序被颠倒;稳定排序是 0 对。需要“同键按原顺序”就必须明确用稳定版本。有意思的是几乎有序的输入(末尾 1% 乱序)稳定排序只要 17.5 ms,比不稳定的 37.9 ms 还快。</p>'),
     ('源码', '<p>pdqsort 的短片段阈值是 12 个元素(用插入排序),“坏枢轴”用完 <code>limit</code> 就回退到堆排序,保证最坏情况不会退化成平方级。<code>slices</code> 的注释说明它没有 BlockQuicksort 的优化。我没有构造专门击败枢轴选择的输入来验证堆排序回退。</p>')],
    steps,
    [ENV_G + '。每种形状 100 万个 int,随机数用固定种子的 math/rand/v2 PCG;每格 5 次取最小;稳定性实验 10 万条 {key, seq} 记录;读过的源码与文档:sort/zsortfunc.go 的 pdqsort_func,slices/zsortordered.go 的注释,go doc sort.Slice',
     '没有验证:字符串或结构体排序、对抗性输入下的堆排序回退、更小(几十个元素)的数据、sort.Sort(Interface 版)的成本、Linux 与其它架构的差别、并行排序'],
    '排序')
