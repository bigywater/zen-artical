from lib import *
S = SS('u152')
R = J('u152'); lock = R['lock']; ck = [l for l in lock if l.startswith('checksum')][0].split('"')[1]
steps = [
    step(f"Cargo.lock 的内容(一个依赖 itoa 的最小项目):文件头注明自动生成、不要手改;version = 4 是锁文件格式版本;[[package]] 列出每个包的 name、version、source(registry+https://github.com/rust-lang/crates.io-index)和 checksum({ck[:16]}… 是 .crate 文件的 SHA-256);项目自己(u152)没有 source,只有 dependencies = [\"itoa\"]。锁文件是依赖图的完整快照。", t=tl(S(1)), done=lidx(S(1), 'version = 4', 'name = "itoa"', 'checksum', 'dependencies'), kv=KV([['格式', 'version = 4'], ['每个包', 'name / version / source / checksum'], ['依赖关系', 'dependencies 列表']], ['每个包'])),
    step(f"--locked:Cargo.toml 加了新依赖 semver 但锁文件没更新,cargo build --locked 拒绝:error: cannot update the lock file … because --locked was passed to prevent this;不加 --locked 则 cargo 自动更新锁文件(退出码 0,锁文件里的包数从 2 变成 {R['autoupd']})。CI 里用 --locked 能发现「忘了提交更新后的 Cargo.lock」。", t=tl(S(2)), done=lidx(S(2), '不加 --locked'), mark=lidx(S(2), 'cannot update the lock file'), kv=KV([['--locked', '锁文件需要更新 → 报错'], ['不加', '自动更新锁文件']], ['--locked'])),
    step("校验和防篡改:把锁文件里 itoa 的 checksum 前 8 位改成 deadbeef 并清掉本地的源码缓存,cargo build --locked 报 error: checksum for `itoa v1.0.18` changed between lock files,并列出可能原因(锁文件损坏、镜像返回了不同的校验和、源本身损坏)。同名同版本的内容被替换会被发现。", t=tl(S(3)), mark=lidx(S(3), 'checksum for', 'unable to verify'), kv=KV([['checksum 不一致', '拒绝构建']], ['checksum 不一致'])),
    step("锁文件让构建可复现:cargo update -p itoa --precise 1.0.5 把锁文件钉在 1.0.5,之后 cargo build --locked 成功(退出码 0),cargo tree --locked 显示 itoa v1.0.5(以及 semver v1.0.28)—— 无论 crates.io 上最新版是 1.0.18 还是更高,按这个锁文件构建得到的版本不变。", t=tl(S(4)), done=lidx(S(4), 'cargo build --locked', 'itoa v1.0.5'), kv=KV([['钉在 1.0.5', 'build --locked 成功'], ['cargo tree --locked', 'itoa v1.0.5']], ['cargo tree --locked'])),
    step("提交不提交 Cargo.lock?cargo new --bin 与 cargo new --lib 生成的 .gitignore 都只有 /target —— 两种项目的默认 .gitignore 都没有忽略 Cargo.lock(旧版本 cargo 对库默认忽略,现在默认不忽略)。二进制应该提交锁文件以保证可复现;库是否提交取决于你想不想让 CI 在固定的依赖上测试。", t=tl(S(5)), done=lidx(S(5), 'cargo new --bin', 'cargo new --lib'), kv=KV([['.gitignore(bin / lib)', '/target(都不忽略 Cargo.lock)']], ['.gitignore(bin / lib)'])),
]
A = mkart('u152', 152, 'Rust,Cargo.lock,锁文件,可复现构建,真实验证,动画演示',
    '用真实项目验证 Cargo.lock:格式 version = 4、每个包的 source 与 SHA-256 checksum;--locked 在锁文件需要更新时拒绝构建;篡改 checksum 得 changed between lock files;--precise 钉住版本后 build --locked 保持 itoa 1.0.5;cargo new 的 .gitignore 不忽略 Cargo.lock。',
    'Cargo.lock 到底锁了什么?什么时候该提交?--locked 有什么用?篡改它会怎样?这篇用一个最小项目把锁文件的内容、校验、可复现性和提交约定逐个验证。',
    [('version = 4', '本机 cargo 生成的锁文件格式版本'), ('SHA-256', '锁文件为每个 registry 包记录的校验和'), ('--locked', '让 CI 在锁文件过期时失败的开关')],
    [('锁文件的内容', '<p>依赖版本的解析规则见<a href="rust-cargo-dependency-resolution.html">Cargo.toml 依赖解析</a>。</p>'), ('--locked', None), ('checksum', None), ('可复现构建', '<p>在工作区里统一依赖见<a href="rust-workspace-dependencies.html">Workspace 依赖管理</a>。</p>'), ('要不要提交', None)],
    steps, [ENV_U + '。crates.io 为 2026-10 的最新数据', '没有验证:git 依赖在锁文件里的 source 格式、vendor 目录与离线构建、cargo package 是否把 Cargo.lock 打进发布包、锁文件合并冲突的处理、cargo-deny 对锁文件的审计(见依赖安全审计一篇)'], 'Cargo.lock')
