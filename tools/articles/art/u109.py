from lib import *
import re
S = SS('u109')
R = J('u109')
ul = R['ulimit']; dm = R['depth_main']; dt = R['depth_thread']
c = re.search(r'栈上 \[u8; 256\]\s+每轮\s+([\d.]+) ns.*\n堆上.*每轮\s+([\d.]+) ns', R['cost']); cs, ch = c.group(1), c.group(2); cr = round(float(ch) / float(cs), 1)
steps = [
    step("打印各种东西的地址:局部变量、数组、box 变量本身都在 0x16f… 一带(栈);Box<u64> 的数据、Vec 与 String 的缓冲区在 0x1012… 一带(堆);字符串字面量、static、main 函数代码在 0x1008… 一带(程序映像的只读数据 / 数据 / 代码段)。三个区域的地址范围明显不同。", t=tl(S(1)), done=lidx(S(1), '局部变量 local', '数组', 'box 变量本身', 'Box<u64>', 'Vec 的缓冲区', 'String 的缓冲区', '字符串字面量', 'static', 'main 函数代码'), kv=KV([['栈', '0x16f… 局部变量、box 变量本身'], ['堆', '0x1012… Box / Vec / String 的数据'], ['程序映像', '0x1008… 字面量、static、代码']], ['堆'])),
    step("Box 变量本身(一个指针)在栈上,它指向的数据在堆上;被调函数 deeper 的局部变量地址 0x…3b0 比 main 里的 0x…4d8 更低 —— 这台机器上栈向低地址增长。", t=tl(S(1)), mark=lidx(S(1), '被调函数的局部'), kv=KV([['调用更深', '地址更低(栈向下增长)']], ['调用更深'])),
    step(f"栈有固定上限:主线程栈上限 ulimit -s = {ul} KiB。用二分法测每层约 150 字节的递归:主线程约 {dm} 层时仍正常,子线程(默认栈)约 {dt} 层。递归 400 万层则 stderr 报 fatal runtime error: stack overflow, aborting,进程被信号 6 终止 —— 栈溢出不是 panic。", t=tl(S(2)), done=lidx(S(2), 'ulimit', '主线程', '子线程'), mark=lidx(S(2), '400 万层'), b=bars([['主线程最大深度', dm, str(dm)], ['子线程最大深度', dt, str(dt)]], dm, done=[0, 1]), kv=KV([['主线程', f'约 {dm} 层'], ['子线程', f'约 {dt} 层'], ['溢出', 'abort,信号 6']], ['溢出'])),
    step("大数组放栈上会直接溢出:main 里 [0u8; 16 MiB] 超过 8 MiB 的栈上限,进程被信号 6 终止;同样 16 MiB 放进堆上(vec → into_boxed_slice)正常,b[100] = 0,长度 16777216。", t=tl(S(3)), mark=lidx(S(3), '16 MiB 数组放栈上'), done=lidx(S(3), '16 MiB 放在堆上'), kv=KV([['16 MiB 在栈', '栈溢出 abort'], ['16 MiB 在堆', '正常']], ['16 MiB 在栈'])),
    step(f"分配成本(release,每轮创建并使用 256 字节缓冲区,2000 万轮,取 3 次最小):栈上数组每轮 {cs} ns,堆上 vec![0u8; 256] 每轮 {ch} ns(含分配与释放),约 {cr} 倍。栈分配只是移动栈指针;堆分配要走分配器。", t=tl(S(4)), done=lidx(S(4), '栈上', '堆上'), b=bars([['栈上 [u8; 256]', float(cs), f'{cs} ns'], ['堆上 Vec', float(ch), f'{ch} ns']], float(ch), cur=[1], done=[0]), kv=KV([['栈', f'{cs} ns'], ['堆', f'{ch} ns(约 {cr}×)']], ['堆'])),
]
A = mkart('u109', 109, 'Rust,栈,堆,内存布局,真实验证,动画演示',
    f'用真实运行验证栈与堆:地址分区(栈 0x16f…、堆 0x1012…、字面量/static/代码 0x1008…);栈向低地址增长;主线程栈 {ul} KiB 约 {dm} 层、子线程约 {dt} 层,溢出是 abort;16 MiB 栈数组溢出而堆上没事;256 字节缓冲区栈 {cs} ns 对堆 {ch} ns。',
    '“局部变量在栈上,Box 和 Vec 在堆上”这句话怎么验证?栈到底多大?放不下会怎样?栈分配比堆分配快多少?这篇都用真实运行回答。',
    [(f'{ul} KiB', '这台机器主线程的栈上限(ulimit -s)'), (f'约 {dm} 层', '每层约 150 字节栈帧的递归在主线程溢出前的深度'), (f'{cr}×', '256 字节缓冲区:堆分配比栈分配慢的倍数')],
    [('变量在哪里', '<p>Box 见<a href="rust-box-heap.html">Box&lt;T&gt; 与堆分配</a>。</p>'), ('栈的大小限制', '<p>线程栈大小见<a href="rust-thread-spawn-join.html">线程创建与 Join</a>。</p>'), ('大数组', None), ('分配成本', '<p>耗时是本机 release 微基准;栈上版本可能被优化器部分消除,只用于量级比较。</p>')],
    steps, [ENV_U + '。macOS aarch64', '没有验证:Linux 上的栈布局与栈保护页、每层栈帧大小的精确值(只是估算)、glibc/其它分配器的成本、栈上数组被优化器完全消除的情形、堆的地址随机化(ASLR)每次运行的变化'], '栈与堆')
