from lib import *
S = SS('f37')
R = J('f37'); rl_ = R['real']
steps = [
    step("MAX_CONTENT_LENGTH 默认是 None(不限制),request.max_content_length 也是 None。设成 1000 后:POST 500 字节 → 200;恰好 1000 字节 → 200;1001 字节与 100000 字节 → 413「Request Entity Too Large」。", t=tl(S(1)), done=lidx(S(1), '默认配置', '设成 1000 后', '正文    500', '正文   1000'), mark=lidx(S(1), '正文   1001', '正文 100000'), kv=KV([['默认', 'None(不限制)'], ['≤ 1000 字节', '200'], ['> 1000 字节', '413']], ['> 1000 字节'])),
    step("检查发生在读取请求体的时候:视图完全不读请求体时,即使发 100000 字节(超限)也是 200;multipart 上传 5000 字节的文件(访问 request.files 时触发解析)→ 413,异常类型 RequestEntityTooLarge。", t=tl(S(2)), done=lidx(S(2), '视图完全不读请求体'), mark=lidx(S(2), 'multipart 上传'), kv=KV([['不读请求体', '不检查,200'], ['读 request.files / data', '超限 → 413']], ['读 request.files / data'])),
    step("Flask 3.1 可以按请求设置:全局不限制时,视图里在读取之前设 request.max_content_length = 100,发 500 字节 → 413,发 50 字节 → 200。适合对不同的接口设不同的上限(上传接口大、普通接口小)。", t=tl(S(3)), done=lidx(S(3), '全局不限制'), kv=KV([['request.max_content_length = 100', '500 字节 → 413;50 字节 → 200']], ['request.max_content_length = 100'])),
    step(f"真实 HTTP(gunicorn + curl,限制 1 MB):500 KB 的文件 → {rl_['500 KB(限制内)']};30 MB 的文件 → {rl_['30 MB(超限)']}(服务端读到限制附近就返回 413,curl 只发出了一小部分);视图不读请求体时 30 MB → {rl_['30 MB,视图不读请求体']}(同样只发出一小部分);30 MB 的 chunked 请求(没有 Content-Length)→ {rl_['30 MB chunked(无 Content-Length)']} —— 这里视图 get_data() 返回的恰好是 1048576 字节(限制值),状态码是 200:服务端按限制读取,多出的部分被截断,没有报 413。这是本机这一组实验的结果,用 chunked 上传时不能指望 MAX_CONTENT_LENGTH 一定返回 413。", t=tl(S(4)), done=lidx(S(4), '500 KB(限制内)'), mark=lidx(S(4), '30 MB(超限)', '30 MB,视图不读请求体', 'chunked'), kv=KV([['30 MB + Content-Length', '413,客户端只发出一小部分'], ['不读请求体', '200,同样只发出一小部分'], ['30 MB chunked', '200,get_data 只有 1048576 字节']], ['30 MB chunked'])),
    step("413 响应本身:默认是「413 Request Entity Too Large」的 HTML 页;@errorhandler(413) 可以返回 JSON,例如 {'error': 'payload too large', 'limit': 10}。", t=tl(S(5)), done=lidx(S(5), '自定义 413 处理器', '默认 413 页'), kv=KV([['默认', 'HTML 413 页'], ['errorhandler(413)', '可返回 JSON']], ['errorhandler(413)'])),
]
A = mkartf('f37', 37, 'Flask,上传大小限制,MAX_CONTENT_LENGTH,413,真实验证,动画演示',
    '实测 MAX_CONTENT_LENGTH:默认不限制;超限返回 413;只在读请求体时才检查;Flask 3.1 可按请求设 request.max_content_length;真实 gunicorn + curl 上传 30 MB 在限制 1 MB 时很快返回 413(只发出一部分);chunked 上传在本机实测里被截断到限制大小却返回 200。',
    '上传文件大小怎么限制?超限时服务器读了多少?限制什么时候检查?chunked 上传也受限吗?这篇既用 test client 也用真实的 30 MB 上传来验证。',
    [('413', '超过 MAX_CONTENT_LENGTH 时的状态码'), ('1048576', 'chunked 30 MB 上传时视图 get_data() 实际拿到的字节数(限制 1 MB)'), ('None', 'MAX_CONTENT_LENGTH 的默认值')],
    [('默认不限制', '<p>上一篇:<a href="flask-multi-file-upload.html">多文件上传</a>;下一篇:<a href="flask-secure-filename.html">secure_filename() 的安全处理</a>。</p>'), ('检查发生的时机', None), ('按请求设置', None), ('真实上传 30 MB', None), ('413 响应', None)],
    steps, [ENV_F, '没有验证:Nginx 的 client_max_body_size 与 Flask 限制的先后(见第 174 篇)、uWSGI 对请求体的缓冲行为、chunked 请求超限时是否有更严格的设置、curl 在服务端提前关闭连接时的重试行为、MAX_FORM_MEMORY_SIZE 与 MAX_CONTENT_LENGTH 的关系', 'chunked 上传「截断而不报错」是本机 Flask 3.1.3 + Werkzeug 3.1.9 + gunicorn 26.2.0 下的一次实测,没有查证这是否是设计行为'], '上传大小限制')
