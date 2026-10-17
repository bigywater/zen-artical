from lib import *
S = SS('f126')
R = J('f126'); sz = R['size']
steps = [
    step("只看扩展名和客户端声明的 Content-Type 的实现(naive)很容易被糊弄:真正的 PNG、x.png、image/png → 通过(accepted: true);一段纯文本只要文件名写成 x.png、声明 image/png 也通过;改成大写 X.PNG 同样通过;反过来,真正的 PNG 但文件名是 x.txt → 400。Content-Type 与文件名都是客户端随便填的,不能当作文件内容的证据。", t=tl(S(1)), mark=lidx(S(1), '纯文本,x.png', '纯文本,X.PNG'), done=lidx(S(1), '真正的 PNG,x.png', 'x.txt'), kv=KV([['扩展名 + 声明的类型', '客户端想写什么就写什么'], ['结论', '不能证明内容']], ['结论'])),
    step("校验内容的实现:先把文件名过 secure_filename 取扩展名并查白名单,再读前 16 个字节检查文件头签名(PNG、JPEG、GIF),要求扩展名与内容一致,最后用 Pillow 的 Image.open().verify() 解析,通过后用随机 uuid 当文件名保存。结果:真 PNG 与 .jpeg 的真 JPEG → 200(扩展名 jpeg 存成 .jpg);纯文本冒充 PNG → 400「文件内容不是允许的图片类型」;PNG 内容写成 x.jpg → 400「扩展名与内容不一致」;PNG 签名加垃圾 → 400「图片无法解析」;x.svg 与没有扩展名 → 400「扩展名不允许」;'../my pic.png' → 200,原名被清洗成 my_pic.png,磁盘上的文件名是随机 uuid,不含用户给的名字。", t=tl(S(2)), done=lidx(S(2), '真正的 PNG', '真正的 JPEG', '文件名含路径', '磁盘上保存'), mark=lidx(S(2), '纯文本冒充', 'PNG 内容,扩展名写成 jpg', '垃圾', 'svg', '没有扩展名'), kv=KV([['白名单扩展名', '先过一遍'], ['文件头签名 + Pillow', '再验证内容'], ['保存名', '随机 uuid']], ['保存名'])),
    step("这个实现还有一个我自己踩到的缺陷:中文文件名 照片.png 被拒绝(400「扩展名不允许」,ext 为空)——因为我对 secure_filename 的结果取扩展名,而 secure_filename 会把 照片.png 变成 png(第 125 篇看过),取不到扩展名。扩展名应该从原始文件名里取,清洗后的名字只用来显示或记录。", t=tl(S(2)), mark=lidx(S(2), '中文文件名'), kv=KV([['对 secure_filename 的结果取扩展名', '中文文件名会丢掉扩展名'], ['修正', '从原始文件名取扩展名']], ['对 secure_filename 的结果取扩展名'])),
    step(f"大小限制:MAX_CONTENT_LENGTH = 200 KB 时,上传约 100 KB 与 199 KB 通过({sz['100']}、{sz['199']}),约 201 KB 与 1000 KB 返回 {sz['201']}、{sz['1000']}(请求体过大,在读取文件之前就被拒绝)。", t=tl(S(3)), done=lidx(S(3), '100 KB', '199 KB'), mark=lidx(S(3), '201 KB', '1000 KB'), kv=KV([['MAX_CONTENT_LENGTH', '超过 → 413']], ['MAX_CONTENT_LENGTH'])),
    step("文件头签名只能证明「开头像」:一张被截断的 PNG(签名与头部完整、数据缺失)通过了签名检查,但 Pillow 解析时抛 UnidentifiedImageError,被拒绝(400「图片无法解析」)。所以签名检查之后还要真的解析一遍;对要重新分发的图片,更稳妥的是用 Pillow 重新编码保存(本篇没有验证)。", t=tl(S(4)), mark=lidx(S(4), '被截断的 PNG'), kv=KV([['签名检查', '只看开头'], ['Pillow 解析', '能发现被截断的文件']], ['Pillow 解析'])),
]
A = mkartf('f126', 126, 'Flask,文件上传,类型校验,Pillow,真实验证,动画演示',
    '实测 Flask 文件上传的类型校验:只看扩展名与客户端声明的 Content-Type 会被纯文本冒充、校验文件头签名加扩展名一致加 Pillow 解析能挡住冒充与垃圾、保存时用随机 uuid 名字、对 secure_filename 的结果取扩展名会误拒中文文件名、MAX_CONTENT_LENGTH 返回 413、被截断的 PNG 要靠解析才能发现。',
    '上传的文件怎么确认它真是图片?扩展名和 Content-Type 能信吗?校验到什么程度才算够?这篇只验证防御端:拿一份朴素实现和一份校验内容的实现,用各种「像又不像」的文件逐个对照,还记录了我自己代码里一个会误拒中文文件名的缺陷。',
    [('400', '纯文本冒充 PNG 在内容校验下的结果(朴素实现返回 200)'), ('uuid', '保存到磁盘的文件名,不使用用户提供的名字'), ('413', '请求体超过 MAX_CONTENT_LENGTH 时的状态码')],
    [('只看扩展名与声明的类型', '<p>上一篇:<a href="flask-path-traversal-download.html">路径穿越与文件下载</a>;下一篇:<a href="flask-host-header-validation.html">Host Header 校验</a>。</p>'), ('校验内容(含一个中文文件名的缺陷)', None), ('大小限制', None), ('签名与解析', '<p>本篇是防御向的验证:没有构造任何恶意文件,「冒充」用的是一段普通文本。</p>')],
    steps, [ENV_F + '。Pillow 12.3.0', '没有验证:SVG、PDF、Office 文档等格式的校验、压缩包与图片炸弹(超大像素)的防护、病毒扫描、把上传目录放在 Web 根之外与对象存储的做法、图片重新编码后的元数据清除、流式分块上传的大小限制'], '文件上传类型校验')
