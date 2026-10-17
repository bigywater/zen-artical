import json
from lib import *
txt = out('74').splitlines()
T = json.load(open('out/74.json'))['trace']
def block(a, b):
    i = next(k for k, l in enumerate(txt) if l.startswith(a)); j = next((k for k, l in enumerate(txt) if l.startswith(b) and k > i), len(txt))
    return '\n'.join(l for l in txt[i+1:j] if l.strip())

dis = block('== 一', '== 二').splitlines()[:-1]   # 去掉 highest protocol 那行
desc = {
 'PROTO': "PROTO 2:声明协议版本。栈还是空的。",
 'GLOBAL': "GLOBAL 'posix system':按名字导入 posix.system(macOS 上 os.system 就是它),压栈。注意:这里没有任何检查。",
 'BINPUT': "BINPUT:把栈顶存进 memo 备用(为了对象引用),栈本身不变。",
 'BINUNICODE': "BINUNICODE:压入一个字符串,就是要执行的 shell 命令。",
 'TUPLE1': "TUPLE1:把栈顶的字符串打包成一个 1 元组——它将作为调用的参数。",
 'REDUCE': "REDUCE:弹出参数元组和可调用对象,执行 posix.system(*args),把返回值压栈——命令就是在这一步执行的。",
 'STOP': "STOP:弹出栈顶作为 loads 的返回值。返回的是 0(os.system 的退出码),根本不是 Evil 对象。",
}
ops = [l.split()[2] if not l.split()[1].startswith('\\x') else l.split()[2] for l in dis]
ops = [l.split()[2] for l in dis]
steps = []
for i, l in enumerate(dis):
    op = ops[i]
    if i < len(T): stack = T[i][1]
    else: stack = ['0']
    items = [s if len(s) < 40 else s[:37] + '…' for s in stack]
    hl = len(items) - 1 if items else None
    n = desc[op]
    steps.append(step(n,
        dis={'lines': [x.strip() for x in dis], 'cur': [i], 'done': list(range(i))},
        stack={'items': items, 'hl': hl if hl is not None else -1},
        ))
# 最后一步 REDUCE 之后栈只剩 0

A = dict(
    n=74,
    tags='Python,标准库,安全,序列化,真实验证,动画演示',
    desc='本机用一个只写标记文件的无害载荷真实验证:pickle.loads 在反序列化时就执行了 os.system,返回的是 0 而不是原对象;用 pickletools 反汇编 54 字节的载荷,用 allowlist 的 find_class 拦截,并把每条 opcode 之后的真实栈状态做成逐步演示。',
    lead='pickle 不是「把对象变成字节」这么简单——它的字节流是一段由虚拟机执行的小程序。这篇造了一个只往当前目录写一个文件的无害载荷,亲眼看 <code>pickle.loads</code> 是怎么在你拿到返回值之前就跑起了它。',
    facts=[('54 字节', '载荷全长,里面出现的是 posix.system,而不是任何自定义类名'), ('loads → 0', '返回值是 os.system 的退出码(int),不是 Evil 实例'), ('find_class', '重写它做 allowlist,恶意载荷被 UnpicklingError 拦下')],
    body=[
        sec('做的事:一个会「回调」的类', '<code>__reduce__</code> 告诉 pickle 「还原我的时候请调用这个函数」',
            src('实验脚本', '''class Evil:
    def __reduce__(self):
        # 序列化时返回 (可调用对象, 参数元组);反序列化时 pickle 会执行 可调用对象(*参数)
        return (os.system, ("echo pwned > PWNED.txt",))

payload = pickle.dumps(Evil(), protocol=2)
obj = pickle.loads(payload)      # 谁来执行 os.system?'''),
            '<p>载荷只做一件无害的事:在当前(临时)目录写一个 <code>PWNED.txt</code>。真实攻击里这条命令可以换成任何东西——这里把它限制到最小,只为证明「会执行」。</p>'),
        sec('验证一:载荷里是一段 opcode 程序', 'pickletools.dis 反汇编', term('', txt[0] + '\n' + '\n'.join(dis)),
            '<p>只有 10 条指令。核心是这三条:<code>GLOBAL \'posix system\'</code> 按名字导入一个函数、<code>BINUNICODE</code> 放入命令字符串、<code>REDUCE</code> 调用它。载荷里出现的是 <code>posix system</code>,并没有 <code>Evil</code> 这个类名——攻击者不需要你的代码里有任何特定的类,pickle 允许通过 <code>GLOBAL</code> 引用任何可导入的东西。</p>'),
        sec('验证二:loads 一返回,文件已经被写了', '', term('', block('== 二', '== 三') + '\n' + block('== 三', '== 四')),
            callout('<b>危险发生在反序列化这一刻,而不是你使用对象的时候。</b>返回值是 <code>0</code>(os.system 的退出码),你拿到的甚至不是一个 Evil 对象——所以用 <code>isinstance</code> 检查返回类型来防御是没用的:代码早在检查之前就执行过了。'),
            '<p>这也解释了 pickle 文档为什么反复强调「不要反序列化不可信来源的数据」:数据来源是网络、上传文件、共享缓存(比如别人也能写入的 Redis)时,等于给对方一个远程代码执行入口。</p>'),
        sec('验证三:能拦住,但要用 allowlist', '重写 <code>Unpickler.find_class</code>', term('', block('== 四', '== 五')),
            '<p>所有「按名字导入」都要经过 <code>find_class</code>,把它改成只放行明确列出的类型,恶意载荷在 <code>GLOBAL</code> 这一步就被拒了:<code>posix.system</code> 被拒绝,标记文件没有被创建,而正常的 <code>[1, 2, {\'a\': 3}]</code> 照常还原。这里用的是 allowlist(只允许白名单),不是 denylist——黑名单永远漏得掉,因为可导入的东西太多。就算这样,也只应当用在「格式受你控制但需要防御一层」的场景;来源不可信时,直接换成不会执行代码的格式。</p>'),
        sec('验证四:换成 JSON 就没有这回事', '', term('', block('== 五', '== 六')),
            '<p>同一串字节交给 <code>json.loads</code>,得到的只是解析错误;JSON 只能表示数据(对象、数组、字符串、数字),没有「调用函数」这个概念。代价是它表示不了任意 Python 对象(自定义类、集合、元组会变形),需要自己定义转换——这是安全的代价,也是刻意的。</p>'),
        sec('分步演示:载荷在 pickle 虚拟机里怎么一步步执行', '左边是上面 <code>pickletools.dis</code> 的原始输出,栈是纯 Python 版 <code>pickle._Unpickler</code> 每执行一条 opcode 后的真实内容',
            demo('pickle 虚拟机执行 54 字节载荷',
                 [('dis', 'term', '当前执行到哪条 opcode'), ('stack', 'stack', '虚拟机的栈')],
                 steps, '正在执行的 opcode / 栈顶')),
    ],
    refs=['本机 macOS 27 / Python 3.14.7,标准库 <code>pickle</code>、<code>pickletools</code>;载荷只写一个临时目录里的 PWNED.txt',
          '没有验证:其他协议版本下 opcode 的差异、<code>__setstate__</code> 等其他触发路径、C 版 Unpickler 与纯 Python 版在 find_class 上的完全等价性(演示用的是纯 Python 版,防御实验用的是默认版)'],
)
