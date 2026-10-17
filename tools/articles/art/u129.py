from lib import *
S = SS('u129')
R = J('u129'); on = R['rows']['CARGO_INCREMENTAL=1(dev 默认)']; off = R['rows']['CARGO_INCREMENTAL=0']; ro = R['rel']['release 默认(无增量)']; ri = R['rel']['release + CARGO_INCREMENTAL=1']
steps = [
    step(f"一个 5000 个函数(200 个模块 × 25 个)的 crate,dev profile。增量编译开启(默认):首次全量编译 {on[0]} s;没有改动再 build {on[1]} s;只改动一个函数体后重新编译 {on[2]} s。关闭增量(CARGO_INCREMENTAL=0):首次 {off[0]} s,没改动 {off[1]} s,改一个函数体后仍要 {off[2]} s(每次都等同于全量)。", t=tl(S(1)), done=lidx(S(1), 'CARGO_INCREMENTAL=1', 'CARGO_INCREMENTAL=0'), b=bars([['增量 改一处', on[2], f'{on[2]} s'], ['非增量 改一处', off[2], f'{off[2]} s'], ['增量 首次', on[0], f'{on[0]} s'], ['非增量 首次', off[0], f'{off[0]} s']], max(on[0], off[2]) * 1.1, done=[0, 1, 2, 3]), kv=KV([['增量:改一个函数体', f'{on[2]} s'], ['非增量:改一个函数体', f'{off[2]} s'], ['没有改动', f'{on[1]} s(都一样)']], ['增量:改一个函数体'])),
    step(f"代价:首次编译略慢({on[0]} s 对 {off[0]} s,要额外保存增量状态),并且占磁盘:target/debug/incremental 目录在这个 crate 上有 {on[3]} MB(关闭增量时是 {off[3]} MB)。只改一个函数体的重编是非增量的 {off[2] / on[2]:.1f} 分之一的时间。", t=tl(S(1)), mark=lidx(S(1), 'incremental'), kv=KV([['首次', f'{on[0]} 对 {off[0]} s'], ['磁盘', f'{on[3]} MB 增量目录']], ['磁盘'])),
    step(f"release profile 默认不开增量:改一个函数体后仍要 {ro[1]} s(首次 {ro[0]} s);强制 CARGO_INCREMENTAL=1 后,首次 {ri[0]} s,改一个函数体只要 {ri[1]} s。发布构建默认关掉增量是为了更好的优化与可复现的产物;这里只比较了编译时间,没有比较产物的运行速度。", t=tl(S(2)), done=lidx(S(2), 'release'), b=bars([['release 默认 改一处', ro[1], f'{ro[1]} s'], ['release + 增量 改一处', ri[1], f'{ri[1]} s']], ro[1], cur=[0], done=[1]), kv=KV([['release 默认', f'{ro[1]} s'], ['release + CARGO_INCREMENTAL=1', f'{ri[1]} s']], ['release + CARGO_INCREMENTAL=1'])),
]
A = mkart('u129', 129, 'Rust,增量编译,Cargo,编译时间,真实验证,动画演示',
    f'用 5000 个函数的 crate 验证增量编译:dev 里改一个函数体 {on[2]} s 对关闭增量 {off[2]} s;代价是首次稍慢({on[0]} 对 {off[0]} s)和 {on[3]} MB 的增量目录;release 默认不开增量,改一处 {ro[1]} s,强制开启后 {ri[1]} s。',
    '增量编译到底省多少时间,又付出了什么?为什么 release 默认关着?这篇用一个 5000 个函数的 crate,在 dev 和 release 里分别开关增量,量出重编时间与磁盘占用。',
    [(f'{off[2] / on[2]:.1f}×', 'dev 里改一个函数体,增量对非增量的重编加速比'), (f'{on[3]} MB', '这个 crate 的 target/debug/incremental 大小'), (f'{ro[1]} → {ri[1]} s', 'release 里改一处:默认与强制开启增量')],
    [('增量开与关', '<p>各个编译阶段见<a href="rust-compile-stages.html">Rust 编译阶段</a>;构建配置见<a href="rust-cargo-profile.html">Cargo Profile</a>。</p>'), ('release 与增量', '<p>数字是本机的实测(只改动一个模块里的一个函数体,3 次或 2 次取最小);修改被很多地方依赖的类型定义时,增量的收益会小得多,没有测。</p>')],
    steps, [ENV_U + '。crate 是生成的 5000 个小函数,没有外部依赖', '没有验证:修改公共类型或 trait 定义时的重编时间、增量编译产物与全量产物的运行速度差异、rust-analyzer 与 cargo 共用增量缓存的情况、sccache 的效果、-Z threads 并行前端'], '增量编译')
