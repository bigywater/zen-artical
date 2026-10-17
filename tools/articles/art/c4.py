from lib import *
S = SS('c4')
steps = [
    step("COPY 与 ADD 对本地压缩包的处理:同一个目录里有 pack.tar、pack.tar.gz、pack.zip。COPY 到 /copy/:三个文件原样躺在那里(/copy/pack.tar、/copy/pack.tar.gz、/copy/pack.zip)。ADD 到 /add/:pack.tar 和 pack.tar.gz 被自动解压,得到 /add/hello/a.txt 与 /add/hello/b.txt;pack.zip 没有被解压,仍是 /add/pack.zip。", t=tl(S(1)), done=lidx(S(1), '/copy/pack.tar', '/copy/pack.zip'), mark=lidx(S(1), '/add/hello/a.txt', '/add/hello/b.txt', '/add/pack.zip'), kv=KV([['COPY', '原样复制,从不解压'], ['ADD tar / tar.gz', '自动解压'], ['ADD zip', '不解压,原样复制']], ['ADD tar / tar.gz'])),
    step("ADD 目录与 COPY 目录的结果相同,文件的权限和属主:COPY dir 与 ADD dir 之后,/c/dir/x.txt 与 /a/dir/x.txt 都是 -rw-r----- 属主 0:0,diff -r 显示内容完全相同;COPY run.sh 保留 -rwxr-xr-x;COPY --chmod=0600 --chown=1000:1000 run.sh 得到 -rw------- 属主 1000:1000。", t=tl(S(2)), done=lidx(S(2), '/a/dir/x.txt', '内容完全相同'), mark=lidx(S(2), 'run600.sh', '/c/run.sh'), kv=KV([['COPY / ADD 目录', '内容与权限一致'], ['源文件权限', '默认保留'], ['--chmod / --chown', '可以显式指定']], ['--chmod / --chown'])),
    step("ADD 远程 URL(守护进程去下载,实验里指向宿主机上起的本地 HTTP 服务):构建成功;下载下来的 data.txt(1200 字节)和 remote.tar.gz(132 字节)权限都是 -rw-------,属主 root;remote.tar.gz 前 4 个字节是 1f 8b 08 08(gzip),说明 URL 下载的压缩包没有被解压。ADD --checksum=sha256:<正确摘要> 构建成功;摘要写成 64 个 0:退出码 1,错误是 digest mismatch sha256:457f2431…: sha256:0000…。", t=tl(S(3)), done=lidx(S(3), '-rw------- 1 0 0 1200', '--checksum 正确'), mark=lidx(S(3), '1f 8b 08 08', '--checksum 错误'), kv=KV([['URL 下载的文件', '权限 0600,属主 root'], ['URL 下载的压缩包', '不解压(1f 8b 是 gzip 魔数)'], ['--checksum', '摘要不对就失败,digest mismatch']], ['--checksum'])),
]
A = mkartc('c4', 4, 'Docker,COPY,ADD,Dockerfile,自动解压,真实验证,动画演示',
    '在 Docker Engine 29.8.2(BuildKit)里实测 COPY 与 ADD:ADD 会自动解压本地的 tar 和 tar.gz,但不解压 zip,COPY 从不解压;ADD 目录与 COPY 目录结果相同;ADD 远程 URL 下载的文件权限是 0600 属主 root,压缩包不会被解压;ADD --checksum 摘要不对时构建失败。',
    'Dockerfile 最佳实践常说“能用 COPY 就不要用 ADD”。ADD 到底多做了什么?这篇用同一组本地压缩包和一个本地 HTTP 服务逐项验证:自动解压的范围、权限与属主、远程 URL 的行为,以及 --checksum 能不能挡住被篡改的下载。',
    [('tar、tar.gz 解压,zip 不解压', 'ADD 对本地压缩包的处理'), ('0600 root', 'ADD 远程 URL 下载的文件的权限与属主'), ('digest mismatch', 'ADD --checksum 摘要不匹配时的构建错误')],
    [('ADD 的“多余”功能一:解压', '<p>本地的 <code>pack.tar</code> 与 <code>pack.tar.gz</code> 被 <code>ADD</code> 自动解压到目标目录(得到 <code>/add/hello/a.txt</code> 等),<code>pack.zip</code> 不会;<code>COPY</code> 三者都原样复制。所以“把压缩包放进镜像”用 <code>COPY</code>,“展开一个 tar”才用 <code>ADD</code>——而且最好明确写出来,避免有人把 tar 当成普通文件复制却被悄悄解压。</p>'),
     ('目录与权限', '<p><code>ADD dir</code> 与 <code>COPY dir</code> 得到完全相同的内容(<code>diff -r</code> 验证)。权限默认保留源文件的,<code>COPY --chmod</code>、<code>--chown</code> 可以显式指定,实验里得到 <code>-rw-------</code> 与 1000:1000。</p>'),
     ('ADD 的多余功能二:远程 URL', '<p>URL 由守护进程(构建器)去下载,不是客户端。下载的文件权限是 <code>0600</code>、属主 root,压缩包不会被解压(开头是 gzip 的 <code>1f 8b</code>)。加 <code>--checksum=sha256:…</code> 可以校验内容,写错摘要构建以 <code>digest mismatch</code> 失败。本文的 URL 指向宿主机上的本地服务,没有测真实的外网下载。</p>')],
    steps,
    [ENV_C + '。压缩包由 Python tarfile / zipfile 生成;URL 指向宿主机上用 Python 起的 HTTP 服务(通过 host.docker.internal 访问);结果通过在构建出的镜像里 find / ls / od 观察;每种情形一次;实验后已删除所有镜像和临时文件',
     '没有验证:git URL 作为 ADD 源、真实互联网上的 ADD、ADD 解压 tar.xz / tar.bz2 / tar.zst、符号链接与硬链接在 tar 里的处理、ADD 缓存键对远程内容变化的反应'],
    'COPY 与 ADD')
