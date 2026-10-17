from lib import *
S = SS('f157')
steps = [
    step("真实运行的 10 个上传测试(pytest -v -s,10 passed)。单个文件:data={'file': (io.BytesIO(b'hello'), 'a.txt'), 'title': 't1'} 提交,得到 201,视图读到 size = 5、原文件名 a.txt、表单字段 title = t1,并且文件被保存到 pytest 的 tmp_path 下(用 tmp_path 当 UPLOAD_DIR,测试结束自动清理,断言文件内容是 b'hello')。", t=tl(S(1)), done=lidx(S(1), 'test_single_file'), kv=KV([['(BytesIO, 文件名)', '元组就是一个文件字段'], ['tmp_path', '保存上传文件的临时目录']], ['tmp_path'])),
    step("不写 content_type 时,只要 data 里有文件,test client 自动用 multipart/form-data(test_content_type_is_multipart_by_default,201);文件名 b.png 没有声明类型时,服务端读到的 mimetype 是按文件名猜出来的 image/png;元组第三项可以显式声明 mimetype(test_declared_mimetype)。服务端不要信任这个 mimetype(第 126 篇)。", t=tl(S(1)), done=lidx(S(1), 'auto-multipart', 'mimetype'), kv=KV([['自动 multipart', '有文件就用'], ['mimetype', '没声明时按文件名猜']], ['自动 multipart'])),
    step("错误输入:没有文件字段 → 400「no file」;文件名是空字符串 → 同样 400(浏览器里不选文件提交时就是空文件名);同一个字段名上传多个文件,用列表 data={'files': [(f1, '1.txt'), (f2, '2.txt')]},服务端 getlist('files') 得到两个文件,names = ['1.txt', '2.txt']、sizes = [1, 2]。", t=tl(S(1)), done=lidx(S(1), 'nofile', 'emptyname', 'multi'), kv=KV([['缺文件 / 空文件名', '都要处理成 400'], ['多个文件', '列表 + getlist']], ['缺文件 / 空文件名'])),
    step("大小限制:MAX_CONTENT_LENGTH = 100 KB 时,上传 200 KB 的文件得到 413(test client 里有 Content-Length,限制生效;第 153 篇看到分块上传在真实服务器上会被悄悄截断,这一项 test client 测不到)。", t=tl(S(1)), done=lidx(S(1), 'toolarge'), kv=KV([['有 Content-Length', '超过限制 → 413']], ['有 Content-Length'])),
    step("两个容易踩的点:用磁盘上的真实文件上传时要在 with open(...) 里提交,服务端读到 30 字节(test_real_file_from_disk);传进去的文件对象如果读指针不在开头(先 read(3) 了),服务端只能读到剩下的 3 个字节(test_stream_position_matters:b'abcdef' 读掉 3 个后 size = 3)——复用同一个 BytesIO 要先 seek(0)。保存时的文件名用随机 uuid 加清洗后的扩展名,原文件名('../../evil name.txt')只作为记录,磁盘上只有 tmp_path 下的一个 .txt 文件。", t=tl(S(1)), done=lidx(S(1), 'disk', 'position', 'name'), kv=KV([['读指针', '不在开头会少读'], ['保存名', '用 uuid,不用用户给的名字']], ['读指针'])),
]
A = mkartf('f157', 157, 'Flask,测试,文件上传,multipart,pytest,tmp_path,真实验证,动画演示',
    '用真实的 pytest 运行 10 个 Flask 文件上传测试:(BytesIO, 文件名) 元组即文件字段、tmp_path 保存上传文件、自动 multipart 与按文件名猜 mimetype、缺文件与空文件名返回 400、同名多文件用列表与 getlist、200 KB 超过 100 KB 限制返回 413、读指针不在开头只会读到剩下的字节。',
    'Flask 的上传接口怎么写测试?文件怎么构造?临时目录怎么处理?哪些边界值得测?这篇用一组真实运行的 pytest 用例把写法与结果逐项列出。',
    [('10 passed', '本篇真实运行的上传测试数'), ('tmp_path', 'pytest 提供的自动清理的临时目录,用作上传目录'), ('seek(0)', '复用 BytesIO 前必须做的事,否则只会读到剩下的字节')],
    [('一组真实运行的上传测试', '<p>上一篇:<a href="flask-test-session.html">测试 Session</a>;下一篇:<a href="flask-test-error-handler.html">测试异常处理器</a>。</p><p>上传视图是一个简化版(保存到 UPLOAD_DIR、用 uuid 命名),类型校验见第 126 篇。</p>')],
    steps, [ENV_F + '。pytest 9.1.1', '没有验证:分块上传与超大文件的流式处理、Flask-WTF 的 FileField 与 FileAllowed(第 73 篇)、并发上传、真实浏览器的 multipart 边界差异、文件存对象存储时的 mock 方式'], '测试文件上传', panels=[('t', 'term', '实验输出'), ('kv', 'kv', '要点')])
