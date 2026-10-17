from lib import *
S = SS('l49')
steps = [
    step("合并提交 M(合并 feature(M))有两个 parent:^1 是合并时你所在的 main 的末端(M2 主线上的提交),^2 是被合并进来的 feature 的末端(F2 功能的第二步)。M 之后 main 上还有 M3。当前文件:base.txt、f1.txt、f2.txt、m2.txt、m3.txt。", t=tl(S(1)), mark=lidx(S(1), 'M^1', 'M^2'), done=lidx(S(1), '合并 feature(M)', 'M3 合并之后的提交', '当前文件'), kv=KV([['M^1', '合并时所在的分支(main)'], ['M^2', '被合并进来的分支(feature)'], ['当前文件', 'f1、f2 来自 feature,m2 来自 main']], ['M^2'])),
    step("git revert M 直接报错:error: commit … is a merge but no -m option was given. 和 fatal: revert failed。revert 要算“这个提交相对它的 parent 改了什么,再反过来做一遍”;合并提交有两个 parent,算出的差异完全不同,git 不替你猜,要你用 -m 指定哪个 parent 是“主线”。", t=tl(S(2)), mark=lidx(S(2), 'is a merge but no -m option was given', 'revert failed'), done=lidx(S(2), 'git revert --no-edit'), kv=KV([['revert', '= 撤销“提交相对 parent 的差异”'], ['合并提交', '有两个 parent,差异不唯一'], ['-m <n>', '指定哪个 parent 是主线']], ['-m <n>'])),
    step("-m 1:以 ^1(main 一侧)为主线,撤销的是 feature 带进来的内容。revert 之后文件变成 base.txt、m2.txt、m3.txt——f1、f2 没了,m2、m3 还在;自动生成的说明是 Revert \"合并 feature(M)\" 加 This reverts commit …, reversing changes made to …。把现在的 HEAD 与 M 的 ^1(M2)比较,差异文件只有 m3.txt:M 之后的改动保留,feature 的改动被撤销。", t=tl(S(3)), mark=lidx(S(3), 'base.txt m2.txt m3.txt', 'Revert "合并 feature(M)"'), done=lidx(S(3), '差异文件只有', 'This reverts commit'), kv=KV([['-m 1', '主线 = main,撤销 feature 带来的东西'], ['保留', 'M 之后 main 上的提交'], ['最常用', '撤销一个已经合并的功能']], ['-m 1'])),
    step("-m 2:以 ^2(feature 一侧)为主线,撤销的是 main 带进来的内容。结果文件变成 base.txt、f1.txt、f2.txt、m3.txt——m2.txt 没了,f1、f2 还在。这等于“把 main 在分叉之后的改动撤销”,通常不是想要的结果。选 -m 1 还是 -m 2,取决于你把哪一侧当作主线。", t=tl(S(4)), mark=lidx(S(4), 'base.txt f1.txt f2.txt m3.txt'), done=lidx(S(4), 'm2.txt 没了'), kv=KV([['-m 2', '主线 = feature,撤销 main 带来的东西'], ['m2.txt', '被撤销'], ['f1 / f2', '保留']], ['-m 2'])),
    step("revert 合并之后再合并同一个 feature 会丢东西:revert M(-m 1)之后,feature 上又提交了 F3,再 git merge feature,只带来了 f3.txt(文件变成 base、f3、m2、m3),f1.txt、f2.txt 没有回来。因为 F1、F2 在提交图里仍然是 main 的祖先——git 认为它们早已合并过,不会再次应用;revert 只是新增了一个反向修改的提交,没有改变“已合并”的历史。git log --graph 里可以看到 M 和 Revert 都还在。", t=tl(S(5)), mark=lidx(S(5), 'f1.txt、f2.txt 没有回来', 'Revert "合并 feature(M)"'), done=lidx(S(5), 'Merge branch \'feature\'', 'F3 功能的第三步'), kv=KV([['revert 不改变祖先关系', 'F1、F2 仍是 main 的祖先'], ['再合并', '只带来之后新增的提交'], ['后果', '功能缺了一半']], ['revert 不改变祖先关系'])),
    step("正确做法:先 git revert 那次 revert(把 F1、F2 的改动恢复),f1、f2 回来;然后 feature 上有了 F3 再合并,结果 base.txt f1.txt f2.txt f3.txt m2.txt m3.txt 全部都在。官方文档把这个叫做“revert the revert”:要重新带入一个曾被 revert 的分支,先把当初的 revert 本身 revert 掉。", t=tl(S(6)), mark=lidx(S(6), '再合并 feature'), done=lidx(S(6), 'revert 了 revert 之后', 'Merge made by'), kv=KV([['revert the revert', '先恢复被撤销的改动'], ['再合并', '带来之后新增的提交'], ['替代', '或者在 feature 上 rebase / 重建分支']], ['revert the revert'])),
]
A = mkarti('l49', 49, 'Git,revert,合并提交,-m,真实验证,动画演示',
    '实测撤销一个合并提交:git revert 直接报错 is a merge but no -m option was given;-m 1(以 main 为主线)撤销 feature 带来的东西,-m 2 反过来撤销 main 带来的东西;revert 之后再合并同一个分支,git 认为已合并过,只带来之后新增的提交;要先 revert 那次 revert 才能恢复。',
    '为什么 revert 一个 merge commit 必须加 -m?-m 1 和 -m 2 的结果有什么不同?revert 之后再合并同一个分支为什么会丢提交?这篇造出一个合并,逐项验证。',
    [('-m 1 / -m 2', '撤销 feature 带来的(f1、f2 消失)与撤销 main 带来的(m2 消失)'), ('f3 only', 'revert 合并之后再合并同一个 feature,只带来新增的 f3,f1、f2 没有回来'), ('revert the revert', '要先 revert 那次 revert,才能再次带入被撤销的改动')],
    [('合并提交的两个 parent', '<p>合并提交 M 有两个 parent:<code>M^1</code> 是合并时所在的分支(这里是 main 的 M2),<code>M^2</code> 是被合并进来的分支的末端(feature 的 F2)。合并之后 main 上还可以继续有提交(M3)。</p>'),
     ('为什么需要 -m', '<p>revert 的做法是“撤销这个提交相对它的 parent 的差异”。合并提交有两个 parent,相对不同 parent 的差异完全不同,所以必须用 <code>-m &lt;n&gt;</code> 指定主线 parent,否则报 <code>is a merge but no -m option was given</code>。</p>'),
     ('-m 1', '<p>以第一个 parent(合并时所在的分支,通常是 main)为主线,撤销被合并进来的分支带来的内容。这是撤销一个已合并功能时最常用的写法;合并之后 main 上的其它提交保留。</p>'),
     ('-m 2', '<p>以第二个 parent(被合并的分支)为主线,撤销的是 main 带来的内容,结果通常不是想要的。</p>'),
     ('陷阱', '<p><code>revert</code> 只是新增一个反向修改的提交,不改变提交图里的祖先关系。被撤销的分支提交仍是 main 的祖先,所以之后再合并同一个分支时,git 认为它们已经合并过,只带来之后新增的提交。</p>'),
     ('怎么挽回', '<p>先对那次 revert 提交再做一次 revert(把被撤销的改动恢复),之后的合并就会正常带来新增的提交。或者把 feature 分支 rebase / 重建,让它的提交成为新的提交。</p>')],
    steps,
    [ENV_I_GIT + '。合并提交 M 用 --no-ff 创建;所有的 revert 使用 --no-edit;每个场景在单独的仓库里重做',
     '没有验证:revert 后用 git merge --no-ff 重新合并而不是 revert the revert 的其它办法;revert 的冲突(合并提交之后有其它改动时);git cherry-pick -m 的对应行为;章鱼合并(三个以上 parent)的 revert;多次 revert 同一个合并的历史形状'],
    'revert 合并提交')
