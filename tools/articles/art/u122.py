from lib import *
S = SS('u122')
steps = [
    step("调用 libc:用 unsafe extern \"C\" { fn strlen(…); fn abs(…); fn getpid(); fn toupper(…) } 声明后直接调用。字符串要用 CString 变成以 \\0 结尾:strlen(\"héllo\") = 6(C 数字节,é 占 2 字节,与 Rust 的 len() = 6 相同);abs(-42) = 42;toupper('a') = 'A';getpid() 与 std::process::id() 相等(true)。", t=tl(S(1)), done=lidx(S(1), 'strlen', 'abs(-42)', 'getpid()'), kv=KV([['字符串', 'CString / c\"…\" 字面量,以 \\\\0 结尾'], ['函数声明', 'extern \"C\" + unsafe 调用']], ['字符串'])),
    step("CString::new 拒绝中间有 \\0 的字符串:CString::new(\"a\\0b\") 返回 Err(\"nul byte found in provided data at position: 1\");c\"字面量\" 是编译期的 &CStr,字节数 9(UTF-8)。", t=tl(S(1)), mark=lidx(S(1), 'CString::new', 'c"…"'), kv=KV([['含 \\\\0 的字符串', 'Err(NulError)']], ['含 \\\\0 的字符串'])),
    step("回调:把 Rust 写的 extern \"C\" fn cmp_desc 交给 libc 的 qsort 作比较函数,v = [5, 2, 9, 1, 7, 3, 8] 排成 [9, 8, 7, 5, 3, 2, 1],C 一共回调了 17 次。回调必须用 extern \"C\" 调用约定声明。", t=tl(S(2)), done=lidx(S(2), 'qsort'), kv=KV([['回调', 'extern \"C\" fn,由 C 调用'], ['调用次数', '17']], ['回调'])),
    step("链接自己的 C 库:用 clang 把 vec2.c 编译成 vec2.o,再用 ar 打成 libvec2.a,Rust 用 #[link(name = \"vec2\", kind = \"static\")] 链接。repr(C) 的 Vec2 { x: f64, y: f64 } 可以按值传入、按值返回:vec2_add = Vec2 { x: 11.0, y: 22.0 };按指针传:vec2_len2(&r) = 605。", t=tl(S(3)), done=lidx(S(3), 'clang', 'vec2_add', 'vec2_len2'), kv=KV([['按值传递结构体', 'repr(C) 保证布局一致'], ['按指针传递', '&r → const Vec2*']], ['按值传递结构体'])),
    step("C 直接读写 Rust 的内存:vec2_scale_all 原地把 Rust 数组乘以 10,得到 [Vec2 { x: 10, y: 10 }, Vec2 { x: 20, y: 30 }];fill_greeting 往 Rust 的 32 字节缓冲区写入 12 字节,CStr 读出 \"hello from C\";缓冲区只有 4 字节时 C 返回 0(约定「放不下」);sum_i32(Rust 数组) = 15。", t=tl(S(3)), done=lidx(S(3), 'vec2_scale_all', 'fill_greeting', '缓冲区太小', 'sum_i32'), kv=KV([['缓冲区', 'Rust 分配,C 填写'], ['长度', '要一起传给 C']], ['缓冲区'])),
    step("extern 声明写错时 rustc 不会报错 —— 编译器看不到 C 的头文件。同一个 C 函数 sum_i32:正确声明得 6;错声明成返回 f64,编译通过、没有任何警告,运行输出一个极小的数(326 个字符的 0.000…);少声明一个参数 n,编译通过,运行时段错误(退出码 -11);把 n 写成 1000(越界读),输出一个随机的垃圾整数(这次是 288628513)。声明与定义是否一致完全靠人,所以通常用 bindgen 自动生成声明。", t=tl(S(4)), mark=lidx(S(4), 'ret_f64', 'no_n', 'n_wrong_ptr'), done=lidx(S(4), 'right'), kv=KV([['错的返回类型', '输出垃圾值,无警告'], ['少一个参数', '段错误(-11)'], ['n 写大', '读到越界的垃圾']], ['少一个参数'])),
]
A = mkart('u122', 122, 'Rust,FFI,C,extern,真实验证,动画演示',
    '用真实 libc 与自己用 clang 编译的静态库验证 FFI:strlen / abs / getpid 与 CString;把 Rust 回调交给 qsort(17 次回调);repr(C) 结构体按值与按指针传递;C 往 Rust 缓冲区写数据;extern 声明写错时 rustc 不报错而运行得到垃圾或段错误。',
    'Rust 调 C 函数需要什么?字符串怎么传?结构体怎么传?回调怎么写?声明写错会怎样?这篇用真实的 libc 和一个自己编译的 C 静态库一次验证清楚。',
    [('17 次', 'qsort 回调 Rust 比较函数的次数(7 个元素)'), ('0 个警告', '把 extern 声明写错(返回类型/参数个数)时 rustc 给出的警告'), ('-11', '少声明一个参数时程序的退出码(段错误)')],
    [('调用 libc', '<p>可空指针的 FFI 表示见<a href="rust-option-ref-niche.html">Option&lt;&T&gt; 的空指针优化</a>;repr(C) 见<a href="rust-repr-c-layout.html">#[repr(C)] 与内存布局</a>。</p>'), ('回调', None), ('链接自己的 C 库', '<p>用 clang 与 ar 手工构建静态库,没有使用 cc crate 与 build.rs(见<a href="rust-build-rs.html">Build Script build.rs</a>)。</p>'), ('声明写错', '<p>输出里的垃圾值每次运行可能不同。</p>')],
    steps, [ENV_U + '。C 代码用系统 clang 编译', '没有验证:bindgen / cbindgen 自动生成、C 回调里 panic 穿过 FFI 边界(extern \"C\" 里的 panic 会 abort)、变长参数函数(printf)的调用、动态库的 link 与 rpath、C++ 的名字改编、跨平台 ABI 差异(Windows x64 等)'], 'FFI 调用 C')
