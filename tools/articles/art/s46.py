from lib import *
S = SS('s46')
steps = [
    step("FilesPipeline(ITEM_PIPELINES 里启用,FILES_STORE 指向目录):item 的 file_urls 放 6 个 URL——a.txt 出现两次、b.pdf、没有扩展名的 /dl?id=3、404 的 missing.txt、302 的 redir。服务器只收到一次 a.txt;item['files'] 有 4 条结果(a.txt 的两条一模一样,都是 downloaded),404 和 302 没有结果,日志 WARNING “File (code: 404/302): Error downloading file …”。落盘文件名是 URL 的 SHA1 加扩展名:full/0ba82ee8….txt(13 字节)、full/52ea1979….pdf(20,009 字节)、full/ffb2a4d9…(/dl?id=3 的路径里没有扩展名,文件也没有扩展名,20,009 字节)。checksum 是文件内容的 md5(a.txt 的对得上)。stats:file_count = 3、file_status_count/downloaded = 3。", t=tl(S(1)), mark=lidx(S(1), '磁盘上', 'checksum'), done=lidx(S(1), 'status=downloaded'), kv=KV([['落盘路径', 'full/<SHA1(URL)><扩展名>'], ['checksum', '文件内容的 md5'], ['重复 URL', '只请求一次,结果列出两条'], ['404 / 302', '没有结果,WARNING 日志']], ['落盘路径'])),
    step("第二次运行(同一个 FILES_STORE):下载过且没过期的文件状态变成 uptodate,服务器不再收到 a.txt、b.pdf、/dl 的请求(只剩失败过的 missing.txt、redir 又请求一遍,失败不缓存),stats file_status_count/uptodate = 3;把 FILES_EXPIRES 设成 0(天)后,所有已有文件都算过期,服务器重新收到全部请求,状态回到 downloaded。默认过期天数是 90 天。", t=tl(S(2)), mark=lidx(S(2), 'FILES_EXPIRES=0'), done=lidx(S(2), '第二次'), kv=KV([['第二次', 'uptodate × 3,不请求服务器'], ['失败的 URL', '每次都重试'], ['FILES_EXPIRES = 0', '全部重新下载']], ['第二次'])),
    step("重定向:文件 URL 返回 302 时,默认(MEDIA_ALLOW_REDIRECTS = False)不跟——files 为空,日志 WARNING “File (code: 302)”,服务器只收到 /f/redir;设成 True 才跟随到 /f/a.txt,文件下载成功,但保存的路径用的是最初那个 URL 的 SHA1(full/df36b499…,没有扩展名),不是跳转后的。", t=tl(S(3)), mark=lidx(S(3), '默认(False)'), done=lidx(S(3), 'MEDIA_ALLOW_REDIRECTS=True'), kv=KV([['默认', '302 不跟随,下载失败'], ['MEDIA_ALLOW_REDIRECTS = True', '跟随;路径仍按原 URL 的 SHA1']], ['默认'])),
    step("自定义文件名:子类重写 file_path(request, response=None, info=None, *, item=None),用 URL 里的原文件名——磁盘上是 by-name/a.txt、by-name/b.pdf、by-name/dl-id3(不再是 SHA1)。注意这样的名字在不同 URL 同名时会互相覆盖。", t=tl(S(4)), mark=lidx(S(4), 'by-name'), kv=KV([['file_path()', '决定落盘的相对路径'], ['同名冲突', '自己负责避免']], ['file_path()'])),
]
A = mkarts('s46', 46, 'Scrapy,FilesPipeline,文件下载,FILES_STORE,uptodate,真实验证,动画演示',
    '实测 FilesPipeline:file_urls 下载到 full/<SHA1(URL)><扩展名>,checksum 是内容 md5,重复 URL 只请求一次;失败的 404/302 没有结果也不缓存;第二次运行 3 个文件变 uptodate 不再请求,FILES_EXPIRES=0 全部重下;MEDIA_ALLOW_REDIRECTS 默认不跟 302;重写 file_path 自定义文件名。',
    'item 里放一串 file_urls,FilesPipeline 就替你下载文件。它存在哪、文件名怎么来、重复下载怎么避免、失败了怎么办?这篇用一个带 404、重定向、无扩展名下载链接的服务器全跑一遍。',
    [('SHA1(URL)', '落盘文件名的来源(加上 URL 路径里的扩展名)'), ('uptodate × 3', '第二次运行已下载文件的状态(服务器 0 次请求)'), ('False', 'MEDIA_ALLOW_REDIRECTS 的默认值')],
    [('落盘与结果', '<p>文件保存在 <code>FILES_STORE/full/</code>,文件名是 URL 的 SHA1 加扩展名;结果写进 item 的 <code>files</code> 字段,每条有 url、path、checksum、status。</p>'),
     ('避免重复下载', '<p>已存在且没过 <code>FILES_EXPIRES</code> 天的文件状态为 <code>uptodate</code>,不再请求服务器;失败的 URL 不会被记住。</p>'),
     ('重定向', '<p>媒体请求默认不跟随 3xx,需要 <code>MEDIA_ALLOW_REDIRECTS = True</code>;保存路径仍按最初的 URL 计算。</p>'),
     ('自定义文件名', '<p>重写 <code>file_path()</code> 即可用可读的名字,但要自己避免冲突。</p>')],
    steps,
    [ENV_Y + '。服务器提供 a.txt(13 字节)、b.pdf(20,009 字节随机内容)、/dl?id=3(同内容但无扩展名)、404、302;item 里直接放 file_urls 的 dict;首次运行和第二次运行共用同一个 FILES_STORE',
     '没有验证:ImagesPipeline(缩略图、尺寸过滤);S3、GCS、FTP 存储;大文件下载时的内存(FilesPipeline 在 2.19 里是否流式写入没有测);并发下载文件数(MEDIA 管道与下载器并发的关系);Content-Disposition 里的文件名(默认不使用);超过 DOWNLOAD_MAXSIZE 的文件'],
    '文件下载')
