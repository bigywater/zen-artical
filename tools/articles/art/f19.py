from lib import *
S = SS('f19')
R = J('f19'); c = R['cost']
steps = [
    step("两个自定义转换器:ListConverter(regex 匹配逗号分隔的词,to_python 返回列表)与 UserConverter(regex \\d+,to_python 去字典里查用户,查不到就 raise ValidationError)。注册方式是 app.url_map.converters['list'] = ListConverter。结果:GET /tags/a,b,c → 200,视图收到 list ['a', 'b', 'c'];/tags/solo → ['solo'];/tags/a,,b 不匹配 regex → 404;/u/1 → 收到字典 {'id': 1, 'name': 'ann'};/u/3(用户不存在,ValidationError)与 /u/abc → 404。", t=tl(S(1)), done=lidx(S(1), '/tags/a,b,c', '/u/1', '/u/2'), mark=lidx(S(1), '/tags/a,,b', '/u/3', '/u/abc'), kv=KV([['to_python', '把 URL 片段变成 Python 对象'], ['ValidationError', '→ 404'], ['不匹配 regex', '→ 404']], ['ValidationError'])),
    step("to_url 负责反向生成:url_for('tags', tags=['x','y','z']) → /tags/x,y,z;url_for('user', u={'id': 2, ...}) → /u/2;含空格的 ['a b', 'c'] → /tags/a%20b,c(to_url 里调用 BaseConverter.to_url 做了 URL 转义)。视图收到的对象能直接传回 url_for。", t=tl(S(2)), done=lidx(S(2), 'url_for("tags", tags=["x"', 'url_for("user"'), mark=lidx(S(2), 'a b'), kv=KV([['列表 → URL', '/tags/x,y,z'], ['用户对象 → URL', '/u/2'], ['空格', '%20 转义']], ['用户对象 → URL'])),
    step("转换器必须在注册路由之前加入 url_map.converters:新建的应用上直接用 <list:v> 注册路由,抛 LookupError「the converter 'list' does not exist」。", t=tl(S(3)), mark=lidx(S(3), 'LookupError'), kv=KV([['未注册的转换器', "LookupError: the converter 'list' does not exist"]], ['未注册的转换器'])),
    step("转换失败(ValidationError)与视图里 abort(404) 对比:GET /u/3 得到 404,触发的回调只有 before_request(视图没有执行);GET /v/1 视图里 abort(404),触发 before_request 与 view。两者的最终状态码都是 404,但 before_request 都会执行,因为路由异常是在分发时才抛出的。", t=tl(S(4)), mark=lidx(S(4), 'GET /u/3', 'GET /v/1'), kv=KV([['ValidationError', 'before_request 执行,视图不执行'], ['abort(404)', 'before_request 与视图都执行']], ['ValidationError'])),
    step(f"开销:匹配 /u/<user:u>(转换器里有一次字典查找)每个请求 {c[0]:.1f} µs,匹配内置 /u/<int:u> 是 {c[1]:.1f} µs,差 {c[0] - c[1]:.1f} µs —— 在 test client 的测量精度内没有可见差别。", t=tl(S(5)), b=bars([['自定义 user 转换器', c[0], f'{c[0]:.1f} µs'], ['内置 int', c[1], f'{c[1]:.1f} µs']], max(c), done=[0, 1]), kv=KV([['自定义转换器', f'{c[0]:.1f} µs'], ['内置 int', f'{c[1]:.1f} µs']], ['自定义转换器'])),
]
A = mkartf('f19', 19, 'Flask,自定义转换器,BaseConverter,路由,真实验证,动画演示',
    '实现并验证两个自定义 URL 转换器(逗号分隔的列表、按 ID 查用户并在不存在时 404):to_python 与 to_url 的作用、ValidationError 变成 404、未注册转换器的 LookupError、与 abort(404) 触发回调的差别、开销与内置 int 无明显差别。',
    '想让 URL 里的 /u/<user:u> 直接给视图一个用户对象,怎么写转换器?转换失败会怎样?url_for 又怎么反过来?这篇写两个转换器并实测。',
    [('2', '一个转换器必须提供的两个方法:to_python 与 to_url(本篇实现)'), ('404', '转换失败(ValidationError)与 regex 不匹配的最终状态码'), (f'{c[0] - c[1]:.1f} µs', '自定义转换器相对内置 int 的每请求差(test client)')],
    [('两个转换器', '<p>上一篇:<a href="flask-url-converters.html">path、int、float、uuid 转换器</a>;下一篇:<a href="flask-trailing-slash.html">路由中的尾部斜杠行为</a>。</p>'), ('to_url', None), ('注册时机', None), ('ValidationError 与 abort', None), ('开销', None)],
    steps, [ENV_F, '没有验证:转换器 weight 属性对优先级的影响(只在上一篇读到内置转换器的权重)、转换器里访问数据库的事务边界问题、part_isolating 属性的作用、给转换器传参数(如 <list(sep=","):x>)的写法'], '自定义转换器')
