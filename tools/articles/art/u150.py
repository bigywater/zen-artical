from lib import *
S = SS('u150')
R = J('u150')
steps = [
    step(f"把 no_std 的 Rust 编译成 WebAssembly(wasm32-unknown-unknown,release,opt-level s,panic = abort,lto):包含 add、fib、checked_div 三个函数的模块只有 {R['size']} 字节。导出是 memory 与三个函数(没有 main),导入是空的 —— 模块不依赖宿主提供任何东西。", t=tl(S(1)), done=lidx(S(1), 'w1.wasm 大小', '导出', '导入'), kv=KV([['大小', f"{R['size']} 字节"], ['导入', '无'], ['导出', 'memory + add / fib / checked_div']], ['导入'])),
    step("在 node 里用 WebAssembly API 实例化并调用:add(2, 3) = 5(返回 number);fib(50) = 12586269025n,返回 bigint —— wasm 的 i64 在 JS 里是 BigInt;add(2147483647, 1) = -2147483648,i32 加法回绕,不检查溢出。", t=tl(S(1)), done=lidx(S(1), 'add(2, 3)', 'fib(50)', 'add(2147483647'), kv=KV([['i32', 'number'], ['i64', 'bigint'], ['溢出', '回绕,不检查']], ['i64'])),
    step("panic 在 wasm 里是 trap:checked_div(1, 0) 里 b == 0 时 panic,panic_handler 执行 unreachable 指令,JS 收到 RuntimeError: unreachable。trap 之后实例仍然可用:add(1, 1) = 2(wasm 不会因 trap 毁掉整个宿主进程)。", t=tl(S(1)), mark=lidx(S(1), 'checked_div(1, 0)'), done=lidx(S(1), '陷入 trap 之后'), kv=KV([['panic', '→ unreachable trap'], ['宿主', '收到 RuntimeError,继续运行']], ['宿主'])),
    step("线性内存:wasm 模块有一块连续的内存,指针就是它里面的偏移(整数)。buf_ptr() 返回 1048576,内存共 1114112 字节 = 17 页(每页 64 KiB)。JS 往这个偏移写入 \"hello wasm\" 的 10 字节,Rust 的 sum(10) 得 1004,与 JS 里自己算的一致;upper(10) 在 Rust 里就地改写后,JS 读到 \"HELLO WASM\"。两边读写的是同一块内存。", t=tl(S(2)), done=lidx(S(2), 'buf_ptr()', 'JS 写入', 'upper(10)'), kv=KV([['指针', '线性内存里的偏移'], ['共享', 'JS 与 wasm 读写同一块内存']], ['共享'])),
    step("WASI:模块通过导入 wasi_snapshot_preview1.fd_write 和 proc_exit 才有输出与退出的能力,导出 _start 与 memory。node 的 WASI 对象提供这些导入:运行输出「hello from Rust compiled to WASI」,wasi.start 返回退出码 0。宿主决定 fd 1 接到哪里。", t=tl(S(3)), done=lidx(S(3), '导入', 'hello from Rust', 'wasi.start'), kv=KV([['导入', 'fd_write + proc_exit'], ['能力', '由宿主提供']], ['能力'])),
    step("宿主不提供 WASI 导入时,实例化直接失败:TypeError: WebAssembly.Instance(): Import #0 \"wasi_snapshot_preview1\": module is not an object or function。模块声明了需要什么,宿主不给就跑不起来 —— 这就是 wasm 沙箱的基础:没有导入就没有系统调用、没有文件、没有网络。", t=tl(S(3)), mark=lidx(S(3), '宿主不提供'), kv=KV([['没有提供导入', '实例化失败'], ['沙箱', '能力 = 宿主给的导入']], ['沙箱'])),
]
A = mkart('u150', 150, 'Rust,WebAssembly,WASI,wasm,真实验证,动画演示',
    f'真实把 no_std Rust 编译成 WebAssembly 并在 node 里运行:模块仅 {R["size"]} 字节、零导入;i32 对 number、i64 对 BigInt;panic 变成 unreachable trap 且实例可继续使用;JS 与 Rust 通过线性内存(偏移指针、17 页)共享字节;手写 WASI 的 fd_write / proc_exit 导入,宿主不提供导入时实例化失败。',
    'WebAssembly 和 WASI 到底是什么?这篇不讲概念,而是真的把 Rust 编译成 .wasm,检查它的导入导出,从 JS 调用,往它的线性内存里写字节,再让它通过 WASI 打印一行字,最后看宿主不提供能力时会怎样。',
    [(f'{R["size"]} 字节', '三个函数的 Rust wasm 模块大小'), ('BigInt', 'wasm 的 i64 在 JS 里的类型'), ('0 个导入', '纯计算模块需要宿主提供的导入数量(WASI 版本需要 2 个)')],
    [('编译成 wasm 并从 JS 调用', '<p>本机的 brew rustc 没有 wasm32 的预编译标准库,所以用 -Z build-std=core(RUSTC_BOOTSTRAP=1)从源码构建 core,链接器用 Zig 里自带的 wasm-ld(通过 pip 安装的 ziglang 提供,只装在实验用的虚拟环境里)。因此这里是 no_std 的模块,不是带 std 的 wasm32-wasip1 程序。panic 的行为见<a href="rust-panic-unwrap-expect.html">panic!、unwrap 与 expect</a>。</p>'), ('线性内存', '<p>裸指针的概念见<a href="rust-raw-pointer-deref.html">原始指针解引用</a>。</p>'), ('WASI 与沙箱', None)],
    steps, [ENV_U + '。Node.js v26.10(WebAssembly 与 node:wasi);wasm-ld 来自 ziglang 0.16(LLD 21.1)', '没有验证:带 std 的 wasm32-wasip1 程序(缺 wasi-libc)、浏览器里运行、wasm-bindgen / wasm-pack、组件模型(WASI preview2)、wasmtime 与 wasmer 等独立运行时、线程与 SIMD 扩展、wasm 文件优化工具 wasm-opt'], 'WASI 与 WebAssembly')
