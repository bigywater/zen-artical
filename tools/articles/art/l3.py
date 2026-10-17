from lib import *
S = SS('l3')
steps = [
    step("一个提交里同时放进四种条目:普通文件 plain.txt、可执行的 run.sh、符号链接 link(指向 plain.txt)、子模块 vendor/lib。git ls-tree HEAD 的模式列分别是 100644、100755、120000,vendor 是一个目录(040000 tree);用 -r 展开之后 vendor/lib 变成 160000 commit。四种模式对应四种条目:文件、可执行文件、符号链接、子模块。", t=tl(S(1)), mark=lidx(S(1), '120000 blob', '100755 blob', '160000 commit'), done=lidx(S(1), 'plain.txt', 'git ls-tree HEAD'), kv=KV([['100644', '普通文件'], ['100755', '可执行文件'], ['120000', '符号链接'], ['160000', '子模块(commit 条目)']], ['120000'])),
    step("直接读 tree 对象的原始字节,模式是 ASCII 数字:100644、120000、100644、100755、40000。目录写成 40000 而不是 040000。vendor 的子 tree 里只有一个条目:160000 commit f0b877b…,叫 lib。tree 里没有存任何别的权限位,也没有时间戳、所有者。", t=tl(S(2)), mark=lidx(S(2), "'40000'", "'120000'"), done=lidx(S(2), "'100644'", "'100755'", 'vendor/ 这个子 tree'), kv=KV([['模式', 'ASCII 数字,tree 里照存'], ['目录', '存成 40000(少一个 0)'], ['没有的东西', '时间戳、所有者、其它权限位']], ['目录'])),
    step("符号链接 link 的 blob 只有 9 字节,内容正好是链接目标 plain.txt(9 个字符),原始字节是 blob 9 NUL plain.txt。git 不存“这是个链接”这件事在 blob 里,这件事由 tree 条目的模式 120000 表达;换句话说 blob 本身看起来就是一个文本文件。", t=tl(S(3)), mark=lidx(S(3), "b'blob 9", 'plain.txt'), done=lidx(S(3), 'git cat-file -s'), kv=KV([['blob 内容', '链接目标的路径字符串'], ['区别于普通文件', '只靠 tree 条目的 120000'], ['长度', '9 字节 = len("plain.txt")']], ['区别于普通文件'])),
    step("子模块条目 vendor/lib 的 hash f0b877b… 是子仓库的 commit。在主仓库里 git cat-file -t 这个 hash 报 fatal: could not get object info(对象根本不在本仓库的对象库里);指到子仓库的 .git 就能看到它是 commit。.gitmodules 只保存路径和 URL,git ls-tree -r 里没有 lib.txt(grep 计数 0)——子模块的内容完全不进主仓库。", t=tl(S(4)), mark=lidx(S(4), 'fatal: git cat-file', '[submodule "vendor/lib"]'), done=lidx(S(4), 'commit', '  0'), kv=KV([['gitlink', 'tree 里记录子仓库的 commit hash'], ['对象位置', '不在主仓库,在子仓库里'], ['.gitmodules', '只有路径与 URL']], ['gitlink'])),
    step("想写“别的模式”时 git 会规整:--cacheinfo 100664 与 100600 都变成 100644,100777 变成 100755,120755 变成 120000。也就是说文件的权限位只保留“用户是否可执行”这一个信息,符号链接的权限位没有意义。", t=tl(S(5)), mark=lidx(S(5), '100777', '120755'), done=lidx(S(5), '100664', '100600'), b=bars([['100664 → 100644', 1, '规整'], ['100600 → 100644', 1, '规整'], ['100777 → 100755', 1, '规整'], ['120755 → 120000', 1, '规整']], 1, mark=[2, 3], done=[0, 1]), kv=KV([['只保留', '是否可执行(644 / 755)'], ['符号链接', '权限位被忽略,一律 120000'], ['旧仓库', '可能有历史遗留的 100664(fsck 会提示)']], ['只保留'])),
]
A = mkarti('l3', 3, 'Git,tree,文件模式,符号链接,子模块,gitlink,真实验证,动画演示',
    '在真实仓库里放进普通文件、可执行文件、符号链接和子模块,对照 git ls-tree 与 tree 对象的原始字节:四种模式 100644、100755、120000、160000;符号链接的 blob 内容就是目标路径;子模块条目是子仓库的 commit hash,在主仓库里根本找不到这个对象;写其它模式时 git 会规整成这四种之一。',
    'tree 对象里每个条目前面的 100644、100755、120000、160000 到底是什么?这篇把四种条目放进同一个提交,读原始字节,看符号链接的 blob 里存了什么、子模块的条目指向哪个根本不在本仓库里的对象,还试了试写别的模式会怎样。',
    [('4 种', 'tree 条目的模式:100644 文件、100755 可执行、120000 符号链接、160000 子模块'), ('9 字节', '符号链接的 blob 内容就是链接目标 plain.txt,没有别的标记'), ('找不到', '子模块条目的 commit 在主仓库里 git cat-file 报错,对象在子仓库')],
    [('四种模式', '<p>一个条目的模式决定它被检出成什么:<code>100644</code> 普通文件、<code>100755</code> 可执行文件、<code>120000</code> 符号链接、<code>160000</code> 子模块(gitlink),再加上目录本身的 <code>40000</code>。tree 里就这些,不保存时间戳、所有者和其它权限位。</p>'),
     ('tree 里的写法', '<p>模式在 tree 对象里是 ASCII 数字,目录写 <code>40000</code>(没有前导零),<code>git ls-tree</code> 显示时才补成 <code>040000</code>。</p>'),
     ('符号链接', '<p>符号链接的 blob 内容就是链接目标的路径字符串,没有别的标记;“这是个链接”这件事由 tree 条目的 <code>120000</code> 表达。所以在不支持符号链接的系统上检出,会得到一个内容为路径的普通文本文件。</p>'),
     ('子模块', '<p>子模块在父仓库里只占一个 <code>160000 commit</code> 条目,hash 是子仓库的某个 commit。这个对象不在父仓库的对象库里,父仓库自己的 <code>git cat-file</code> 找不到它;路径与 URL 记录在 <code>.gitmodules</code> 里。</p>'),
     ('模式会被规整', '<p>写入索引时 git 把非标准的文件模式规整:<code>100664</code>、<code>100600</code> → <code>100644</code>,<code>100777</code> → <code>100755</code>,<code>120755</code> → <code>120000</code>。权限位只剩“是否可执行”一个信息。</p>')],
    steps,
    [ENV_I_GIT + '。子模块用本机另一个目录当远程(git -c protocol.file.allow=always submodule add);符号链接在 macOS 文件系统上创建;原始字节来自对象文件的 zlib 解压',
     '没有验证:Windows 上检出符号链接的行为(core.symlinks=false);--cacheinfo 之外(如 git add 在不同 core.fileMode 下)的模式规整,见后面 core.fileMode 一篇;旧仓库里历史遗留的 100664 在 fsck 下的告警;子模块的更新流程(后面有专门一篇)'],
    '四种模式')
