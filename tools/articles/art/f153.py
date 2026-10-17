from lib import *
S = SS('f153')
R = J('f153'); hd = R['hdrs']; ho = R['host']
steps = [
    step(f"响应头:同一个 /hello,test client 返回的只有 content-length 与 content-type;真实 gunicorn 多出 connection、date、server 三个头。依赖这些头的行为(缓存的 Date、反向代理对 Connection 的处理)在 test client 里测不到。", t=tl(S(1)), done=lidx(S(1), 'test client:', 'gunicorn   :'), mark=lidx(S(1), '多出'), kv=KV([['test client', 'content-length、content-type'], ['gunicorn 多出', 'connection、date、server']], ['gunicorn 多出'])),
    step("路径里的 %2F、双斜杠与中文:/p/a%2Fb 在 test client 与 gunicorn 里都得到 name = a/b、path = /p/a/b(编码的斜杠被解码成了路径分隔符);/p/a//b 两边都保留双斜杠;/p/%E4%B8%AD 都解码成中文。这几项两边一致。", t=tl(S(2)), done=lidx(S(2), '/p/a%2Fb', '/p/a//b', '/p/%E4%B8%AD'), kv=KV([['路径解码', 'test client 与 gunicorn 一致']], ['路径解码'])),
    step("上传:MAX_CONTENT_LENGTH = 1000。test client 发 3000 字节(有 Content-Length)得到 413;但对真实 gunicorn 发 3000 字节的分块上传(没有 Content-Length,Transfer-Encoding: chunked),响应是 200,视图读到的 n = 1000——请求体被悄悄截断到了上限,没有 413。分块上传的行为在 test client 里没有简单的模拟办法(data 传迭代器会报 AttributeError),只能用真实服务器验证。对必须拒绝超长上传的接口,不能只靠 MAX_CONTENT_LENGTH,还要在反向代理层限制(见第 134 篇的 client_max_body_size)。", t=tl(S(3)), mark=lidx(S(3), '真实 gunicorn'), done=lidx(S(3), 'test client,3000'), kv=KV([['test client', '有 Content-Length → 413'], ['真实 chunked 上传', '200,被截断到 1000 字节']], ['真实 chunked 上传'])),
    step("视图抛异常:TESTING=True 时 test client 把异常直接抛进测试代码(RuntimeError: view exploded);TESTING=False 时返回 500;真实 gunicorn 返回 500。所以测试里想验证「出错时返回 500」要把 TESTING 设为 False,或设置 PROPAGATE_EXCEPTIONS = False。", t=tl(S(4)), done=lidx(S(4), 'TESTING=True', 'TESTING=False', '真实 gunicorn'), kv=KV([['TESTING=True', '异常传播给测试'], ['TESTING=False / 真实服务器', '返回 500']], ['TESTING=True'])),
    step(f"默认的请求头与主机:test client 请求里 request.host 是 localhost、User-Agent 是 Werkzeug/3.1.9、url 是 http://localhost/host;真实的 http.client 请求 host 是 127.0.0.1:端口,User-Agent 为空(None)。测试里依赖 UA 或 Host 的逻辑要显式设置这些头。", t=tl(S(5)), done=lidx(S(5), 'test client:', '真实 http.client:'), kv=KV([['test client', 'host=localhost,UA=Werkzeug/3.1.9'], ['真实客户端', '取决于客户端,这里 UA 为空']], ['test client'])),
    step("重定向的 Location:对 /dir(规则是 /dir/)的 308,test client 的 Location 是 http://localhost/dir/,真实 gunicorn 是 http://127.0.0.1:端口/dir/——都是绝对地址,主机取决于请求的 Host。", t=tl(S(6)), done=lidx(S(6), 'test client', 'gunicorn'), kv=KV([['Location', '绝对地址,主机随请求的 Host']], ['Location'])),
]
A = mkartf('f153', 153, 'Flask,测试,test_client,真实HTTP,差异,真实验证,动画演示',
    '同一个应用在 test_client 与真实 gunicorn 里的差异:响应头(date、server、connection)、路径解码一致、分块上传在 MAX_CONTENT_LENGTH 下被悄悄截断到 1000 字节而不是 413、TESTING 决定异常是传播还是 500、默认的 Host 与 User-Agent、重定向的 Location。',
    'test_client 里测过了,真实服务器上就一定一样吗?哪些行为只有真实 HTTP 才能验证?这篇把同一个应用放在两边,把差异逐项对照出来(包括一个我没预料到的分块上传结果)。',
    [('200 而不是 413', '分块上传超过 MAX_CONTENT_LENGTH 时,真实服务器的结果(内容被截断到上限)'), ('3 个头', '真实服务器比 test client 多出的响应头:connection、date、server'), ('TESTING', '决定视图异常是传播给测试还是返回 500 的开关')],
    [('响应头', '<p>上一篇:<a href="flask-test-request-context.html">test_request_context()</a>;下一篇:<a href="flask-fixtures-app-factory.html">Fixture 与测试应用工厂</a>。</p>'), ('路径解码', None), ('分块上传与大小限制', '<p>第一次运行这一节时我把请求里的换行写错了(写成了字面的反斜杠),得到一个 500,以为是服务器行为,检查输出才发现是我发的请求本身有问题。修正后才看到真实的结果。</p>'), ('异常', None), ('默认的请求头', None), ('重定向', None)],
    steps, [ENV_F + '。gunicorn sync worker', '没有验证:keep-alive 与 HTTP/1.0 的差异、nginx 在中间时的差异、Expect: 100-continue、非常大的头部、HTTP/2、客户端断开连接时视图的行为'], 'test_client 与真实 HTTP 差异')
