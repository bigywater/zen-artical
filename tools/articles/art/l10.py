from lib import *
S = SS('l10')
steps = [
    step("四种符号链接(相对 rel、绝对 abs、指向目录 dirlink、悬空 dangling)再加一个 dir/up 指向 ../outside,git add 之后暂存区里全是 120000。blob 的内容就是 readlink 得到的字符串:rel 是 target.txt,abs 是完整的绝对路径,dirlink 是 dir,悬空的 dangling 是 nothing.txt(目标不存在也照样记录),dir/up 是 ../outside(指向仓库外面也照样记录)。git 完全不检查目标。", t=tl(S(1)), mark=lidx(S(1), 'dangling  readlink', 'dir/up    readlink', 'abs       readlink'), done=lidx(S(1), 'rel       readlink', 'dirlink   readlink', '120000'), kv=KV([['blob 内容', 'readlink 的原样字符串'], ['悬空 / 指向仓库外', '照样存,git 不检查'], ['绝对路径', '原样存进 blob']], ['blob 内容'])),
    step("提交后 clone 到另一个目录:相对链接 rel -> target.txt 仍然有效(读到 real),指向目录的 dirlink -> dir 能读到 inner,悬空的 dangling -> nothing.txt 读不到;而绝对链接 abs 仍指向原仓库里的路径 /work/l10/target.txt,读到的是原仓库的文件,不是副本里自己的 target.txt——换一台机器就是悬空的。", t=tl(S(2)), mark=lidx(S(2), 'abs       -> /work/l10/target.txt', 'dangling  ->'), done=lidx(S(2), 'rel       ->', 'dirlink   ->'), kv=KV([['相对链接', '换位置仍然有效'], ['绝对链接', '指向原路径,别的机器上悬空'], ['悬空链接', '检出后依旧悬空']], ['绝对链接'])),
    step("指向目录的链接:git add ln 把 ln 当作链接记录(120000);而 git add ln/(带斜杠)被拒绝:fatal: pathspec 'ln/' is beyond a symbolic link——带斜杠就把 ln 当成真正的目录,而路径穿过了符号链接,git 不允许。", t=tl(S(3)), mark=lidx(S(3), 'beyond a symbolic link'), done=lidx(S(3), 'git add ln; git ls-files -s', '120000 ac558a3'), kv=KV([['git add ln', '记录链接本身'], ['git add ln/', 'fatal: beyond a symbolic link'], ['git 的立场', '不穿过符号链接追踪内容']], ['git add ln/'])),
    step("链接目标变了:ln -sfn dir rel 把 rel 改指 dir,git status 是 M rel,git diff 显示 blob 内容从 target.txt 变成 dir(index 行的模式仍是 120000),两行都带 \\ No newline at end of file——链接 blob 内容没有换行。而改被指向的 target.txt 的内容,status 只显示 M target.txt,不会牵连链接。", t=tl(S(4)), mark=lidx(S(4), '-target.txt', '+dir', 'M target.txt'), done=lidx(S(4), 'M rel', 'index 4cbb553..8724519 120000'), kv=KV([['改链接目标', '链接 blob 内容变了'], ['改被指向的文件', '只有那个文件变,链接不受影响'], ['diff', '120000,无结尾换行']], ['改链接目标'])),
    step("core.symlinks=false 的 clone:rel 被写成普通文件(-rw-r--r--),内容是 target.txt 这个路径字符串,暂存区仍是 120000,git status 对 5 个链接全显示 T(类型改变:abs、dangling、dir/up、dirlink、rel)。在这种环境里编辑这个“文件”再提交,暂存区里的模式变成 100644(blob 8724519 的内容是 dir)——链接被悄悄变成了普通文件。", t=tl(S(5)), mark=lidx(S(5), ' T rel', ' T abs', '100644 87245193'), done=lidx(S(5), '-rw-r--r--', 'target.txt; git status', '120000 4cbb553'), kv=KV([['core.symlinks=false', '链接检出成含路径的普通文件'], ['status', '全部显示 T(类型改变)'], ['在这里提交', '可能把链接变成普通文件']], ['在这里提交'])),
]
A = mkarti('l10', 10, 'Git,符号链接,120000,core.symlinks,真实验证,动画演示',
    '在真实仓库里验证符号链接的存法:blob 内容就是 readlink 字符串,相对、绝对、悬空、指向仓库外都照存;clone 后相对链接有效、绝对链接指回原路径;git add 指向目录的链接带斜杠会被拒绝;core.symlinks=false 时链接检出成普通文件,status 全显示 T,在那里提交会把链接变成普通文件。',
    '符号链接在 git 里到底存了什么?这篇创建相对、绝对、悬空、指向目录的四种链接,看暂存区和 blob 里的内容,clone 后哪些还有效,git add 带斜杠的行为,以及 core.symlinks=false 的环境里会发生什么。',
    [('120000', '所有符号链接在暂存区里的模式,不管目标存不存在'), ('绝对路径', 'abs 链接的 blob 里存的是完整的绝对路径,clone 后仍指向原仓库'), ('T', 'core.symlinks=false 的检出里,git status 对每个链接都显示 T(类型改变)')],
    [('存了什么', '<p>符号链接作为一个 <code>120000</code> 条目,blob 内容就是 <code>readlink</code> 的原样字符串。git 不检查目标:相对、绝对、不存在、指向仓库外面的,都照样记录。</p>'),
     ('可移植性', '<p>相对链接换个位置检出仍然有效;绝对链接把作者机器上的路径带到了别处,通常是悬空的。悬空链接检出后依旧悬空。</p>'),
     ('指向目录的链接', '<p><code>git add ln</code> 记录链接本身;<code>git add ln/</code> 带了斜杠,被当成穿过符号链接的路径,git 拒绝。</p>'),
     ('链接目标变化', '<p>改链接目标让链接的 blob 内容变化,<code>git diff</code> 显示两个路径字符串(模式仍是 120000);被指向文件的内容变化是另一个文件的改动,和链接无关。</p>'),
     ('core.symlinks=false', '<p>在不能创建符号链接的环境里,git 把链接检出成含路径字符串的普通文件,暂存区仍是 120000,所以 status 显示类型改变。在那里提交修改过的文件,会把链接永久变成普通文件,需要小心。</p>')],
    steps,
    [ENV_I_GIT + '。符号链接在 macOS 文件系统上创建;core.symlinks=false 是用命令行 -c 强制指定的,模拟不支持链接的环境,并不是真的在 Windows 上',
     '没有验证:Windows 上 core.symlinks 的自动探测与权限要求;git 对链接目标逃出仓库的安全检查(检出时的 path traversal 防护);链接指向 .git 目录等特殊路径时的限制;子模块路径上的链接'],
    '符号链接')
