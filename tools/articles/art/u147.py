from lib import *
import re
S = SS('u147')
R = J('u147'); n = re.search(r'vars_os\(\) 共 (\d+) 个', R['iter']['vars_os'][1]).group(1)
steps = [
    step("读取环境变量:env::var 返回 Result。存在的 U147_SET = \"hello\" 得 Ok(\"hello\");不存在的 U147_MISSING 得 Err(NotPresent,「environment variable not found」);值不是合法 UTF-8 的 U147_BAD 得 Err(NotUnicode)(消息里带着原始字节 bad\\xFF\\xFE);空字符串的 U147_EMPTY 是 Ok(\"\")(空 ≠ 不存在)。var_os 不会因编码失败:对 U147_BAD 返回 Some(OsString),原始字节 [98, 97, 100, 255, 254]。", t=tl(S(1)), done=lidx(S(1), 'U147_SET', 'U147_MISSING', 'U147_BAD', 'U147_EMPTY'), kv=KV([['不存在', 'Err(NotPresent) / var_os None'], ['非 UTF-8', 'Err(NotUnicode) / var_os Some'], ['空字符串', 'Ok(\"\")']], ['非 UTF-8'])),
    step("修改自己的环境:set_var 之后启动的子进程能看到 U147_X=from-rust;remove_var 之后子进程看到的是空。修改只影响当前进程与它之后启动的子进程,不会影响父 shell。", t=tl(S(2)), done=lidx(S(2), 'set_var 之后子进程看到', 'remove_var 之后子进程看到'), kv=KV([['set_var', '当前进程 + 之后的子进程'], ['父 shell', '不受影响']], ['父 shell'])),
    step("edition 2024 里 set_var 是 unsafe:直接调用 std::env::set_var(\"A\", \"1\") 报 error[E0133]: call to unsafe function `set_var` is unsafe and requires unsafe block,note 提示去读文档了解如何避免未定义行为(多线程里修改环境与读取环境同时发生是数据竞争)。", t=tl(S(2)), mark=lidx(S(2), 'error[E0133]', 'set_var'), kv=KV([['set_var / remove_var', '2024 edition 起 unsafe']], ['set_var / remove_var'])),
    step("进程环境是各自一份拷贝:父进程设 U147_SHARED=parent,子进程里 export U147_SHARED=child 并打印 child,子进程结束后父进程读到的仍然是 Ok(\"parent\")。环境变量不是进程间的通信手段,只是启动时一次性传下去的初始值。", t=tl(S(3)), done=lidx(S(3), 'child: child', '子进程改完之后'), kv=KV([['子进程里的修改', '父进程看不到']], ['子进程里的修改'])),
    step(f"遍历全部环境变量:环境里只要有一个值不是合法 UTF-8,env::vars() 就 panic(退出码 101,called `Result::unwrap()` on an `Err` value: \"bad\\xFF\\xFE\");vars_os() 照常工作,数到 {n} 个。处理外部传入的环境时用 vars_os。", t=tl(S(4)), mark=lidx(S(4), '退出码 101', 'vars →'), done=lidx(S(4), 'vars_os'), kv=KV([['vars()', '遇到非 UTF-8 panic'], ['vars_os()', f'不失败,{n} 个']], ['vars()'])),
    step("编译期与运行期是两回事:option_env!(\"U147_COMPILE\") 在编译时读取。编译时设置 A、运行时设置 B,程序输出编译期 Some(\"A-at-compile\")、运行期 Some(\"B-at-run\");编译时没设置,编译期得到 None;env!(\"U147_REQUIRED\") 编译时没有这个变量则编译失败:error: environment variable `U147_REQUIRED` not defined at compile time。", t=tl(S(5)), done=lidx(S(5), '编译时设置 A', '编译时没设置'), mark=lidx(S(5), 'U147_REQUIRED'), kv=KV([['option_env!', '编译时的值,缺失 None'], ['env!', '缺失则编译失败'], ['env::var', '运行时的值']], ['env!'])),
]
A = mkart('u147', 147, 'Rust,环境变量,env,set_var,真实验证,动画演示',
    '用真实进程验证环境变量:var 的 NotPresent / NotUnicode 与 var_os;空字符串不等于不存在;set_var 只影响自己与子进程且在 2024 edition 里是 unsafe(E0133);子进程的修改父进程看不到;非 UTF-8 的值让 vars() panic 而 vars_os() 正常;option_env! / env! 是编译期的值。',
    '环境变量的读取看似一行代码,却牵出编码、可变性、进程边界与编译期差异。这篇逐条验证 env::var 的各种结果、set_var 为什么变成 unsafe、子进程的修改是否可见,以及 env! 与 env::var 的区别。',
    [('NotUnicode', '环境变量值不是合法 UTF-8 时 env::var 的错误'), ('E0133', '2024 edition 里不加 unsafe 调用 set_var 的错误码'), ('编译期 与 运行期', 'option_env! 读编译时的值,env::var 读运行时的值')],
    [('读取', '<p>子进程如何继承与修改环境见<a href="rust-subprocess-command.html">子进程与 Command</a>。</p>'), ('修改', '<p>unsafe 的含义见<a href="rust-unsafe-boundary.html">unsafe 的安全边界</a>。</p>'), ('子进程的修改', None), ('遍历', None), ('编译期', '<p>build.rs 里的 cargo:rustc-env 见<a href="rust-build-rs.html">Build Script build.rs</a>。</p>')],
    steps, [ENV_U + '。非 UTF-8 值通过 Python 的 bytes 环境传入', '没有验证:多线程中并发 set_var 与 getenv 的真实竞争后果、Windows 上环境变量名大小写不敏感、dotenv 类 crate、env::args 与环境变量的关系、setenv 在 C 库里的线程安全性'], '环境变量')
