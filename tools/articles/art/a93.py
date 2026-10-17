import json, re
from lib import *
txt = out('93').splitlines()
R = json.load(open('out/93.json')); calls = R['calls']; t1, t2, t3 = R['t']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())
line = lambda key: next(l for l in txt if key in l)
tabs = float(re.search(r'abs\(-5\)\s+(\d+) ns', line('Python 内置 abs')).group(1)); tc = float(re.search(r'abs\(-5\)\s+(\d+) ns', line('ctypes libc.abs')).group(1))
init = [5, 2, 9, 1, 7, 3, 8, 4]
steps = [step("准备一个 8 个整数的数组,交给 C 的 qsort,并把一个 Python 函数作为比较回调传进去。", cells={'values': init}, log={'lines': ['(还没有回调)'], 'cur': []})]
lg = []
for i, (x, y) in enumerate(calls):
    lg.append(f"第 {i+1:>2} 次回调 py_cmp({x}, {y}) → {(x>y)-(x<y):+d}")
    steps.append(step(f"C 的 qsort 调用了 Python 函数:比较 {x} 和 {y}。", cells={'values': init, 'cur': [init.index(x)], 'mark': [init.index(y)]}, log={'lines': list(lg), 'cur': [len(lg) - 1]}))
steps.append(step(f"qsort 结束:一共回调了 {len(calls)} 次 Python 函数,数组原地变成 [1, 2, 3, 4, 5, 7, 8, 9]。", cells={'values': sorted(init), 'done': list(range(8))}, log={'lines': list(lg), 'cur': []}))
A = dict(
    n=93,
    tags='Python,标准库,C扩展,ctypes,真实验证,动画演示',
    desc=f'本机真实用 ctypes 调用 libc 与自己编译的 C 动态库:不声明 argtypes 时传 Python float 直接 ArgumentError,只声明 argtypes 不声明 restype 时 sqrt(2.0) 返回 0;malloc 默认返回值被截断成 32 位;结构体布局与 C 的 sizeof/offsetof 一致(24 字节);qsort 回调 Python 比较函数 {len(calls)} 次;对 100 万整数求和,C 函数 {t1:.2f} ms、sum() {t2:.1f} ms、for 循环 {t3:.0f} ms;读空指针进程直接被 SIGSEGV 杀死。',
    lead='不写一行 C 扩展,<code>ctypes</code> 就能让 Python 直接调用动态库里的函数。但它是「信任你」的:你告诉它函数接受什么、返回什么,它就照做,说错了也不报错。这篇用 libc 和一个自己编译的小 C 库,把它的能力和陷阱都真实跑一遍。',
    facts=[('restype 不声明', 'sqrt(2.0) 返回 0 而不是 1.414…'), (f'{len(calls)} 次', 'C 的 qsort 对 8 个整数回调 Python 比较函数的次数'), ('SIGSEGV', '读地址 0:Python 没有异常,进程被信号直接杀掉(返回码 -11)')],
    body=[
        sec('验证一:直接调用 libc', '', term('', block('== 一', '== 二')),
            '<p><code>ctypes.CDLL(ctypes.util.find_library("c"))</code> 打开 C 标准库,函数就成了属性。<code>getpid</code> 与 <code>os.getpid()</code> 结果相同——它们真是同一个系统调用。传参要用 C 能理解的类型:<code>bytes</code> 会被当作 <code>char*</code>,直接传 <code>str</code> 就报 <code>ArgumentError</code>;<code>strlen</code> 数的是 UTF-8 字节数(6)而不是字符数。</p>'),
        sec('验证二:不声明类型,结果可能是错的', '<code>argtypes</code> 与 <code>restype</code>', term('', block('== 二', '== 三')),
            '<p>这是 ctypes 最容易踩的坑。<code>sqrt</code> 接受 double 返回 double:①不声明 <code>argtypes</code>,传 Python float 会 <code>ArgumentError</code>;②声明了 <code>argtypes</code> 但不声明 <code>restype</code>,默认按 <code>int</code> 读返回值,结果得到 <code>0</code>,没有任何报错;③两个都声明才对。返回指针也一样:<code>malloc</code> 默认返回值被当成 32 位整数,而真实指针超过 <code>2**32</code>,高位丢失——用这个值当地址,程序会崩或者改到不该改的内存。要声明 <code>restype = c_void_p</code>。</p>'
            '<p>(第二个 <code>malloc</code> 的两个返回值来自两次不同的调用,不是同一块内存,这里只想展示位数:错误的读法只剩 32 位。)</p>'),
        sec('验证三:编一个 C 库来调用', '数组、结构体、指针', term('', block('== 三', '== 四')),
            '<p>用 <code>cc -shared</code> 编出动态库,<code>(c_int32 * 5)(...)</code> 造一个 C 数组交给 <code>sum_array</code>;继承 <code>ctypes.Structure</code> 声明一个和 C 结构体对应的类,用 <code>byref</code> 传指针让 C 函数填写。最后一行是关键的对照:C 里 <code>sizeof(Rec)</code> 是 24,<code>value</code> 的偏移是 8,ctypes 算出来也完全一致——13 字节的字段被对齐填充到 24 字节。字段顺序或类型写得和 C 不一样,读到的就是错位的数据。</p>'),
        sec('验证四:C 反过来调用 Python', '回调函数', term('', block('== 四', '== 五')),
            f'<p>用 <code>CFUNCTYPE</code> 声明回调的类型,把 Python 函数包装后传给 C 的 <code>qsort</code>。8 个整数的排序里,C 一共回调了 Python 的比较函数 {len(calls)} 次,最后数组原地有序。每次回调都在 C 和 Python 之间来回切换,所以回调密集的场景会慢。</p>'),
        sec('验证五:调用开销', '', term('', block('== 五', '== 六')),
            f'<p>调用一次 <code>libc.abs</code> 要 {tc:.0f} ns(含外层 lambda),而 Python 自带的 <code>abs</code> 只要 {tabs:.0f} ns——ctypes 每次调用要做参数转换,不适合频繁调用「很小」的函数。但把整块数据一次交给 C:100 万个整数求和,C 函数 {t1:.2f} ms,<code>sum()</code> {t2:.1f} ms,for 循环 {t3:.0f} ms。<b>调用次数少、每次工作量大</b>才是 ctypes 的用法(注意 <code>(c_int32 * N)</code> 数组这里是事先造好的,构造它本身不算在内)。</p>'),
        sec('验证六:没有安全网', '', term('', block('== 六', 'zzzz')),
            '<p>读地址 0:Python 层没有 <code>Exception</code> 可以捕获,进程直接被 SIGSEGV(信号 11)杀死。ctypes 绕过了 Python 的类型和内存安全,任何一处 <code>argtypes</code>、结构体布局、指针生命周期写错,都可能表现为随机崩溃。上线用之前,请一定给每个函数声明 <code>argtypes</code> 和 <code>restype</code>。</p>'),
        sec('分步演示:C 的 qsort 回调 Python 的比较函数', '17 次回调的参数取自上面的真实记录',
            demo('C 调用 Python 回调', [('cells', 'cells', 'qsort 拿到的数组(蓝 = 回调的第一个参数,黄 = 第二个)'), ('log', 'term', '回调记录')], steps, '此刻被比较的两个元素')),
    ],
    refs=['本机 macOS 27 / arm64,Python 3.14.7,标准库 <code>ctypes</code>,Apple clang 21 编译 C 库',
          '没有验证:Windows 上的调用约定(WinDLL 与 CDLL 的区别)、<code>cffi</code>/Cython 与 ctypes 的性能对比、回调对象被垃圾回收后 C 仍持有指针会怎样'],
)
