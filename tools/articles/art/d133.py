from lib import *
R = J('d133')
def S(k): return [l for l in out('d133').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("DEBUG=True 时 static(MEDIA_URL, document_root=MEDIA_ROOT) 返回 1 条路由,GET /media/a.txt → 200;DEBUG=False 时返回 0 条路由,GET /media/a.txt → 404。上线后 Django 不提供 /media/,要由 nginx / 对象存储 / CDN 提供。", t=tl(S(1)), mark=[2, 3], done=[0, 1], kv=KV([['DEBUG=True', 'static() 才有路由'], ['DEBUG=False', '返回空列表,404']], ['DEBUG=False'])),
    step("上传文件名的处理(FileField 保存时):'a b.txt' → docs/a_b.txt(空格换成下划线);'../../evil.txt' → docs/evil.txt、'/etc/passwd' → docs/passwd(路径部分被去掉,仍在 MEDIA_ROOT 内);同名第二次上传 → rep_ 加 7 位随机字符 .txt(如 rep_UvQcZtV.txt);中文名保留;304 字符的长名被截成 100 个字符(FileField 默认 max_length=100);page.html 的扩展名原样保留。8 个文件全部在 MEDIA_ROOT 内。", t=tl(S(2)), done=[0, 1, 2, 3, 4, 5, 6, 7], kv=KV([['路径穿越写法', '被去掉路径'], ['重名', '加随机后缀']], ['路径穿越写法'])),
    step("FILE_UPLOAD_MAX_MEMORY_SIZE 默认 2621440 字节(2.5 MiB):上传 1 MiB 时请求里的文件对象是 InMemoryUploadedFile,上传 3 MiB 时是 TemporaryUploadedFile(落到磁盘临时文件)。", t=tl(S(3)), done=[1, 2], kv=KV([['≤ 2.5 MiB', '内存'], ['> 2.5 MiB', '临时文件']], ['> 2.5 MiB'])),
    step("DATA_UPLOAD_MAX_MEMORY_SIZE 设成 1000 字节:上传 500000 字节的文件 → 200(不限制文件);提交 2000 字节的普通字段 → 400。DATA_UPLOAD_MAX_NUMBER_FILES 默认 100:一次传 100 个文件 → 200,101 个 → 400。", t=tl(S(4)), done=[1, 4], mark=[2, 5], kv=KV([['DATA_UPLOAD_MAX_MEMORY_SIZE', '只限制非文件字段'], ['文件个数', '默认最多 100']], ['文件个数'])),
    step("把上传的文件原样返回:FileResponse 按扩展名猜 Content-Type:page.html → text/html(Content-Disposition: inline),加 as_attachment=True 后变成 attachment;a.txt → text/plain。用户上传的 HTML 如果以 inline 方式放在站点自己的域名下,浏览器会把它当页面渲染。", t=tl(S(5)), mark=[0], done=[1], kv=KV([['上传的 .html', 'inline 时按页面渲染'], ['as_attachment', '强制下载']], ['as_attachment'])),
]
A = dict(
    n=133, series='django', tags='Django,媒体文件,文件上传,FileField,部署,真实验证,动画演示',
    desc='媒体文件上线:DEBUG=False 时 static() 返回空路由、/media/ 是 404;FileField 把 ../../evil.txt 保存成 docs/evil.txt、重名加随机后缀;2.5 MiB 以上用临时文件;DATA_UPLOAD_MAX_MEMORY_SIZE 不限文件,文件个数默认最多 100;上传的 .html 会以 text/html 返回。',
    lead='用户上传的文件有一套自己的规矩:谁来提供、文件名会被怎样处理、大文件放在哪、有哪些上限。这篇在自己的测试应用上逐项验证,所有「恶意文件名」都只是对 FileField 自己的防护做测试。',
    facts=[('/media/ 404', 'DEBUG=False 时 Django 不提供,static() 返回 0 条路由'), ('docs/evil.txt', "上传 '../../evil.txt' 保存后的文件名,仍在 MEDIA_ROOT 内"), ('100', 'DATA_UPLOAD_MAX_NUMBER_FILES 默认值;101 个文件 → 400')],
    body=[
        sec('谁来提供 /media/', '', term('', blk('d133', 1))),
        sec('文件名的处理', '', term('', blk('d133', 2)), '<p>这是 <code>FileField.save()</code> / 存储后端的处理。如果你自己拼路径(比如把用户给的文件名直接传给 <code>open()</code>),这些保护就不存在了。</p>'),
        sec('内存与临时文件', '', term('', blk('d133', 3))),
        sec('上传上限', '', term('', blk('d133', 4)), '<p>文件本身的总大小没有被这两个设置限制,要限制上传大小,需要在代理(nginx 的 <code>client_max_body_size</code>)或视图 / 表单里做;本文没有测代理。</p>'),
        sec('原样返回上传的文件', '', term('', blk('d133', 5)), '<p>用户上传的内容不应当用站点自己的域名、以 inline 方式提供;更稳妥的做法是用单独的域名或者强制下载。这是通用的安全建议,本文只验证了响应头的差别,没有在浏览器里执行。</p>'),
        sec('分步演示', '', demo('媒体文件上线', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;用 Client 上传 SimpleUploadedFile;所有文件写在项目自己的 media 目录', '没有验证:nginx 提供 /media/、S3 / 对象存储后端(django-storages)、图片处理(ImageField 的 Pillow 校验)、文件内容类型校验、病毒扫描、并发上传同名文件的竞态'],
)
