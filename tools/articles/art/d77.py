from lib import *
R = J('d77')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("每个模型迁移后自动有 add / change / delete / view 四个权限;Meta.permissions 里声明的 publish_article 也一起创建:['add_article', 'change_article', 'delete_article', 'publish_article', 'view_article']。权限的全名是 app_label.codename,如 lab.add_article。", t=tl(L('perms')), kv=KV([['默认', '四个权限 + Meta.permissions']], ['默认'])),
    step("has_perm 的规则:没有任何权限 False;直接授予 add_article 后,同一个 user 对象上再调 has_perm 仍是 False(权限缓存);重新从库里取用户才是 True;通过组获得权限同样(新取用户 True);超级用户对任意字符串都返回 True;超级用户但 is_active=False → False;只写 codename 不带 app_label 也是 False。", t=tl(L('has_perm')), mark=[1], cur=[2, 3, 4], kv=KV([['缓存', '同一个 user 对象上不会看到新权限'], ['不活跃', '超级用户也没有权限']], ['缓存'])),
    step("缓存机制:第一次 has_perm 发 2 次查询(用户权限 + 组权限),同一个用户对象上再查其它权限 0 次查询;缓存放在对象上(_perm_cache、_user_perm_cache、_group_perm_cache)。在视图里给用户加了权限、又在同一个请求里检查它时,要重新取用户。", t=tl(L('cache')), b=bars([['第一次 has_perm 查询数', 2, '2'], ['之后再查其它权限', 0, '0']], 3, mark=[0], done=[1]), kv=KV([['第一次', '2 次查询'], ['之后', '0 次(对象上缓存)']], ['第一次'])),
    step("对象级权限:默认后端不支持——有 change_article 权限的用户,has_perm('lab.change_article') 是 True,但带对象 has_perm('lab.change_article', obj) 一律 False;超级用户不受限。要做「只能改自己的文章」需要自定义认证后端或用第三方库(如 django-guardian,本文没有测)。", t=tl(L('obj')), kv=KV([['obj 参数', '默认后端恒为 False(超级用户除外)']], ['obj 参数'])),
]
A = dict(
    n=77, series='django', tags='Django,权限,Groups,Permissions,真实验证,动画演示',
    desc='实测 Django 权限:每个模型 add/change/delete/view 四个默认权限 + Meta.permissions;has_perm 在同一个 user 对象上缓存(授予权限后仍返回 False,重新取用户才 True);超级用户与不活跃用户;默认后端不支持对象级权限。',
    lead='用户有没有某个权限,Django 怎么算?为什么刚给用户加了权限,has_perm 还是 False?对象级权限支持吗?这篇逐条验证。',
    facts=[('缓存', 'has_perm 的结果缓存在 user 对象上,同一对象上授予权限后不会立刻生效'), ('is_active', '超级用户如果 is_active=False,has_perm 也是 False'), ('对象级', '默认后端的 has_perm(perm, obj) 恒为 False(超级用户除外)')],
    body=[
        sec('默认权限', '', term('', blk('d77', 1)), '<p>权限行由 <code>post_migrate</code> 信号创建,所以新加的模型要迁移之后才有权限行。</p>'),
        sec('has_perm 的规则', '', term('', blk('d77', 2)), '<p>需要 <code>app_label.codename</code> 全名。组的权限和直接授予的权限取并集。</p>'),
        sec('权限缓存', '', term('', blk('d77', 3)), '<p>在 <code>request.user</code> 上调用 <code>has_perm</code> 时,缓存存在这个对象上,随请求结束消失,所以「每个请求最多查两次库」。但在测试或脚本里长期持有同一个 user 对象时容易踩坑。</p>'),
        sec('对象级权限', '', term('', blk('d77', 4)), '<p>Django 提供了 <code>obj</code> 参数的接口,但默认的 <code>ModelBackend</code> 不实现。</p>'),
        sec('分步演示:权限检查', '', demo('权限', [('t', 'term', '输出'), ('b', 'bars', '查询次数'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite', '没有验证:Permission 与 ContentType 缓存(ContentType.objects 的缓存)、权限检查在 admin 里的使用、组权限的变更传播、自定义后端实现对象级权限'],
)
