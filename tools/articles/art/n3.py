from lib import *
S = SS('n3')
steps = [
    step("两条独立的路由:/u/:id 与 /s/*p。:id 只吃一段:/u/1 → id=\"1\";/u/1/2 → 404;/u/ 和 /u 也是 404(没有空的 :id);%20 和中文会被解码成 \"a b\" 与 \"中文\"。*p 吞掉剩下的全部:/s/ → p=\"/\";/s/a/b/c → p=\"/a/b/c\";/s 被 301 到 /s/;/s//x 的 p 是 \"//x\"。", t=tl(S(1)), mark=lidx(S(1), '/u/1/2', '/u/                        →', '/s/a/b/c', '/s//x'), done=lidx(S(1), '/u/1                       →', '/s/                        →'), kv=KV([[':id', '一段,不能为空'], ['*p', '剩下的全部,可以只是 "/"'], ['/s', '301 到 /s/']], ['*p'])),
    step("十种注册组合里 8 种 panic,panic 信息把冲突的位置拼出来:/x/:id 与 /x/*p,不管谁先谁后;/x/:id 与 /x/:name(名字不同,即使后面还有静态段);*p 后面还有路径;/x/*p 与静态 /x/ 或 /x/a 同位置;/x/a 先注册再注册 /x/*p。只有同名 :id 后面接不同静态段、以及静态 /x/new 与 /x/:id 共存这两种能成功。", t=tl(S(2)), mark=lidx(S(2), 'conflicts with existing wildcard', 'only allowed at the end', 'conflicts with existing path segment'), done=lidx(S(2), '注册成功'), b=bars([['panic', 8, '8 种'], ['注册成功', 2, '2 种']], 10, mark=[0], done=[1]), kv=KV([['8 / 10', '会 panic 的组合'], ['能共存', '同名 :id 接不同后缀;静态与 :id']], ['8 / 10'])),
    step("*p 的值总是以 / 开头:/files/a/b.txt → p=\"/a/b.txt\",所以常见写法是 p[1:];/files/ → p=\"/\",去掉斜杠后是空串,代码里要处理;/files/a//b 保持原样 \"/a//b\";/files/%2e%2e/x 与 /files/../x 的 p 都是 \"/../x\"(Gin 没有清理路径,也没有拒绝 ..)。", t=tl(S(3)), mark=lidx(S(3), '/files/                    →', '/files/%2e%2e/x', '/files/../x'), done=lidx(S(3), '/files/a/b.txt'), kv=KV([['*p 的开头', '一定有 /'], ['/files/', 'p="/",去掉斜杠后为空'], ['/files/../x', 'p="/../x",Gin 不清理']], ['/files/../x'])),
    step("/files/:name 不能匹配带斜杠的名字:/files/dir/a.txt → 404;把斜杠编码成 %2F 的 /files/dir%2Fa.txt 默认也是 404(默认用 URL.Path,已经解码成带斜杠的路径)。把 UseRawPath 与 UnescapePathValues 都设为 true 之后,%2F 的这条请求命中 :name,name=\"dir/a.txt\";而没编码的 /files/dir/a.txt 仍然 404。", t=tl(S(4)), mark=lidx(S(4), '/files/dir%2Fa.txt         → 200'), done=lidx(S(4), 'UseRawPath=true'), kv=KV([['默认', '%2F 解码后变成斜杠,:name 匹配不了'], ['UseRawPath + UnescapePathValues', 'name="dir/a.txt"'], ['没编码的斜杠', '始终是两段']], ['UseRawPath + UnescapePathValues'])),
]
A = mkartn('n3', 3, 'Gin,路由,参数路由,通配符,catchAll,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测 :id 与 *path 的差别::id 只匹配一段且不能为空,*path 匹配剩余的全部且值以斜杠开头;10 种注册组合里 8 种会在注册时 panic;/files/:name 默认匹配不了带 %2F 的名字,开 UseRawPath 后才行。',
    ':id 和 *path 看起来只是“少一段”和“多一段”的区别,但它们的节点类型、冲突规则、值的格式都不一样。这篇用同一批请求打在两种路由上,再把能不能共存的十种组合逐个注册一遍,把 panic 原文列出来。',
    [('8 / 10', '十种注册组合里会 panic 的个数'), ('"/a/b.txt"', '*p 取到的值,开头带斜杠'), ('%2F', '默认 404;开 UseRawPath 后 name="dir/a.txt"')],
    [(':id 与 *p 各自匹配什么', '<p><code>:id</code> 只匹配到下一个斜杠为止,而且不能为空:<code>/u/1/2</code>、<code>/u/</code> 都是 404。<code>*p</code> 把斜杠之后的所有内容当成一个值,哪怕只是一个 <code>/</code>。URL 里的 <code>%20</code> 和中文在取值时已经解码。</p><p>注意 <code>/s</code> 没有匹配而是被 301 重定向到 <code>/s/</code>:*p 前面的斜杠是路由的一部分。</p>'),
     ('冲突:什么情况下注册会 panic', '<p>同一位置只能有一种通配符:<code>:id</code> 与 <code>*p</code> 不能并存,<code>:id</code> 与 <code>:name</code> 也不行(即使它们后面跟着不同的静态段)。catch-all 只能出现在路径末尾,而且不能与同一位置的静态路径并存,先后顺序都一样。能共存的是:同名的 <code>:id</code> 后面接不同的静态段,以及静态路径与 <code>:id</code> 并存(下一篇会逐个验证)。</p>'),
     ('*p 的值与路径穿越', '<p><code>*p</code> 的值总是以 <code>/</code> 开头,所以用它拼文件路径时常写 <code>p[1:]</code>,并且要处理空串。<code>/files/../x</code> 和 <code>/files/%2e%2e/x</code> 的 p 都是 <code>"/../x"</code>——Gin 的路由不会清理或拒绝 <code>..</code>,把它拼进文件路径之前必须自己处理。</p>'),
     ('带斜杠的参数', '<p><code>:name</code> 永远是一段。默认情况下 Gin 用已经解码的 <code>URL.Path</code> 匹配,<code>%2F</code> 解码成斜杠后就变成了两段,所以 404;把 <code>UseRawPath</code> 和 <code>UnescapePathValues</code> 都设为 true,就改用 <code>RawPath</code> 匹配、再对取出的值解码,这时 <code>dir%2Fa.txt</code> 能命中,值是 <code>dir/a.txt</code>。</p>')],
    steps,
    [ENV_N_GIN + '。请求都用 httptest 直接调用 Engine.ServeHTTP,没有经过真实的 http.Server(所以没有 http.ServeMux 的路径清理);每种情形各一次',
     '没有验证:真实 http.Server 对 %2F、.. 的预处理(我只用 httptest 构造请求);UseRawPath 对其它特殊字符的影响;catch-all 值里的非 UTF-8 字节;Gin 其他版本里冲突规则的差异(只测了 v1.12.0)'],
    ':id 与 *path')
