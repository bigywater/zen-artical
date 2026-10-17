from lib import *
S = SS('f103')
R = J('f103')
steps = [
    step("request.args.get('n', type=int) 转换失败时悄悄回退成默认值,不报错:'abc'、'12abc'、''、'1.5' 都回退成默认值;而 int() 能接受的写法都被当成合法:' 12 '(带空格)→ 12、'1_000' → 1000、'+5' → 5、阿拉伯-印度数字 '١٢' → 12、20 位的大整数也原样通过(没有上限)。所以「不报错」不等于「合法」,范围还得自己查。", t=tl(S(1)), mark=lidx(S(1), "'abc'", "'12abc'", "''", "'1.5'"), done=lidx(S(1), "' 12 '", "'1_000'", "'+5'", "'١٢'", '99999999999999999999'), kv=KV([['转换失败', '悄悄回退成默认值'], ['int() 接受的', '空格、下划线、+、Unicode 数字都放行'], ['范围', '不检查']], ['转换失败'])),
    step("type=float 接受 'nan'、'inf'、'-inf',甚至 '1e400' 变成 inf——后续做比较或排序时会出问题;type=bool 实际是 bool(字符串):'false'、'0'、'1' 都是 True,只有空字符串是 False。要解析布尔值得自己写映射。", t=tl(S(2)), mark=lidx(S(2), "'nan'", "'inf'", "'1e400'", "'false'", "'0'"), kv=KV([['float', '接受 nan / inf'], ['bool', "'false' 也是 True"]], ['bool'])),
    step("路径转换器 <int:i> 不匹配时是 404,不是 400:/items/abc、/items/-1、/items/1.5 都是 404;/items/007 得到 7;阿拉伯-印度数字 /items/٣ 也匹配,得到 3。负数不被 int 转换器接受(默认不带符号)。", t=tl(S(3)), mark=lidx(S(3), 'abc', '-1', '1.5'), done=lidx(S(3), '007', '٣', '/items/5'), kv=KV([['不匹配', '404'], ['负数', '默认不匹配'], ['Unicode 数字', '也匹配']], ['不匹配'])),
    step("直接 request.json['name']:缺少键是 500(普通 dict 的 KeyError,不是 400——只有 request.args 与 request.form 这类 MultiDict 缺键才会变成 400);请求体是列表时也是 500;类型错误的值(name 是整数 12345、name 是嵌套对象)原样放行。读 JSON 必须自己校验类型,而且校验失败要明确返回 4xx。", t=tl(S(4)), mark=lidx(S(4), '缺 name', '列表'), done=lidx(S(4), '整数', '嵌套'), kv=KV([['缺键 / 不是对象', '500'], ['类型错误', '放行']], ['缺键 / 不是对象'])),
    step("手写校验函数一次收集所有错误并返回 422:合法 → 201;name 缺失加 age 越界 → 422 同时报两个字段;age 是字符串 '30' → 422;age 是 true → 422(要排除 bool,因为 True 是 int 的子类);请求体是列表 → 422;非法 JSON(get_json(silent=True) 返回 None)→ 422。", t=tl(S(5)), done=lidx(S(5), '合法', '请求体是列表'), mark=lidx(S(5), 'name 缺失', 'age 是字符串', 'age 是 true', '非法 JSON'), kv=KV([['一次返回所有错误', '422 + 按字段的 errors'], ['bool', 'isinstance(True, int) 为真,要排除']], ['一次返回所有错误'])),
    step("分页参数夹到合法区间:没传 → limit 20、offset 0;limit=0 → 1;limit=100000 → 100;负数 → 夹到最小值;limit=abc → 默认 20。getlist('id', type=int) 对 ?id=1&id=2&id=x&id=3 返回 [1, 2, 3]——无法转换的 x 被悄悄丢掉。", t=tl(S(6)), done=lidx(S(6), '/page', 'getlist'), kv=KV([['limit / offset', 'max(min()) 夹到区间'], ['getlist', '无法转换的元素被丢掉']], ['limit / offset'])),
    step("请求体大小限制:MAX_CONTENT_LENGTH = 1000 字节时,500 与 1000 字节的请求是 200,1001 与 5000 字节是 413(Request Entity Too Large)。不设这个配置时没有上限。", t=tl(S(7)), mark=lidx(S(7), '1001', '5000'), done=lidx(S(7), '500', '请求体 1000'), kv=KV([['MAX_CONTENT_LENGTH', '超过就 413']], ['MAX_CONTENT_LENGTH'])),
]
A = mkartf('f103', 103, 'Flask,请求校验,参数校验,422,MAX_CONTENT_LENGTH,真实验证,动画演示',
    '实测 Flask 请求参数校验的陷阱:args.get(type=int) 转换失败悄悄回退并接受带空格、下划线、Unicode 数字;type=float 接受 nan 与 inf;type=bool 对 "false" 返回 True;int 转换器不匹配是 404;request.json 缺键是 500 而不是 400;手写校验一次返回全部错误;MAX_CONTENT_LENGTH 返回 413。',
    '拿到请求参数之后,Flask 自己替你检查了什么?type=int 失败会怎样?JSON 里缺字段会返回什么?这篇用 test_client 把各种边界输入的结果逐个打印出来。',
    [('不报错 ≠ 合法', 'args.get(type=int) 失败时回退默认值,而 \' 12 \'、\'1_000\'、Unicode 数字都被接受'), ('500', 'request.json["name"] 缺键与请求体是列表时的状态码(不是 400)'), ('413', '请求体超过 MAX_CONTENT_LENGTH 时的状态码')],
    [('type=int 的行为', '<p>上一篇:<a href="flask-api-error-format.html">API 错误响应统一格式</a>;下一篇:<a href="flask-api-pagination.html">API 分页</a>。</p>'), ('float 与 bool', None), ('路径转换器', None), ('JSON 请求体', None), ('手写校验', '<p>第 115、116 篇会用 Marshmallow 与 Pydantic 做同样的事。</p>'), ('分页参数', None), ('请求体大小', None)],
    steps, [ENV_F, '没有验证:Marshmallow、Pydantic、webargs 等库的校验(见第 115、116 篇)、multipart 表单与文件上传的校验、MAX_FORM_MEMORY_SIZE 与 MAX_FORM_PARTS 配置、真实 HTTP 下 Content-Length 缺失(分块上传)时的 MAX_CONTENT_LENGTH 行为'], '请求参数校验')
