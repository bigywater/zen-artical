from lib import *
S = SS('l9')
steps = [
    step("在磁盘上造十种权限的文件再 git add:600、611、640、644、664 进去都是 100644;700、711、744、755、775 进去都是 100755(run.sh 也是 100755)。判据只有一个:属主有没有可执行位。611 的属主是 rw-、组和其他有 x,仍是 100644;700 的属主只有 rwx,是 100755。读写权限、组和其他人的权限都不记录。", t=tl(S(1)), mark=lidx(S(1), '100644 p611', '100755 p700', '100755 p711'), done=lidx(S(1), '100644 p600', '100644 p640', '100755 p744', '100755 p775'), kv=KV([['记录的信息', '属主是否有 x:100644 或 100755'], ['不记录', '读写位、组和其他人的权限']], ['记录的信息'])),
    step("clone 出去再检出:600、611、640、664 都变成 644;700、711、744、775 都变成 755(umask 是 0022)。原来的 600、664 等细节全部丢了:检出时 git 按 100644 → 666 & ~umask、100755 → 777 & ~umask 创建文件。", t=tl(S(2)), mark=lidx(S(2), 'umask', '0022'), done=lidx(S(2), '644 p600', '755 p700'), kv=KV([['检出时', '100644 → 666 & ~umask'], ['', '100755 → 777 & ~umask'], ['原来的细节', '全部丢失']], ['检出时'])),
    step("默认 core.fileMode=true:chmod 755 data.txt 之后 git status 显示 M data.txt,git diff 显示 old mode 100644 → new mode 100755(没有内容改动);git add 后暂存区里模式是 100755,提交的 --stat 显示 data.txt | 0——文件内容没变,只有模式变了,提交里仍有这个改动。", t=tl(S(3)), mark=lidx(S(3), 'old mode 100644', 'new mode 100755'), done=lidx(S(3), 'M data.txt', '100755 587be6b', 'data.txt | 0'), kv=KV([['权限变化', 'status 里显示 M,diff 显示 old/new mode'], ['提交', '内容不变也能产生一个提交(--stat 里 0 行)']], ['权限变化'])),
    step("core.fileMode=false:chmod 644 data.txt 之后 git status 是空的,暂存区里还是 100755;改回 true 之后 status 立刻显示 M data.txt。git init 在这台机器上探测到文件系统保存权限位,自动设置了 core.fileMode=true。false 是给不保存权限位的文件系统准备的,git 在它们上面会自动设成 false。", t=tl(S(4)), mark=lidx(S(4), 'fileMode=false 下 chmod 644 后 status 为空', 'true'), done=lidx(S(4), '100755 587be6b', 'M data.txt'), kv=KV([['fileMode=false', '忽略磁盘权限位的变化'], ['git init', '探测文件系统,本机是 true'], ['适用', '不保存权限位的文件系统']], ['fileMode=false'])),
    step("fileMode=false 时 add 新文件:磁盘上 tool.sh 是 755,但暂存区里记成了 100644(不看磁盘权限)。手动指定:git update-index --chmod=+x 变成 100755,--chmod=-x 再变回 100644;切回 true 之后再 +x,status 显示 A tool.sh。", t=tl(S(5)), mark=lidx(S(5), '--chmod=+x', '--chmod=-x'), done=lidx(S(5), '100644 1a24852', 'A  tool.sh'), kv=KV([['fileMode=false 下 add', '新文件一律 100644'], ['--chmod=+x / -x', '手工设定可执行位'], ['用途', '在 Windows 等环境里提交脚本']], ['--chmod=+x / -x'])),
    step("另一面:已提交为 100755 的 tool.sh 在磁盘上被 chmod 644,fileMode=true 时 status 显示 M tool.sh;fileMode=false 时 status 为空,看不出变化,暂存区仍是 100755;改回 true 之后 git diff --summary 显示 mode change 100755 => 100644。要是在 false 环境里重新提交,权限丢失不会被察觉。", t=tl(S(6)), mark=lidx(S(6), 'mode change 100755 => 100644', 'fileMode=false 时 status 为空'), done=lidx(S(6), ' M tool.sh', '100755 1a24852'), kv=KV([['风险', 'fileMode=false 隐藏真实的权限丢失'], ['诊断', '临时改回 true,看 git diff --summary'], ['建议', '只在确实无法保存权限位时才用 false']], ['风险'])),
]
A = mkarti('l9', 9, 'Git,文件权限,core.fileMode,100755,umask,真实验证,动画演示',
    '在真实仓库里验证 git 只记录属主的可执行位:十种磁盘权限进去只有 100644 和 100755;检出时按 umask 重新生成权限;core.fileMode=true 时 chmod 会产生只有 old mode / new mode 的改动,false 时被忽略,新文件一律记成 100644,可用 update-index --chmod 手工指定。',
    '为什么改了文件权限 git status 也会报告改动?core.fileMode 到底管什么?这篇造十种权限的文件看 git 记成什么、检出后又变成什么,再比较 fileMode 为 true 和 false 时 chmod、add、update-index 的表现。',
    [('2 种', '十种磁盘权限提交进去只有 100644 和 100755 两种'), ('0 行', '只改权限的提交,--stat 里 data.txt | 0,但这个提交仍然存在'), ('静默', 'core.fileMode=false 时 chmod 644 一个已提交为 100755 的文件,status 不显示任何变化')],
    [('只记录一个位', '<p>git 对每个文件只记录一个信息:属主有没有可执行位,记成 <code>100755</code> 或 <code>100644</code>。读写位、组和其他人的权限一概不记。</p>'),
     ('检出时重新生成', '<p>检出时按 umask 重新生成权限:100644 变成 666 & ~umask(这里是 644),100755 变成 777 & ~umask(755)。所以 600、664 这样的细节无法通过 git 传递。</p>'),
     ('fileMode=true', '<p>默认情况下 <code>chmod</code> 会被 git 看作改动:<code>git diff</code> 显示 <code>old mode</code> / <code>new mode</code>,可以提交,提交里只有模式变化而没有行数变化。</p>'),
     ('fileMode=false', '<p>在不保存权限位的文件系统上 git 会自动把 <code>core.fileMode</code> 设成 false,此时磁盘权限的变化被忽略。这台机器上 <code>git init</code> 探测到的是 true。</p>'),
     ('手工指定可执行位', '<p>fileMode=false 时新文件一律记成 100644;要提交可执行脚本,用 <code>git update-index --chmod=+x</code> 手工设置。</p>'),
     ('风险', '<p>false 会隐藏真实的权限丢失:已提交为 100755 的文件在磁盘上失去可执行位,status 看不出来。怀疑权限被破坏时,临时切回 true 再看 <code>git diff --summary</code>。</p>')],
    steps,
    [ENV_I_GIT + '。文件系统是 macOS 的 APFS;umask 为 0022;所有权限数字来自 stat 与 git ls-files -s',
     '没有验证:Windows / FAT / exFAT 等文件系统上 git init 自动设置 core.fileMode=false 的探测过程;core.sharedRepository 对仓库内部文件权限的影响;ACL、扩展属性(macOS 的 @)是否会被 git 记录;git archive 导出时的权限'],
    '文件权限')
