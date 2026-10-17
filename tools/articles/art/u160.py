from lib import *
import re
S = SS('u160')
R = J('u160')
first = R['first']; t1000 = re.search(r'mix_1000\s+time:\s+\[(\S+ \S+) (\S+ \S+) (\S+ \S+)\]', '\n'.join(first)); lo, mid, hi = t1000.groups()
thr = re.search(r'mix_scaling/1000.*\n\s+thrpt:\s+\[(\S+ \S+) (\S+ \S+) (\S+ \S+)\]', '\n'.join(first))
sec = R['second']; third = R['third']
def changes(L): return [m.group(2) + '%' for l in L for m in [re.search(r'\[([+\-−][\d.]+)% ([+\-−][\d.]+)% ([+\-−][\d.]+)%\]', l)] if m and 'p =' in l]
c2 = changes(sec); c3 = changes(third); v2 = [l.strip() for l in sec if 'regressed' in l or 'within noise' in l or 'No change' in l or 'improved' in l]; v3 = [l.strip() for l in third if 'regressed' in l or 'within noise' in l or 'No change' in l or 'improved' in l]
est = R['est']
steps = [
    step(f"Criterion 是第三方基准库(criterion 0.7 从 crates.io 下载,在稳定版上用,Cargo.toml 里 [[bench]] harness = false)。每个基准先预热、再采样 100 次,给出时间的置信区间 [下界 估计 上界]:mix_1000 是 [{lo} {mid} {hi}];带 throughput 的 mix_scaling/1000 还给出吞吐 [{thr.group(1)} {thr.group(2)} {thr.group(3)}]。三个规模 100 / 1000 / 10000 的耗时约 139 ns、1.72 µs、17.6 µs,基本线性。", t=tl(S(1)), done=lidx(S(1), 'mix_1000', 'mix_scaling/100', 'mix_scaling/1000', 'mix_scaling/10000'), mark=lidx(S(1), 'thrpt'), kv=KV([['mix_1000', f'[{lo} {mid} {hi}]'], ['mix_scaling', '100 / 1000 / 10000 → 约线性']], ['mix_1000'])),
    step("Criterion 还会报告离群值:每个基准下方有「Found N outliers among 100 measurements」并按 low/high mild/severe 分类。离群值常来自后台进程或调度抖动,说明单次测量并不可靠,所以它用 100 次采样的分布而不是单个数字。", t=tl(S(1)), mark=lidx(S(1), 'outliers', 'severe'), kv=KV([['离群值', '按 mild / severe 分类报告']], ['离群值'])),
    step(f"不改代码再跑一次,Criterion 把这次与上一次比较。mix_1000 报告 change {c2[0]},判定「{v2[0]}」(p = 0.00 < 0.05);而 mix_scaling/100 与 /1000 的变化只有 {c2[1]}、{c2[2]},被判定为 Change within noise threshold;mix_scaling/10000 又是 {c2[3]},判定 regressed。代码一个字没改,却有两个基准被判为「变差」—— p 值很小只说明「差别不太可能是随机抽样误差」,不能保证是代码造成的,机器当时的状态也会让几个百分点的差别显得统计显著。", t=tl(S(2)), mark=lidx(S(2), 'regressed'), done=lidx(S(2), 'within noise threshold'), kv=KV([['代码没改', '2 个基准被判 regressed(+2.0%、+3.1%)'], ['其余 2 个', 'within noise threshold(<1% 左右)']], ['代码没改'])),
    step(f"换成另一个实现 mix_slow(循环里每轮多一次 black_box)再测:四个基准都判定 regressed,变化是 {'、'.join(c3)}(mix_1000 是 {c3[0]})。这次的差别是真实存在的,只有 3% 到 5%;但对照上一步的「没改代码也 +2%~+3%」,几个百分点以内的结论要靠重复运行和更长的采样时间来确认。", t=tl(S(3)), done=lidx(S(3), 'mix_1000', 'mix_scaling/1000'), mark=lidx(S(3), 'regressed'), kv=KV([['mix_slow', '四个基准都慢约 ' + '、'.join(c3)], ['噪声', '同样量级(+2~3%)']], ['噪声'])),
    step(f"数据保存在 target/criterion/<基准名>/new/estimates.json:mix_1000 的 mean 估计 {est['mean']:,.1f} ns,置信区间 [{est['ci'][0]:,.1f}, {est['ci'][1]:,.1f}] ns,median {est['median']:,.1f} ns,标准差 {est['std']:,.1f} ns。比较两次运行靠的就是这些文件(和上一次的 base 目录);要做长期趋势要自己保存它们。", t=tl(S(4)), done=lidx(S(4), 'estimates.json', 'mix_1000 的 mean'), kv=KV([['mean', f"{est['mean']:,.1f} ns"], ['置信区间', f"[{est['ci'][0]:,.1f}, {est['ci'][1]:,.1f}]"], ['std_dev', f"{est['std']:,.1f} ns"]], ['置信区间'])),
]
A = mkart('u160', 160, 'Rust,Criterion,基准测试,统计,真实验证,动画演示',
    f'下载 criterion 0.7 验证:预热 + 100 次采样给出置信区间(mix_1000 为 [{lo} {mid} {hi}])与吞吐;离群值报告;不改代码再跑一次竟有 2 个基准被判 regressed(纯噪声),另 2 个 within noise threshold;换成 mix_slow 后四个基准 +3~5%;estimates.json 里的 mean / 置信区间 / 标准差。',
    'Criterion 比 #[bench] 多做了什么?它的「性能变差」可信吗?这篇用 criterion 真实跑一个小基准,看置信区间、离群值、与上次比较的 change 和 p 值,并故意不改代码看它会不会误报。',
    [('100 次', '每个基准的采样次数(预热之后)'), ('2 / 4', '代码一个字没改时被判为 regressed 的基准数'), (f'{est["mean"]:,.0f} ns', 'mix_1000 的均值估计(标准差 ' + f'{est["std"]:,.0f} ns)')],
    [('置信区间与离群值', '<p>#[bench] 与基准陷阱见<a href="rust-benchmark.html">Benchmark</a>。criterion 0.7 从 crates.io 下载,这里关闭了默认 feature(没有 HTML 报告与绘图)。</p>'), ('误报', '<p>这些数字是 macOS 上的实测,每次运行不同;不要把「regressed」当作一定是代码引起的。</p>'), ('真实的变化', None), ('保存的数据', None)],
    steps, [ENV_U + '。criterion 0.7(default-features = false,仅 cargo_bench_support)', '没有验证:HTML 报告与 gnuplot/plotters 图表、--save-baseline 与 --baseline 的对比流程、iter_batched 的各种批量模式、async 基准(需要 async 特性)、更长的 measurement-time 对误报的影响、criterion 的 noise_threshold 与 significance_level 的调整'], 'Criterion')
