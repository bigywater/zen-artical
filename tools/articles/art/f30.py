from lib import *
S = SS('f30')
R = J('f30'); rl_ = R['real']
steps = [
    step("路径里的中文:浏览器发的是百分号编码的 UTF-8。GET /%E7%94%A8%E6%88%B7/%E5%BC%A0%E4%B8%89 → 200,视图里 name = '张三'、request.path = '/用户/张三';大写与小写十六进制(%e7%94%a8)结果相同。WSGI 的 PATH_INFO 是把 UTF-8 字节按 latin-1 解成的 str,在 environ 里看起来是乱码(ç\\x94¨æ\\x88·…),Werkzeug 再还原。", t=tl(S(1)), done=lidx(S(1), 'GET /%E7%94', 'GET /用户/张三'), mark=lidx(S(1), 'PATH_INFO'), kv=KV([['request.path', '/用户/张三(已解码)'], ['environ PATH_INFO', '按 latin-1 解的字节(乱码形式)'], ['大小写十六进制', '等价']], ['environ PATH_INFO'])),
    step("查询字符串:name=a+b 与 sp=a%20b 都解码成 'a b';plus=1%2B1 才是 '1+1';x=%E4%B8%AD%E6%96%87 解码成 '中文'。request.query_string 是原始字节,request.full_path 保留原始编码形式,request.url 里中文被还原成字符、%2B 与 %20 保持编码。", t=tl(S(2)), done=lidx(S(2), 'args='), kv=KV([['+ 与 %20', '都是空格'], ['%2B', '加号'], ['query_string', '原始字节']], ['%2B'])),
    step("编码的斜杠 %2F:在 <s>(string)段里,/seg/a%2Fb 与 /seg/a/b 都是 404;在 <path:p> 段里 /files/a%2Fb 与 /files/a/b 都得到 p = 'a/b'(%2F 被解码成 /)。", t=tl(S(3)), done=lidx(S(3), '/files/a%2Fb', '/files/a/b'), mark=lidx(S(3), '/seg/a%2Fb', '/seg/a/b'), kv=KV([['<s> 段里的 %2F', '404'], ['<path:p> 段里的 %2F', '解码成 /']], ['<s> 段里的 %2F'])),
    step("不合法的 UTF-8:/seg/%FF 与截断的 /seg/%E4%B8 都返回 200,s = '�'(无效字节被替换成替换字符,不报 400);/seg/%ZZ(不是合法的百分号编码)原样保留成 '%ZZ';/seg/a%00b 得到包含 \\x00 的字符串 'a\\x00b' —— 零字节也能进到视图,用它拼文件路径或 SQL 前要先校验。", t=tl(S(4)), done=lidx(S(4), '/seg/%FF', '/seg/%E4%B8'), mark=lidx(S(4), '/seg/%ZZ', '/seg/a%00b'), kv=KV([['无效 UTF-8', '替换字符 �,200'], ['%ZZ', '原样 %ZZ'], ['%00', '零字节进入视图']], ['%00'])),
    step("url_for 与 redirect 都生成百分号编码的 ASCII:url_for('user', name='张三') → /%E7%94%A8%E6%88%B7/%E5%BC%A0%E4%B8%89;url_for('q', name='中文 空格&号', x='a/b') → /q?name=%E4%B8%AD%E6%96%87+%E7%A9%BA%E6%A0%BC%26%E5%8F%B7&x=a/b(查询里空格是 +、& 被转成 %26、斜杠不转义);redirect('/目标/页 面?x=中文') 的 Location 是 /%E7%9B%AE%E6%A0%87/%E9%A1%B5%20%E9%9D%A2?x=%E4%B8%AD%E6%96%87。", t=tl(S(5)), done=lidx(S(5), 'url_for("user"', 'url_for("q"'), mark=lidx(S(5), 'Location'), kv=KV([['url_for', '百分号编码'], ['查询里的空格', '+'], ['redirect 的 Location', '也被编码']], ['redirect 的 Location'])),
    step(f"真实 HTTP(gunicorn,原始套接字):已编码的中文路径 → {rl_['已编码'][0]},正文「{rl_['已编码'][1]}」;直接发没有编码的原始 UTF-8 字节的请求行 → {rl_['原始 UTF-8 字节'][0]};发非法字节 → {rl_['原始 latin-1 非法字节'][0]}。浏览器和 curl 都会先编码,所以通常遇不到,但脚本直接发原始字节时在 gunicorn 下匹配不到包含中文的规则(本篇没有深究 gunicorn 内部是怎么处理这种请求行的)。", t=tl(S(6)), done=lidx(S(6), '已编码'), mark=lidx(S(6), '原始 UTF-8 字节', '原始 latin-1'), kv=KV([['已编码', '200 name=张三'], ['原始 UTF-8 字节', '404'], ['非法字节', '404']], ['原始 UTF-8 字节'])),
]
A = mkartf('f30', 30, 'Flask,Unicode,URL 编码,路径,真实验证,动画演示',
    '实测 URL 里的 Unicode 与编码:中文路径解码成 str(PATH_INFO 是 latin-1 形式);+、%20、%2B 在查询里的差别;%2F 在 string 与 path 段里的不同;非法 UTF-8 被替换成 �、零字节进入视图;url_for 与 redirect 的编码;gunicorn 对未编码的原始 UTF-8 请求行返回 404。',
    '浏览器发来的中文 URL,Flask 里到底拿到什么?%2F 是斜杠吗?非法编码会怎样?url_for 生成的链接长什么样?这篇用 test client 和真实的原始套接字都验证一遍。',
    [('�', '非法 UTF-8 被解码成的替换字符(不报 400)'), ('+ / %20 / %2B', '查询字符串里:空格 / 空格 / 加号'), ('404', '原始(未编码)UTF-8 请求行在 gunicorn 下的状态码')],
    [('路径里的中文', '<p>上一篇:<a href="flask-subdomain-routing.html">子域名路由</a>;下一篇:<a href="flask-werkzeug-request.html">Werkzeug Request 对象</a>。</p>'), ('查询字符串', None), ('编码的斜杠', None), ('非法编码', None), ('url_for 与 redirect', None), ('原始套接字', None)],
    steps, [ENV_F, '没有验证:浏览器对地址栏里中文的实际编码(用的是 UTF-8)、IDN 域名(Punycode)、uWSGI 与其它服务器对未编码请求行的处理、URL 长度上限、gunicorn 返回 404 的内部原因'], 'URL 编码')
