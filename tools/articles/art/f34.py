from lib import *
S = SS('f34')
R = J('f34')
steps = [
    step("同一个视图打印 args / form / files / json / data / values,12 种请求的实测:GET ?a=1 → args 有 a;GET 带 JSON 正文 → json 有值、data 有原始正文(GET 也能带正文);GET 带表单正文 → form 被解析(form={'f': '1'});POST 表单 → form 有值、data 为空;POST ?a=1 + 表单 → args 与 form 并存,values 合并两者;POST JSON → json 有值、args/form 为空;POST multipart → 文本字段进 form、文件进 files;POST text/plain → data 是 'raw text',其余都空;PUT 表单与 PATCH JSON 的行为与 POST 相同;DELETE ?a=1 → 只有 args。", t=tl(S(1)), done=lidx(S(1), 'GET ?a=1', 'POST 表单', 'POST JSON', 'POST multipart'), mark=lidx(S(1), 'GET + JSON 正文', 'GET + 表单正文', 'POST text/plain', 'PUT 表单', 'DELETE'), kv=KV([['查询串', 'args'], ['表单 / multipart 字段', 'form(与方法无关)'], ['JSON', 'json 与 data'], ['未知类型', '只有 data'], ['文件', 'files']], ['文件'])),
    step("request.json 属性与 get_json():正文是 JSON 时三种写法都得到 {'a': 1};正文是表单或没有 Content-Type 时,request.json 与 get_json() 都抛 UnsupportedMediaType(415),只有 get_json(silent=True) 返回 None。所以「可能不是 JSON」的接口要用 silent=True,或自己先判断 request.is_json。", t=tl(S(2)), done=lidx(S(2), 'JSON  '), mark=lidx(S(2), '表单', '空正文无类型'), kv=KV([['JSON 正文', '三种写法都返回对象'], ['非 JSON', 'request.json / get_json() 抛 415'], ['silent=True', '返回 None']], ['非 JSON'])),
    step("request.data 只在 Werkzeug 不解析的类型下有内容:POST 表单的 data 是空串,POST JSON 的 data 是 {\"j\": 1} 原始文本,text/plain 的 data 是 raw text(get_data_len = 8)。表单与 multipart 被解析成 form/files 之后,原始正文就拿不到了。", t=tl(S(3)), done=lidx(S(3), '从第一节'), kv=KV([['表单', 'data 为空'], ['JSON', 'data = 原始文本'], ['text/plain', 'data = raw text']], ['表单'])),
    step("同名时的优先级:POST /all?k=args 带表单 k=form:args['k'] = 'args'、form['k'] = 'form'、values['k'] = 'args' —— values 里 args 在前,所以不要用 values 去区分「来自查询串还是表单」。", t=tl(S(4)), done=lidx(S(4), 'args["k"]'), kv=KV([['args[\"k\"]', 'args'], ['form[\"k\"]', 'form'], ['values[\"k\"]', 'args(args 在前)']], ['values[\"k\"]'])),
    step("类型差别:?id=5 里 args['id'] 是字符串 '5';JSON {\"id\": 5} 里 json['id'] 是整数 5。查询串与表单的值永远是字符串(要用 type=int 转换),JSON 保持原有类型。", t=tl(S(5)), done=lidx(S(5), 'args["id"]'), kv=KV([['args[\"id\"]', "'5'(str)"], ['json[\"id\"]', '5(int)']], ['json[\"id\"]'])),
]
A = mkartf('f34', 34, 'Flask,request.args,request.form,request.json,真实验证,动画演示',
    '12 种请求(GET/POST/PUT/PATCH/DELETE × 查询串/表单/JSON/multipart/text)里 args、form、files、json、data、values 各自拿到什么;request.json 在非 JSON 时抛 415 而 get_json(silent=True) 返回 None;values 里 args 在前;JSON 保留类型而查询串与表单都是字符串。',
    '数据从哪里读:args、form、json、data、values 到底有什么区别?GET 能带正文吗?PUT 的表单会被解析吗?这篇用一个视图和 12 种请求做出一张对照表。',
    [('12', '本篇对照的请求种类数'), ('415', 'request.json 遇到非 JSON 正文时的状态码'), ('args 在前', 'request.values 合并时的顺序')],
    [('12 种请求对照', '<p>上一篇:<a href="flask-form-data-json-body.html">Form Data 与 JSON Body</a>;下一篇:<a href="flask-file-upload-filestorage.html">文件上传与 FileStorage</a>。</p>'), ('request.json 与 get_json', None), ('request.data', None), ('同名时的优先级', None), ('类型差别', None)],
    steps, [ENV_F, '没有验证:chunked 与 gzip 压缩的请求体、真实浏览器的 GET 带正文行为、request.values 在 Flask 其它版本里的合并顺序、Content-Type 带 boundary 错误的 multipart'], 'args / form / json')
