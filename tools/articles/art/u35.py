import re
from lib import *
S = SS('u35')
al = [int(x) for x in re.findall(r'堆分配 (\d+) 次', '\n'.join(S(2)))]
steps = [
    step("Cow<str>(Clone on Write)有两个变体:Borrowed(借用)与 Owned(拥有)。strip_tabs 在没有制表符时返回 Cow::Borrowed(s) —— 结果的指针与原字符串相同(没有任何分配);有制表符时才返回 Cow::Owned(s.replace(...)),分配一个新 String。调用方拿到的是同一个类型,按需处理。", t=tl(S(1)), mark=lidx(S(1), 'Borrowed', 'Owned'), kv=KV([['不需要改', 'Borrowed,零分配'], ['需要改', 'Owned,才分配']], ['不需要改'])),
    step(f"对 10000 个字符串、其中 10% 需要修改:每次都返回 String 的版本堆分配 {al[0]:,} 次;返回 Cow<str> 的版本只分配 {al[1]:,} 次(恰好是 Owned 的那 1000 个)。两者得到的总长度完全相同。绝大多数输入不需要改的场景下,Cow 省掉了大部分分配。", t=tl(S(2)), mark=lidx(S(2), '返回 Cow'), b=bars([['每次返回 String', al[0], f'{al[0]:,} 次'], ['返回 Cow<str>', al[1], f'{al[1]:,} 次']], al[0], mark=[0], done=[1]), kv=KV([['返回 String', f'{al[0]:,} 次分配'], ['返回 Cow', f'{al[1]:,} 次分配']], ['返回 Cow'])),
    step("to_mut() 是写时克隆:开始是 Borrowed(借用 hello);第一次 c.to_mut().push_str(\", world\") 时才克隆成 Owned,之后再 push 不会再克隆;原字符串 original 始终没变(仍是 \"hello\")。into_owned() 取出拥有的 String。", t=tl(S(3)), mark=lidx(S(3), 'to_mut', '是借用:false'), done=lidx(S(3), '没有被改变', 'into_owned'), kv=KV([['to_mut()', '第一次修改时克隆'], ['原数据', '不被改动']], ['to_mut()'])),
    step("大小:Cow<str> 是 24 字节,与 String 一样大(&str 是 16);Cow<[u8]> 同样是 24 字节(Vec<u8> 也是 24)。借用与拥有共用同一块空间,标签藏在容量字段的空闲位模式里(niche)—— 所以用 Cow 并不占更多内存。", t=tl(S(4)), mark=lidx(S(4), 'Cow'), kv=KV([['Cow<str>', '24 字节 = String'], ['&str', '16 字节']], ['Cow<str>'])),
]
A = mkart('u35', 35, 'Rust,Cow,写时复制,分配,真实验证,动画演示',
    f'用真实运行与计数分配器验证 Cow:没有修改时返回 Borrowed(指针与原字符串相同,零分配)、需要修改才 Owned;10000 个字符串中 10% 需要改,String 版本分配 {al[0]:,} 次而 Cow 只分配 {al[1]:,} 次;to_mut 的写时克隆;Cow<str> 与 String 同为 24 字节。',
    '「大多数时候不用改,偶尔需要改」是 Cow 的典型场景:不改就借用、改了才复制。这篇用真实的指针比较和分配计数验证它省了多少,以及 to_mut 在什么时候真正克隆。',
    [(f'{al[0]:,} → {al[1]:,}', '10000 个字符串、10% 需要改时,String 版本与 Cow 版本的堆分配次数'), ('24 字节', 'Cow<str> 的大小,与 String 相同'), ('to_mut()', '第一次修改时才克隆')],
    [('借用还是拥有', None), ('省下多少分配', '<p>分配次数用自定义 <code>#[global_allocator]</code> 计数,release 构建。</p>'), ('写时克隆', None), ('大小', '<p>niche 的原理见<a href="rust-option-ref-niche.html">Option&lt;&amp;T&gt; 的空指针优化</a>。</p>')],
    steps, [ENV_U + '。分配次数为 release 构建的单次运行', '没有验证:Cow 对运行时间的影响(只数了分配)、Cow<\'static, str> 的常见用法(错误信息)、Cow<Path>、to_mut 之后的 Cow 与 String 的互转开销、Cow 的解引用与 Deref 自动转换'], 'Cow')
