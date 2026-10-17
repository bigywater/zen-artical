from lib import *
S = SS('n19')
steps = [
    step("三个中间件 A、B、C 加 handler,每个中间件都调用 c.Next():执行顺序是 A前 → B前 → C前 → handler → C后 → B后 → A后。“前”半段按注册顺序,“后”半段严格相反——后进先出,像剥洋葱。", t=tl(S(1)), mark=lidx(S(1), 'A前 → B前 → C前 → handler → C后 → B后 → A后'), kv=KV([['前半段', 'A → B → C(注册顺序)'], ['后半段', 'C → B → A(相反)'], ['原因', 'Next 是函数调用,返回时逐层退回']], ['后半段'])),
    step("中间件 B 不调用 c.Next(),链并没有停:A前 → B前 → B后 → C前 → handler → C后 → A后——B 提前返回,A 的 Next 循环接着执行 C 和 handler,只是 B 的“后”半段变到了 C 之前。B 调用两次 Next 与调用一次相同(第二次 Next 时下标已经走完)。要真正截断后面的 handler,必须 c.Abort():A前 → B前 → B后 → A后。", t=tl(S(2)), mark=lidx(S(2), 'B 不调用 Next', 'B 调用 Abort'), done=lidx(S(2), 'B 调用两次 Next'), kv=KV([['不调 Next', '后面的 handler 照样执行'], ['调两次 Next', '与一次相同'], ['要截断', '用 Abort']], ['不调 Next'])),
    step("“后”半段能看到的:状态 201、已写字节 5、Written 为 true、Errors 1 条。但这时响应已经写出,在后半段里 c.Header(\"X-Late\", \"1\") 和 c.Status(500) 对真实客户端无效:/x 客户端收到 201、正文 hello、没有 X-Late。如果 handler 只设了状态没写正文(/y:Status(202),Size=-1,Written=false),后半段改成 c.Status(500) 就生效:客户端收到 500,X-Late 与 X-Early 都在。", t=tl(S(3)), mark=lidx(S(3), '/x 客户端收到', '/y 客户端收到'), done=lidx(S(3), '已写出=true', '已写出=false'), kv=KV([['已写出', '后半段改状态、加头无效'], ['没写出', '后半段还能改状态和头'], ['判断', 'c.Writer.Written()']], ['判断'])),
    step("panic 的展开:Recovery 放在最外层时,A前 → B前 → handler → [Recovery 处理 panic] → 状态 500——A 和 B 的“后”半段都没有执行;Recovery 放在 A 与 B 之间时 A 的“后”半段仍会执行(A前 → B前 → handler → Recovery → A后),B 的被跳过;如果 B 用 defer 写收尾,panic 时 defer 会执行(B的defer 出现在 Recovery 之前),而“B后”不会。", t=tl(S(4)), mark=lidx(S(4), 'Recovery 在最外层', 'Recovery 在 A 与 B 之间', 'B 用 defer 写收尾'), kv=KV([['Recovery 在最外层', '所有“后”半段都被跳过'], ['Recovery 在中间', '它外面的“后”半段仍执行'], ['defer', 'panic 时仍会执行']], ['defer'])),
]
A = mkartn('n19', 19, 'Gin,中间件,c.Next,洋葱模型,panic,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测 c.Next() 的展开顺序:三个中间件的前半段按注册顺序、后半段相反;中间件不调用 Next 时后面的 handler 仍会执行;后半段里响应已写出就改不了状态和头;panic 时哪些“后”半段会被跳过。',
    '“c.Next() 之后的代码”到底什么时候执行?中间件不调 Next 会怎样?响应写出以后还能改什么?panic 时哪些后半段会被跳过?这篇用打印顺序和真实客户端把洋葱模型的细节一次看清。',
    [('先进后出', '三个中间件都调 Next 时,后半段的顺序与前半段相反'), ('handler 仍执行', '中间件 B 不调用 Next 时,后面的 C 与 handler 照常执行'), ('201 ≠ 500', '后半段里把状态改成 500,响应已写出时客户端仍收到 201')],
    [('洋葱模型', '<p><code>Next</code> 是个普通的函数调用,所以后半段的顺序和前半段完全相反:A 前、B 前、C 前、handler、C 后、B 后、A 后。需要“包住”后面所有逻辑的事情(计时、日志、统一错误处理)放在 <code>c.Next()</code> 之后。</p>'),
     ('不调 Next 不等于停下', '<p>中间件不调 <code>c.Next()</code> 只是不亲自递归,外层的 <code>Next</code> 循环会接着调下一个 handler,所以后面的中间件和 handler 仍会执行,只是执行时机变成在它的“后”半段之后。要拦截请求必须 <code>c.Abort()</code>(或 AbortWithStatus 系列)。调两次 <code>Next</code> 没有额外效果。</p>'),
     ('后半段能改什么', '<p>后半段里读得到状态、已写字节数、Errors,但响应一旦写出,<code>c.Header</code> 和 <code>c.Status</code> 对客户端就无效了。handler 只设状态而没有写正文时,响应其实还没发出,后半段改状态仍然生效。写“统一加响应头”的中间件要放在 <code>Next</code> 之前。</p>'),
     ('panic 时', '<p>panic 会跳过沿途所有“后”半段,直到被 <code>Recovery</code> 捕获。<code>Recovery</code> 放在最外层,所有后半段都不会执行;放在中间,只有它外面的后半段还能执行。需要在 panic 时也做收尾(释放锁、记录指标)的中间件应该用 <code>defer</code>。</p>')],
    steps,
    [ENV_N_GIN + '。顺序用打印记录;前两节与第四节用 httptest 直接调用 ServeHTTP,第三节用真实的 httptest.NewServer 与 http.Client(因为 httptest.ResponseRecorder 不能区分头是否已发出);每种情形各一次',
     '没有验证:Recovery 在 panic 后对 c.Writer 的处理细节(见后面 Recovery 的文章);在 handler 里启动的 goroutine 里 panic 的情形(单独一篇);gin.Default() 里 Logger 在 Recovery 外层时的顺序'],
    '洋葱模型')
