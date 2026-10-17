from lib import *
import re
S = SS('u67')
R = J('u67')
def parse(t):
    m = re.search(r'链 ([\d.]+) ms \| for 循环 ([\d.]+) ms \| 下标 while ([\d.]+) ms \| 中间 Vec ([\d.]+) ms', t); return [float(m.group(i)) for i in range(1, 5)]
rel = parse(R['rel']); dbg = parse(R['dbg']); opt = {k: parse(v) for k, v in R['opt'].items()}
al = re.search(r'惰性链:\s+alloc (\d+) realloc (\d+) 申请字节 (\d+)', R['alloc']); mv = re.search(r'中间 Vec:\s+alloc (\d+) realloc (\d+) 申请字节 (\d+)', R['alloc'])
dr = round(dbg[0] / dbg[1], 1); mr = round(rel[3] / rel[0], 1); o0r = round(opt['0'][0] / opt['0'][1], 1)
def bar(vals, labels): return bars([[l, v, f'{v:g} ms'] for l, v in zip(labels, vals)], max(vals) * 1.1, done=list(range(len(vals))))
L = ['迭代器链', 'for 循环', '下标 while', '中间 Vec']
steps = [
    step(f"release、1000 万个元素(取 5 次最小),求「偶数的平方和」:迭代器链 {rel[0]:g} ms、for 循环 {rel[1]:g} ms、下标 while {rel[2]:g} ms,三者在测量噪声内;而先 collect 成两个中间 Vec 再求和要 {rel[3]:g} ms,约 {mr} 倍。结果均相同。", t=tl(S(1)), done=lidx(S(1), '链'), b=bar(rel, L), kv=KV([['链 vs for', f'{rel[0]:g} vs {rel[1]:g} ms'], ['中间 Vec', f'{rel[3]:g} ms']], ['链 vs for'])),
    step(f"同样的代码不开优化(debug,100 万个元素):迭代器链 {dbg[0]:g} ms,for 循环 {dbg[1]:g} ms,链约慢 {dr} 倍。「零开销」只在优化之后成立。", t=tl(S(2)), mark=lidx(S(2), '链'), b=bar(dbg, L), kv=KV([['debug 下链 vs for', f'{dbg[0]:g} vs {dbg[1]:g} ms(约 {dr}×)']], ['debug 下链 vs for'])),
    step(f"逐级打开优化(1000 万个元素,取 3 次最小):opt-level=0 时链 {opt['0'][0]:g} ms 对 for {opt['0'][1]:g} ms(约 {o0r}×);opt-level=1 时链 {opt['1'][0]:g} ms、for {opt['1'][1]:g} ms;opt-level=2 链 {opt['2'][0]:g} ms、for {opt['2'][1]:g} ms;opt-level=3 链 {opt['3'][0]:g} ms、for {opt['3'][1]:g} ms。从 opt-level=1 起链就追平了 for(各级之间的小差距在噪声范围,只测了一轮)。", t=tl(S(3)), done=lidx(S(3), 'opt-level=1', 'opt-level=2', 'opt-level=3'), mark=lidx(S(3), 'opt-level=0'), b=bars([[f'opt={k} 链', v[0], f'{v[0]:g} ms'] for k, v in opt.items()], opt['0'][0], cur=[0], done=[1, 2, 3]), kv=KV([[f'opt-level={k}', f'链 {v[0]:g} / for {v[1]:g} ms'] for k, v in opt.items()], ['opt-level=0'])),
    step(f"代价在中间 Vec 上:10 万个元素的同一计算,惰性链 alloc {al.group(1)} 次、申请 {al.group(3)} 字节;写成两个中间 Vec,alloc {mv.group(1)} 次 + realloc {mv.group(2)} 次,申请 {mv.group(3)} 字节(filter 的 size_hint 下界为 0,所以 collect 会反复扩容)。", t=tl(S(4)), done=lidx(S(4), '惰性链', '中间 Vec'), b=bars([['惰性链的 alloc+realloc', int(al.group(1)) + int(al.group(2)), str(int(al.group(1)) + int(al.group(2)))], ['中间 Vec 的 alloc+realloc', int(mv.group(1)) + int(mv.group(2)), str(int(mv.group(1)) + int(mv.group(2)))]], int(mv.group(1)) + int(mv.group(2)) + 2, cur=[1], done=[0]), kv=KV([['惰性链', f'{al.group(3)} 字节'], ['中间 Vec', f'{mv.group(3)} 字节']], ['中间 Vec'])),
]
A = mkart('u67', 67, 'Rust,Iterator,性能,零开销抽象,真实验证,动画演示',
    f'用真实测量验证 Iterator 链的性能:release 下 1000 万个元素链 {rel[0]:g} ms 对 for 循环 {rel[1]:g} ms 几乎相同;debug 下链约慢 {dr} 倍;opt-level=1 起追平;写成中间 Vec 要 {rel[3]:g} ms(约 {mr} 倍)且产生 {int(mv.group(1)) + int(mv.group(2))} 次分配。',
    '「迭代器链和手写循环一样快」是 Rust 的著名说法。这篇不信传说:同一个计算写成链、for、下标 while、中间 Vec,在 release、debug 和各级 opt-level 下实测,再数分配次数,看这个说法成立的条件。',
    [(f'{rel[0]:g} 对 {rel[1]:g} ms', 'release 下 1000 万个元素,链 对 for 循环'), (f'{dr}×', 'debug 下链比 for 循环慢的倍数'), (f'{mr}×', 'release 下中间 Vec 版本比链慢的倍数')],
    [('release 下的对比', '<p>惰性与逐元素执行见<a href="rust-iterator-lazy.html">Iterator 的惰性执行</a>。</p>'), ('debug 下的对比', None), ('opt-level', '<p>Cargo 的 profile 配置见<a href="rust-cargo-profile.html">Cargo Profile</a>。</p>'), ('中间 Vec 的代价', '<p>filter 的 size_hint 见<a href="rust-collect-inference.html">collect 类型推断</a>。</p>')],
    steps, [ENV_U + '。每个数字是该进程内 3~5 次的最小值;不同次运行之间有噪声(同样配置下链与 for 可能差 10% 以上)', '没有验证:x86_64 机器、更复杂的链(zip/chain/flat_map)的汇编、字符串迭代、浮点求和(无法重排)、-C target-cpu=native'], 'Iterator 链性能')
