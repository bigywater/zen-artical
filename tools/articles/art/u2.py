from lib import *
R = J('u2')
S = SS('u2')
steps = [
    step(f"本机只有 rustc 与 cargo(Homebrew 装的 {R['ver']}),没有 rustup:command -v rustup 找不到。rustc --version --verbose 给出宿主平台 {R['host']}、commit、LLVM 版本(22.1.8)—— rustc 是真正的编译器,后端是 LLVM。", t=tl(S(1)), done=[0], kv=KV([['有', 'rustc、cargo'], ['没有', 'rustup']], ['有'])),
    step(f"rustc 的 sysroot 是 /opt/homebrew/Cellar/rust/1.98.1,标准库在 lib/rustlib/<目标平台>/lib 里(libstd 有 rlib {R['std']['.rlib']:,} 字节、dylib {R['std']['.dylib']:,} 字节、rmeta {R['std']['.rmeta']:,} 字节)。rustc 认识 {R['n_targets']} 个目标三元组,但这台机器只装了宿主平台 {R['host']} 的标准库 —— 要交叉编译别的目标,得先装对应的标准库。", t=tl(S(2)), done=[0], b=bars([['rustc 认识的目标', R['n_targets'], str(R['n_targets'])], ['已装标准库的目标', 1, '1']], R['n_targets'], mark=[1], done=[0]), kv=KV([['rustc 认识的目标', R['n_targets']], ['已装标准库的目标', 1]], ['已装标准库的目标'])),
    step("cargo build -v 把 cargo 实际调用的 rustc 命令行打印出来:rustc --crate-name verbose --edition=2024 src/main.rs --crate-type bin --emit=dep-info,link -C debuginfo=2 -C incremental=… --out-dir target/debug/deps …。cargo 做的是依赖解析、决定参数、调用 rustc、管理产物目录;编译本身全是 rustc。", t=tl(S(3)), done=[0], kv=KV([['cargo 的工作', '解析依赖 + 拼参数 + 调 rustc'], ['编译', 'rustc']], ['编译'])),
    step("同一份源码直接 rustc 编译(不带 cargo)也能成功,0.09 s,产物 434,752 字节(cargo debug 产物 438,120 字节,差别在参数不同)。cargo 靠环境变量 RUSTC 找编译器:把 RUSTC 指到不存在的路径,cargo 报「could not execute process /nonexistent/rustc -vV」。另外 rustc +nightly 这种 +toolchain 写法没有 rustup 的代理就不被认识:rustc 把 +nightly 当成第二个输入文件,报 multiple input filenames。", t=tl(S(4)), mark=[1], kv=KV([['RUSTC 环境变量', 'cargo 用它找编译器'], ['+nightly', '没有 rustup 时无效']], ['RUSTC 环境变量'])),
]
A = dict(
    n=2, series='rust', tags='Rust,rustc,Cargo,Rustup,真实验证,动画演示',
    desc=f'在没有装 rustup 的机器上验证三者的分工:rustc({R["ver"]},LLVM 22.1.8)是编译器,cargo 通过 cargo build -v 可见的 rustc 命令行调用它,sysroot 里只有宿主平台的标准库(rustc 认识 {R["n_targets"]} 个目标),RUSTC 环境变量决定 cargo 用哪个 rustc。',
    lead='rustc、Cargo、Rustup 常被一起提到,但它们是三个东西。这台机器碰巧只用 Homebrew 装了 rustc 和 cargo、没有 rustup,正好可以把前两者的边界量清楚:rustc 带着什么、cargo 到底怎么调用 rustc、缺了 rustup 会少什么。rustup 本身没有装,所以关于它的部分我只写「没有」的证据。',
    facts=[('3 个', '角色:rustc(编译器)、cargo(构建与依赖管理)、rustup(工具链管理,本机没装)'), (f'{R["n_targets"]}', 'rustc 认识的目标三元组数(只装了宿主平台的标准库)'), ('RUSTC', 'cargo 用这个环境变量找编译器')],
    body=[
        sec('本机有什么', '', term('', blk('u2', 1))),
        sec('rustc 自带的东西', '', term('', blk('u2', 2)), '<p>标准库是随编译器分发的预编译库(rlib),不是每次编译重新编译的。</p>'),
        sec('cargo 如何调用 rustc', '', term('', blk('u2', 3)), '<p>这些参数的含义会在后面的文章里陆续展开,比如<a href="rust-cargo-profile.html">Cargo Profile</a>(debuginfo、opt-level)与<a href="rust-incremental-compilation.html">增量编译</a>(-C incremental)。</p>'),
        sec('绕过 cargo、换掉 rustc', '', term('', blk('u2', 4)), '<p>rustup 的作用(多版本工具链、+nightly、交叉编译目标的安装)我没有在本机验证,因为没有装它。</p>'),
        sec('分步演示', '', demo('rustc、cargo 与 rustup', [('t', 'term', '输出'), ('b', 'bars', '数量'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_U + '。本机没有 rustup,工具链来自 Homebrew', '没有验证:rustup 的行为(toolchain 切换、target add、component add)、nightly 与 stable 的差别、rust-toolchain.toml 的作用、Windows 与 Linux 上的安装方式、cargo 对其它编译器包装(RUSTC_WRAPPER)的支持'],
)
