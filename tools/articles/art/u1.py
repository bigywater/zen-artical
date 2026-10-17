from lib import *
R = J('u1')
S = SS('u1')
steps = [
    step("cargo new hello 生成一个最小的二进制项目:Cargo.toml(包名、版本、edition = \"2024\"、空的 [dependencies])、src/main.rs(一个 println! 的 main)、.gitignore(只有一行 /target)和一个 .git 仓库。没有别的了:没有 Cargo.lock,没有 target/。", t=tl(S(1)), done=[0], kv=KV([['文件', 'Cargo.toml、src/main.rs、.gitignore、.git'], ['edition', '2024']], ['文件'])),
    step(f"第一次 cargo build 输出 Compiling → Finished `dev` profile [unoptimized + debuginfo],用了 {R['t_first']:.2f} s;什么都不改再 build 只花 {R['t_noop']:.2f} s(cargo 比较指纹后发现无需重编)。cargo run = build + 运行,所以先看到 Finished、Running,再看到程序的输出。这时 Cargo.lock 才出现(version = 4,里面只有 hello 自己)。", t=tl(S(2)), done=[0], b=bars([['第一次 build', R['t_first'], f"{R['t_first']:.2f} s"], ['什么都不改', R['t_noop'], f"{R['t_noop']:.2f} s"]], max(R['t_first'], 0.3), done=[0, 1]), kv=KV([['第一次 build', f"{R['t_first']:.2f} s"], ['无变化再 build', f"{R['t_noop']:.2f} s"]], ['无变化再 build'])),
    step(f"产物都在 target/debug/ 里:可执行文件 hello({R['debug_size']:,} 字节)、hello.d(依赖文件列表)、.fingerprint/(指纹)、deps/、incremental/(增量编译缓存)、build/、examples/ 以及几个锁文件。改一行字符串后重新 build 用了 {R['t_edit']:.2f} s,只重编了 hello 这一个包。", t=tl(S(3)), done=[0, 1], kv=KV([['debug 可执行文件', f"{R['debug_size']:,} B"], ['改一行后 build', f"{R['t_edit']:.2f} s"]], ['debug 可执行文件'])),
    step(f"cargo build --release 用 release 配置(optimized)编译,产物在 target/release/,这个 hello world 里 release 为 {R['release_size']:,} 字节、debug 为 {R['debug_size']:,} 字节,几乎一样大(程序太小,体积主要是标准库链接进来的部分);改源码后 cargo check({R['t_check']:.2f} s)只做类型检查、不生成可执行文件,比 cargo build({R['t_build_after']:.2f} s)快。target/release/hello 可以不经过 cargo 直接运行。", t=tl(S(4)), mark=[0], b=bars([['cargo check', R['t_check'], f"{R['t_check']:.2f} s"], ['cargo build', R['t_build_after'], f"{R['t_build_after']:.2f} s"], ['build --release', R['t_release'], f"{R['t_release']:.2f} s"]], 0.3, done=[0, 1, 2]), kv=KV([['debug / release 大小', f"{R['debug_size']:,} / {R['release_size']:,} B"], ['check / build', f"{R['t_check']:.2f} / {R['t_build_after']:.2f} s"]], ['check / build'])),
]
A = dict(
    n=1, series='rust', tags='Rust,Cargo,编译,真实验证,动画演示',
    desc=f'真实运行 cargo new / build / run / check / build --release:生成的 5 样东西、第一次编译 {R["t_first"]:.2f} s 与无变化重编 {R["t_noop"]:.2f} s、target/debug 里的结构、debug {R["debug_size"]:,} 字节 vs release {R["release_size"]:,} 字节、cargo check 比 build 快多少。',
    lead='每个 Rust 项目都从 cargo new 开始。这篇不讲命令表,而是真的跑一遍:cargo new 到底生成了哪些文件,第一次编译做了什么、再编译一次为什么几乎不花时间,target/ 里有什么,debug 与 release 的差别,以及 cargo check 为什么更快。',
    facts=[('5 样', 'cargo new 生成:Cargo.toml、src/main.rs、.gitignore、.git(Cargo.lock 与 target 此时还没有)'), (f'{R["t_noop"]:.2f} s', '什么都没改时再 cargo build 的耗时(第一次 %.2f s)' % R['t_first']), (f'{R["debug_size"]:,} B', 'hello world 的 debug 可执行文件大小')],
    body=[
        sec('cargo new 生成了什么', '', term('', blk('u1', 1)), '<p>edition 决定语言版本的一组规则(这里的 2024 是 rustc 1.98 新建项目的默认值);Cargo.toml 是人写的清单,Cargo.lock 是 cargo 生成的依赖锁定(见<a href="rust-cargo-lock.html">Cargo.lock 的作用</a>)。</p>'),
        sec('第一次编译、再编译、运行', '', term('', blk('u1', 2)), '<p>cargo 把「是否需要重编」交给指纹(<code>target/debug/.fingerprint/</code>)判断:源文件、依赖、编译参数都没变,就直接 Finished。</p>'),
        sec('target/ 里的东西', '', term('', blk('u1', 3)), '<p>这个目录可以随时删除,下一次 build 会重新生成;所以 .gitignore 里只有 <code>/target</code>。</p>'),
        sec('debug、release 与 check', '', term('', blk('u1', 4)), '<p>release 的优化效果要在有真实计算的程序里才明显(见<a href="rust-debug-vs-release.html">Debug 与 Release 构建差异</a>);这里的 hello world 编译时间都在 0.1 s 量级,差别主要来自「要不要生成可执行文件」。</p>'),
        sec('分步演示', '', demo('cargo 的一次循环', [('t', 'term', '输出'), ('b', 'bars', '耗时'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_U + '。每次实验前清空了共享的 target 目录,项目在临时目录里;时间是单次测量(一个很小的项目,0.1 s 量级的差别主要是进程启动与文件系统开销)', '没有验证:大项目的编译时间、增量编译的细节、rustup 与 rustc 的关系(见第 2 篇)、cargo new --lib 与 workspace、其它 edition 的差别'],
)
