from lib import *
S = SS('u15')
steps = [
    step("一个 package(有 Cargo.toml 的目录)可以有多个 crate:同时有 src/lib.rs 与 src/main.rs 时,cargo build -v 调了两次 rustc:--crate-name pkg2 --crate-type lib 与 --crate-name pkg2 --crate-type bin。bin crate 通过 pkg2::greet() 使用同包的 lib crate,cargo run 输出「来自 lib crate」。crate 是编译单元,package 是 cargo 的管理单元。", t=tl(S(1)), done=lidx(S(1), 'crate', '来自'), kv=KV([['crate', '编译单元(rustc 一次编一个)'], ['package', 'Cargo.toml 所在的目录']], ['crate'])),
    step("workspace:根 Cargo.toml 里只有 [workspace] members = [\"app\", \"core\"],两个成员各有自己的 Cargo.toml,app 用 core_lib = { path = \"../core\" } 依赖另一个成员。在根目录 cargo build 依次编译 core_lib 与 app;整个 workspace 只有根目录有一份 Cargo.lock(app/ 下没有),target 目录也在根(在 app/ 子目录里构建后,ws/target 存在而 ws/app/target 不存在)。", t=tl(S(2)), done=lidx(S(2), 'Compiling', '只有根目录有 Cargo.lock', 'target 存在'), kv=KV([['Cargo.lock', '只有根目录一份'], ['target', '在 workspace 根']], ['Cargo.lock'])),
    step("在成员目录里运行 cargo 仍然作用于整个 workspace:cargo run -q -p app 与 (cd app && cargo run -q) 都输出 answer = 42。cargo tree 画出依赖:app → core_lib;cargo metadata 列出 packages = ['app', 'core_lib']。", t=tl(S(3)), done=lidx(S(3), 'answer = 42', 'app v0.1.0', 'metadata'), kv=KV([['-p app', '指定成员'], ['cargo tree', 'app → core_lib']], ['cargo tree'])),
    step("包名与 crate 名:包名 my-pkg 里的连字符,在 rustc 的 --crate-name 里变成下划线 my_pkg;依赖里写 my-pkg,代码里就写 my_pkg::f()(运行输出 1)。", t=tl(S(4)), mark=lidx(S(4), 'my_pkg'), kv=KV([['包名', 'my-pkg'], ['代码里的名字', 'my_pkg']], ['代码里的名字'])),
]
A = mkart('u15', 15, 'Rust,Crate,Package,Workspace,Cargo,真实验证,动画演示',
    '用真实 cargo 运行验证 crate、package、workspace 的关系:同一 package 里 lib 与 bin 是两个 crate(两次 rustc 调用);workspace 共用根目录的 Cargo.lock 与 target;成员目录里 cargo 命令仍作用于整个 workspace;包名的连字符在代码里变下划线。',
    'crate、package、workspace 是三个常被混用的词。这篇用 cargo 的真实输出把它们分开:一个 package 里到底有几个 crate、workspace 共享什么、在成员目录里运行 cargo 会发生什么,以及包名和代码里的名字为什么不同。',
    [('2 个 crate', '同一个 package 里的 lib 与 bin(cargo build -v 里的两次 rustc 调用)'), ('1 份', 'workspace 只有根目录一份 Cargo.lock 与一个 target'), ('my-pkg → my_pkg', '包名连字符在代码里变下划线')],
    [('package 与 crate', None), ('workspace', '<p>workspace 的依赖统一管理见<a href="rust-workspace-dependencies.html">Workspace 依赖管理</a>;Cargo.lock 的作用见<a href="rust-cargo-lock.html">Cargo.lock 的作用</a>。</p>'), ('在成员目录里运行', None), ('包名与 crate 名', None)],
    steps, [ENV_U + '。项目在临时目录里;全部用路径依赖,没有访问 crates.io', '没有验证:workspace.dependencies 的版本继承、虚拟 workspace 与根 package 同时存在、成员的 default-members、resolver 的版本差别、发布到 crates.io 时的 package 规则'], 'crate、package 与 workspace')
