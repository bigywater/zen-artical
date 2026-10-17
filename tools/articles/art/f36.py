from lib import *
S = SS('f36')
R = J('f36'); pt = R['parts']
steps = [
    step("同一个字段名上传多个文件:request.files.getlist('docs') 返回全部 3 个(a.txt、b.txt、c.txt,大小 3、5、1 字节);request.files['docs'] 只取第一个(a.txt);files.keys() 里只有一个键 docs;普通字段 note 仍然在 form 里。", t=tl(S(1)), done=lidx(S(1), "'count': 3"), kv=KV([['getlist(\"docs\")', '3 个文件'], ['files[\"docs\"]', '只有第一个 a.txt'], ['普通字段', '在 form 里']], ['files[\"docs\"]'])),
    step("不同字段名的文件用 request.files.lists() 按字段名分组:{'avatar': ['me.png'], 'docs': ['d1.pdf', 'd2.pdf']}。", t=tl(S(2)), done=lidx(S(2), "'avatar'"), kv=KV([['avatar', 'me.png'], ['docs', 'd1.pdf、d2.pdf']], ['docs'])),
    step("同名文件会互相覆盖:两个用户都上传 report.pdf 并用 secure_filename 后的名字保存,目录里只剩一个 report.pdf,内容是后上传的 USER-2 data。给文件名加 8 位随机前缀后,两次上传得到 2 个文件(前缀不同)。", t=tl(S(3)), done=lidx(S(3), '两次上传同名文件后目录里'), mark=lidx(S(3), '加随机前缀后目录里'), kv=KV([['只用原文件名', '后者覆盖前者(1 个文件)'], ['加随机前缀', '2 个文件']], ['只用原文件名'])),
    step(f"MAX_FORM_PARTS 对文件也计数(文件与普通字段合计):设成 6 时,3 个文件 + 1 个字段 → {pt['3']},5 个文件 + 1 个字段(共 6 部分)→ {pt['5']},8 个文件 + 1 个字段 → {pt['8']}。超出上限的是 413。", t=tl(S(4)), done=lidx(S(4), '3 个文件', '5 个文件'), mark=lidx(S(4), '8 个文件'), kv=KV([['3 个文件 + 1 字段', str(pt['3'])], ['5 个文件 + 1 字段', str(pt['5'])], ['8 个文件 + 1 字段', str(pt['8'])]], ['8 个文件 + 1 字段'])),
    step("真实 HTTP:curl 重复 -F docs=@1.txt -F docs=@2.txt -F docs=@3.txt 一次上传 3 个文件,服务端 getlist 读到 1.txt:3,2.txt:6,3.txt:1(文件名与字节数)。", t=tl(S(5)), done=lidx(S(5), '→ 1.txt'), kv=KV([['curl 重复 -F docs=@…', '服务端 getlist 得到 3 个']], ['curl 重复 -F docs=@…'])),
]
A = mkartf('f36', 36, 'Flask,多文件上传,getlist,真实验证,动画演示',
    '实测多文件上传:同名字段用 getlist 取全部(files[...] 只取第一个);不同字段名用 files.lists();同名文件会互相覆盖需要随机前缀;MAX_FORM_PARTS 把文件与普通字段合计,设为 6 时 6 部分通过、9 部分 413;curl 重复 -F 真实上传 3 个文件。',
    '<input multiple> 上传一批文件时,Flask 里怎么取?同名的文件会不会互相覆盖?上传多少个会被拒?这篇从 getlist 开始一一验证。',
    [('3', '本篇 getlist 一次取到的文件数'), ('1 个', '两个用户上传同名文件、不加前缀时目录里剩下的文件数'), ('413', 'multipart 部分数超过 MAX_FORM_PARTS 时的状态码')],
    [('getlist', '<p>上一篇:<a href="flask-file-upload-filestorage.html">文件上传与 FileStorage</a>;下一篇:<a href="flask-upload-size-limit.html">上传文件大小限制</a>。</p>'), ('files.lists()', None), ('同名文件覆盖', None), ('数量上限', None), ('真实 HTTP', None)],
    steps, [ENV_F, '没有验证:并发保存同一文件名时的竞态(只演示了顺序覆盖)、浏览器 <input multiple> 实际发出的字段名、目录下文件数量巨大时的性能、随机前缀的碰撞概率(只用了 8 位十六进制)'], '多文件上传')
