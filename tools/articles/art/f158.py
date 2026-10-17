from lib import *
S = SS('f158')
steps = [
    step("真实运行的 8 个异常处理器测试(pytest -v -s,8 passed)。应用里有:自定义异常 PaymentError 的处理器(402)、404 处理器、500 处理器、一个蓝图里的 ValueError 处理器。自定义异常:GET /pay → 402 {code: card_declined, error: payment};404:GET /nope → 404 {error: not found};没有注册处理器的 abort(403) → 403,Content-Type 是 text/html(默认的错误页)。", t=tl(S(1)), done=lidx(S(1), 'custom', '404', 'abort403'), kv=KV([['注册了处理器的', '返回自己的 JSON'], ['没注册的 abort(403)', '默认 HTML 页']], ['注册了处理器的'])),
    step("TESTING=True 时,没有被专门处理的异常(视图里 raise RuntimeError)会直接抛进测试代码——用 pytest.raises(RuntimeError, match='unexpected') 才接得住,500 处理器不会被调用;TESTING=False 时同样的请求返回 500 {error: server error},500 处理器被调用;在 TESTING=True 里再把 PROPAGATE_EXCEPTIONS 设成 False,也得到 500 {error: server error}。测试「出错时的 500 响应」要关掉异常传播;测试「视图确实抛了某个异常」则要保留它。(注册了针对具体异常类的处理器,比如 PaymentError,在 TESTING 下仍然生效。)", t=tl(S(1)), done=lidx(S(1), 'propagate raised', '500handler', 'propagate-off'), kv=KV([['TESTING=True', '未处理的异常抛进测试'], ['PROPAGATE_EXCEPTIONS=False', '走 500 处理器']], ['TESTING=True'])),
    step("蓝图处理器的作用范围:蓝图里的视图抛 ValueError,蓝图的 ValueError 处理器接住,返回 400 {error: bp value error};蓝图之外的视图抛同样的 ValueError,处理器不适用,异常直接传播给测试(pytest.raises(ValueError))。最后一个测试把错误响应的字段集合固定为 {code, error},作为对调用方的格式约定——错误格式变了,这个测试会失败。", t=tl(S(1)), done=lidx(S(1), 'bp-inside', 'bp-outside', 'contract'), kv=KV([['蓝图处理器', '只管蓝图自己的视图'], ['格式约定', '用测试固定字段集合']], ['蓝图处理器'])),
]
A = mkartf('f158', 158, 'Flask,测试,异常处理器,errorhandler,pytest,真实验证,动画演示',
    '用真实的 pytest 运行 8 个 Flask 异常处理器测试:自定义异常与 404 处理器返回 JSON、没注册的 abort 返回默认 HTML、TESTING 下未处理的异常抛进测试而 PROPAGATE_EXCEPTIONS=False 或 TESTING=False 时走 500 处理器、蓝图处理器只管蓝图自己的视图、用测试固定错误响应的字段。',
    '怎么测试 errorhandler?为什么测试里 500 处理器有时不执行?异常什么时候抛进测试、什么时候变成 500?蓝图里的处理器管到哪里?这篇用一组真实运行的 pytest 用例把规则一条条验证。',
    [('8 passed', '本篇真实运行的异常处理器测试数'), ('pytest.raises', 'TESTING=True 时接住视图里未处理异常的写法'), ('PROPAGATE_EXCEPTIONS', '设成 False 后未处理的异常走 500 处理器的开关')],
    [('一组真实运行的异常处理器测试', '<p>上一篇:<a href="flask-test-file-upload.html">测试文件上传</a>;下一篇:<a href="flask-test-blueprint.html">测试 Blueprint</a>。</p><p>第 102 篇讲过统一错误格式的写法,这一篇讲怎么测试它。</p>')],
    steps, [ENV_F + '。pytest 9.1.1', '没有验证:异步视图里的异常、处理器本身抛出异常时的行为、Sentry 等错误上报与处理器的配合、abort 带自定义 description 的 JSON 化、before_request 里抛出的异常走哪个处理器'], '测试异常处理器', panels=[('t', 'term', '实验输出'), ('kv', 'kv', '要点')])
