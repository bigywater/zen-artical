from lib import *
R = J('d75')
steps = [
    step("一开始就用自定义 User:class User(AbstractUser) + AUTH_USER_MODEL = 'lab.User',首次 migrate 顺利。get_user_model() = lab.models.User,表名 lab_user,库里根本没有 auth_user 表;外键用 settings.AUTH_USER_MODEL 引用它;自定义字段(phone)可用。", t=tl(R['fresh'].splitlines()), kv=KV([['起点', '第一次 migrate 之前决定']], ['起点'])),
    step("项目已经用默认 User 迁移过、还有数据,再把 AUTH_USER_MODEL 改成 lab.User:makemigrations 会生成 Create model User,但 migrate 报错 " + R['switch_migrate'].split(': ', 1)[-1] + " 已有的 auth_user 表和数据都还在,新模型没有接上。", t=tl(['makemigrations:' + R['switch_make'].strip(), 'migrate:' + R['switch_migrate'], R['tables']], mark=[1]), kv=KV([['中途替换', 'InconsistentMigrationHistory']], ['中途替换'])),
    step("不需要换 User 时的做法:保持默认 User,用一个 OneToOne 的 Profile 扩展字段。Profile.user 指向 settings.AUTH_USER_MODEL,创建后 u.profile.phone 可直接访问。", t=tl(R['profile'].splitlines()), kv=KV([['只加字段', 'Profile 一对一扩展就够']], ['只加字段'])),
    step("所以「什么时候该换」:如果你觉得将来可能要改用户模型(邮箱登录、手机号、额外字段),在第一次 migrate 之前就继承 AbstractUser 建一个自定义 User——哪怕现在它是空的(class User(AbstractUser): pass)。之后再改的成本是重写迁移历史(本文没有演示如何安全迁移)。", kv=KV([['建议', '项目开始时就定义,哪怕先留空']], ['建议'])),
]
A = dict(
    n=75, series='django', tags='Django,自定义User,AUTH_USER_MODEL,迁移,真实验证,动画演示',
    desc='实测自定义 User Model 的时机:一开始设置 AUTH_USER_MODEL,库里没有 auth_user 表;项目已迁移后再切换,migrate 报 InconsistentMigrationHistory(admin.0001 先于 lab.0001 已应用);只想加字段时用 OneToOne Profile 即可。',
    lead='官方文档说「一开始就用自定义 User」。晚了到底会怎样?这篇分别做「一开始就自定义」「已迁移后再切换」「只加字段用 Profile」三种情形,把报错原文和数据库状态摆出来。',
    facts=[('第一次 migrate 之前', 'AUTH_USER_MODEL 要在第一次 migrate 之前设置;之后切换会 InconsistentMigrationHistory'), ('没有 auth_user', '一开始就自定义时,库里只有 lab_user'), ('Profile', '只想加字段、不改认证行为时,OneToOne Profile 不需要换 User')],
    body=[
        sec('从头就自定义', '', term('', blk('d75', 1)), '<p>所有指向用户的外键都要写 <code>settings.AUTH_USER_MODEL</code>(字符串),代码里取模型用 <code>get_user_model()</code>,不要直接 <code>from django.contrib.auth.models import User</code>。</p>'),
        sec('中途替换', '', term('', blk('d75', 2)), '<p>报错的原因:<code>admin</code> 等应用的迁移依赖了用户模型(<code>settings.AUTH_USER_MODEL</code>),已经在默认 User 上应用过;换了之后依赖顺序被破坏。原有 <code>auth_user</code> 表和数据没有自动搬到新表。</p>'),
        sec('Profile 扩展', '', term('', blk('d75', 3)), '<p>代价是多一次 JOIN 或查询(可用 <code>select_related</code>,第 28 篇)。</p>'),
        sec('分步演示:何时换 User', '', demo('自定义 User Model', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite;项目里装了 admin / sessions / messages(admin 的检查要求相应的中间件与上下文处理器,已配置)', '没有验证:中途安全迁移到自定义 User 的做法(手工改迁移 / 重命名表)、AbstractBaseUser 从零实现、USERNAME_FIELD 为邮箱、swappable 模型的其它影响、与第三方 app 的兼容'],
)
