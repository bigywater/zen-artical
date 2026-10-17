from lib import *
S = SS('l5')
steps = [
    step("对象数的变化:打标签之前 .git/objects 里 3 个对象(1 个 commit、1 个 tree、1 个 blob);git tag light 之后还是 3 个——轻量标签只在 .git/refs/tags/light 写了一个文件,内容就是 commit 的 hash 30385d3…;git tag -a annot 之后变成 4 个,refs/tags/annot 里的 hash 是 8542d98…,不等于 commit 的 30385d3…,因为它指向的是新生成的 tag 对象。", t=tl(S(1)), mark=lidx(S(1), 'git tag -a annot 之后对象数: 4', '8542d98add695'), done=lidx(S(1), '打标签之前对象数: 3', 'git tag light 之后对象数: 3'), b=bars([['打标签之前', 3, '3 个对象'], ['轻量标签 light 之后', 3, '3 个'], ['注解标签 annot 之后', 4, '4 个']], 4, mark=[2], done=[0, 1]), kv=KV([['轻量标签', '一个 ref 文件,内容是 commit hash'], ['注解标签', 'ref 指向新的 tag 对象'], ['对象数', '轻量不变,注解 +1']], ['注解标签'])),
    step("tag 对象的原文:object(指向的对象)、type commit、tag annot(标签名)、tagger(打标签的人、时间戳、时区),一个空行,最后是说明“第一个注解标签”。git cat-file -t annot 得到 tag,而对轻量标签 light 得到 commit:轻量标签名字解出来的就是目标本身。", t=tl(S(2)), mark=lidx(S(2), 'object 30385d36', 'type commit', 'tag annot', 'tagger Alice'), done=lidx(S(2), 'git cat-file -t annot', '第一个注解标签', 'git cat-file -t light'), kv=KV([['object / type', '指向谁、是什么类型'], ['tag', '标签名'], ['tagger', '谁在什么时候打的'], ['light 的类型', 'commit(没有 tag 对象)']], ['tagger'])),
    step("同一个名字的不同写法:light 解出 30385d3(commit);annot 解出 8542d98(tag 对象);annot^{} 与 annot^{commit} 层层剥开,解出 30385d3;annot^{tag} 解出 8542d98。新提交上打了轻量标签 light2 后:git describe(默认只用注解标签)得到 annot-1-g77640ce;git describe --tags 得到 light2;HEAD~1 上有两个标签,--exact-match 选了注解标签 annot。", t=tl(S(3)), mark=lidx(S(3), 'annot^{}', 'git describe --tags', 'light2'), done=lidx(S(3), 'annot-1-g77640ce', 'annot^{tag}', 'exact-match'), kv=KV([['annot', '解出 tag 对象'], ['annot^{}', '剥开,得到最终的 commit'], ['describe', '默认只用注解标签,--tags 才包含轻量标签']], ['annot^{}'])),
    step("标签可以指向任何对象:给 annot 再打 nested(type tag,git 还提示这是嵌套标签);给 tree 打 ontree(type tree),给 blob 打 onblob(type blob)。git for-each-ref 的 objecttype 列显示:除了 light 和 light2(commit),其它几个都是 tag。", t=tl(S(4)), mark=lidx(S(4), 'type tag', 'type tree', 'type blob', 'nested tag'), done=lidx(S(4), '→ tag', '→ commit'), kv=KV([['嵌套标签', '标签指向标签,git 会提示'], ['tree / blob 标签', '可以,type 字段不同'], ['refs 的类型', 'for-each-ref 的 %(objecttype) 看得出']], ['嵌套标签'])),
    step("push --follow-tags 到本地裸仓库,只带上了 annot 和 nested(带注解、能从推送的提交到达的标签);轻量标签 light、light2 与指向 tree / blob 的标签没有被推送。把五个标签全删掉后,tag 对象还在对象库里:git fsck 报告 3 个 dangling tag(3033fe2、d1a592a、9ce851e);annot 因为被 nested 引用着,不算悬空。", t=tl(S(5)), mark=lidx(S(5), 'dangling tag', '--follow-tags 2>&1'), done=lidx(S(5), 'git push -q', 'Deleted tag'), kv=KV([['--follow-tags', '只推带注解、能到达的标签'], ['删标签', '只删 ref,tag 对象还在,直到 gc'], ['fsck', '把没人引用的 tag 对象列为 dangling']], ['--follow-tags'])),
]
A = mkarti('l5', 5, 'Git,tag,注解标签,轻量标签,真实验证,动画演示',
    '在真实仓库里区分轻量标签与注解标签:轻量标签只是一个 ref 文件(对象数不变),注解标签多一个 tag 对象(对象数 3 → 4,ref 指向它而不是 commit);读 tag 对象原文,用 ^{} 剥开;describe 默认只看注解标签;标签可以指向 tag、tree、blob;push --follow-tags 只推注解标签;删标签后 tag 对象成为悬空对象。',
    'git tag v1 和 git tag -a v1 -m ... 有什么区别?这篇数对象个数、读 tag 对象原文、用 ^{} 剥开标签,再让标签指向另一个标签、tree、blob,最后看 push --follow-tags 和删除标签的后果。',
    [('3 → 3 → 4', '打标签前、轻量标签后、注解标签后的对象总数'), ('tag 对象', '注解标签的 ref 指向一个独立的 tag 对象,而不是 commit'), ('--follow-tags', '本地推送实验里只带走了 2 个标签(annot、nested),轻量标签没有被推送')],
    [('轻量标签', '<p><code>git tag name</code> 只在 <code>refs/tags/</code> 下写一个文件,内容是目标 commit 的 hash,没有任何新对象。对它做 <code>git cat-file -t</code> 得到的就是 <code>commit</code>。</p>'),
     ('注解标签', '<p><code>git tag -a</code> 先创建一个 tag 对象,内容是被标记对象的 hash 和类型、标签名、打标签人和时间、说明,再让 <code>refs/tags/name</code> 指向这个 tag 对象。所以 ref 里的 hash 不等于 commit 的 hash。</p>'),
     ('剥开标签', '<p><code>name^{}</code> 把标签一层层剥开到最终对象,<code>name^{tag}</code> 停在 tag 对象。<code>git describe</code> 默认只用注解标签,<code>--tags</code> 才把轻量标签算进去;同一个提交上有两种标签时,优先选注解标签。</p>'),
     ('标签指向什么', '<p>标签可以指向任何对象:另一个标签(git 会提示这是嵌套标签)、tree、blob。实际中几乎都是 commit,但对象模型上没有限制。</p>'),
     ('推送与删除', '<p><code>--follow-tags</code> 只推送带注解、并且指向正在推送的历史的标签。删除标签只删 ref,tag 对象留在对象库里,<code>fsck</code> 把没人引用的那些列为 dangling,直到 <code>gc</code> 清理。</p>')],
    steps,
    [ENV_I_GIT + '。推送实验的远程是本机的一个裸仓库(git init --bare),没有走网络;标签说明与时间由环境变量固定',
     '没有验证:签名标签(git tag -s,需要 GPG 或 SSH 密钥,后面有 SSH 签名一篇);服务器端对标签更新的限制(本实验只验证了本地裸仓库);git describe 在多个候选标签之间选择的完整规则(只观察了本例);轻量标签重名覆盖时的 -f 行为'],
    '两种标签')
