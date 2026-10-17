from lib import *
import re
S = SS('u70')
R = J('u70')
rows = [tuple(int(x) for x in m) for m in re.findall(r'^\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+\d+$', R['cmp'], re.M)]
n3, p3, f3, o3 = rows[-1]
steps = [
    step("BinaryHeap 默认是最大堆:依次 push 5,1,8,3,9,2,7 后 peek 是 Some(9);连续 pop 得 [9,8,7,5,3,2,1]。", t=tl(S(1)), done=lidx(S(1), 'peek =', '连续 pop'), kv=KV([['peek', 'Some(9)'], ['连续 pop', '降序']], ['连续 pop'])),
    step("内部数组只满足堆序,不是排序:into_vec 得 [9,8,7,1,3,2,5](父节点不小于子节点),iter() 的遍历顺序同样是这个数组顺序;要有序用 into_sorted_vec(升序 [1,2,3,5,7,8,9])。最小堆用 Reverse 包一层:pop 得 [1,3,5,8]。", t=tl(S(1)), done=lidx(S(1), 'into_vec', 'into_sorted_vec', 'iter()', 'Reverse'), kv=KV([['into_vec / iter()', '堆序,不是有序'], ['into_sorted_vec', '升序'], ['最小堆', 'Reverse']], ['into_vec / iter()'])),
    step("相同优先级的出队顺序不保证先进先出:只按 pri 比较时,pri=2 的任务出队是 id 1,5,3,7(乱序);给比较加上「seq 小者先」(then(o.seq.cmp(&self.seq)))后,得 1,3,5,7 保持先进先出。", t=tl(S(2)), mark=lidx(S(2), '只按 pri'), done=lidx(S(2), 'pri 相同再按'), kv=KV([['只比 pri', '同优先级顺序乱'], ['再比 seq', '同优先级 FIFO']], ['再比 seq'])),
    step("peek_mut:堆顶 10 改成 0,PeekMut 还没离开作用域时堆没有重排;离开作用域(drop)后 peek 变成 Some(8),堆自动重排完成。PeekMut::pop 取出当前堆顶 8,剩下 [0,1,7]。", t=tl(S(3)), done=lidx(S(3), '离开作用域后', 'PeekMut::pop', '剩下'), kv=KV([['修改堆顶', '离开作用域时才重排']], ['修改堆顶'])),
    step(f"比较次数(计数的 Ord):n = {n3} 时,逐个 push 用了 {p3} 次比较(接近线性,约 {p3 / n3:.1f}n),BinaryHeap::from(vec) 一次性堆化只要 {f3} 次(约 {f3 / n3:.1f}n),全部 pop 要 {o3} 次(约 {o3 / n3:.1f}n,接近 n·log2 n = {n3 * 16.6096:.0f} 的量级)。", t=tl(S(4)), done=lidx(S(4), str(n3)), b=bars([['逐个 push', p3, str(p3)], ['from(vec) 堆化', f3, str(f3)], ['全部 pop', o3, str(o3)]], o3, done=[0, 1, 2]), kv=KV([['逐个 push', f'{p3}'], ['from(vec)', f'{f3}'], ['全部 pop', f'{o3}']], ['from(vec)'])),
    step("用 BinaryHeap<Reverse<(dist, node)>> 做 Dijkstra:6 个节点的小图,从节点 0 出发的最短距离是 [0,7,9,20,20,11],堆共 pop 8 次(含过期条目:d > dist[u] 时直接跳过)。", t=tl(S(5)), done=lidx(S(5), '最短距离'), kv=KV([['最短距离', '[0, 7, 9, 20, 20, 11]'], ['pop 次数', '8']], ['最短距离'])),
]
A = mkart('u70', 70, 'Rust,BinaryHeap,优先队列,数据结构,真实验证,动画演示',
    f'用真实运行验证 BinaryHeap:默认最大堆、into_vec/iter 只是堆序数组、Reverse 做最小堆;相同优先级不保证 FIFO,加 seq 修复;peek_mut 离开作用域才重排;比较次数 n={n3} 时 push {p3}、from(vec) {f3}、全部 pop {o3};Dijkstra 实例。',
    'BinaryHeap 是 Rust 里的优先队列。它的遍历顺序为什么不是排序的?相同优先级先进先出吗?批量建堆比逐个 push 省多少比较?这篇用计数的 Ord 把这些都量出来,最后用 Dijkstra 收尾。',
    [('堆序', 'into_vec 与 iter 的顺序只满足堆性质,不是排序'), (f'{f3} 对 {p3}', f'n={n3} 时 from(vec) 对逐个 push 的比较次数'), ('Reverse', '把最大堆变成最小堆的包装类型')],
    [('最大堆与内部数组', None), ('相同优先级', None), ('peek_mut', None), ('比较次数', '<p>用静态计数器在 Ord::cmp 里累加得到;随机数据,release 构建;数字随数据略有波动。</p>'), ('Dijkstra', '<p>排序见<a href="rust-sort-vs-sort-unstable.html">sort 与 sort_unstable</a>。</p>')],
    steps, [ENV_U, '没有验证:push 的最坏复杂度、into_sorted_vec 的比较次数、与 BTreeSet 作优先队列的速度对比、decrease-key(标准库没有这个操作)、append/merge 的复杂度'], 'BinaryHeap')
