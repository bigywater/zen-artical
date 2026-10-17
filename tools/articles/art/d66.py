from lib import *
R = J('d66')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("编辑已有对象:标签从 {a, b} 改成 {b, c}。ModelForm 保存多对多用 .set():先 SELECT 现有关系,只 DELETE 被去掉的(tag_id IN (1)),只 INSERT 新增的(INSERT OR IGNORE … (1, 3)),没变的 b 不动。不是「先全部清空再全部重建」。", t=tl(L('diff')), kv=KV([['set()', '按差集增删,不清空重建']], ['set()'])),
    step("空提交:blank=True 的多选字段,不提交(等同于全部取消勾选)→ 校验通过,保存后 tags 被清空 []。把字段声明成 required=True,则报 required 错误。注意:「没提交」在 HTML 表单里就是「一个都没勾」,和「字段不在表单里」是两回事——后者(fields 里没有 tags)不会动多对多。", t=tl(L('empty')), kv=KV([['取消全部勾选', '会清空多对多']], ['取消全部勾选'])),
    step("非法选项:提交不存在的 id(99999)→ invalid_choice,params 里带 value;用自定义 queryset 限制可选范围(只允许 a、b),提交范围外的 d → invalid_choice。queryset 既是下拉框的选项,也是校验的白名单。", t=tl(L('invalid')), kv=KV([['queryset', '选项 + 校验白名单']], ['queryset'])),
    step("自定义 through 模型(带额外字段 role):ModelForm 仍可包含 members 字段并保存(Team 表单提交 members → 写入 Membership),但 role 只能取模型上的 default('dev'),表单无法为每个成员指定 role;SQL 是一条 INSERT INTO lab_membership … VALUES (…,'dev')。需要不同 role 就要用 through 模型自己的 FormSet。", t=tl(L('through')), kv=KV([['带额外字段的 through', 'role 取默认值,不能逐个指定']], ['带额外字段的 through'])),
]
A = dict(
    n=66, series='django', tags='Django,ModelForm,多对多,真实验证,动画演示',
    desc='实测 ModelForm 多对多保存:save_m2m 用 set() 做差集(标签 {a,b} → {b,c} 只 DELETE a、INSERT c);取消全部勾选会清空;queryset 是校验白名单;自定义 through 模型的额外字段只能取默认值。',
    lead='ModelForm 保存多对多是先清空再重建吗?取消全部勾选会怎样?有额外字段的 through 表能用表单保存吗?这篇看每种情形的 SQL。',
    facts=[('差集', '保存时只删除被去掉的、只插入新增的关系,没变的不动'), ('清空', '编辑时一个都不勾选 = 清空多对多(blank=True 时)'), ('through 额外字段', '表单保存时 role 只能取默认值')],
    body=[
        sec('保存时的 SQL', '', term('', blk('d66', 1)), '<p>并发场景下这比「先全删再全建」更友好:没变的关系行不会被删除又重建(不会短暂消失)。</p>'),
        sec('空提交与必填', '', term('', blk('d66', 2)), '<p>把「不勾选」当作「清空」是符合直觉的,但如果前端漏渲染了这个字段,保存就会清空用户已有的关系——所以 fields 白名单里的多对多字段一定要在模板里渲染。</p>'),
        sec('校验与 queryset', '', term('', blk('d66', 3)), '<p>用 queryset 限制用户能关联到哪些对象(比如只能选自己的标签)。</p>'),
        sec('自定义 through', '', term('', blk('d66', 4)), '<p>Django 允许对自定义 through 模型的多对多使用 <code>add()</code>/<code>set()</code>,前提是额外字段都有默认值(或用 <code>through_defaults</code> 指定)。</p>'),
        sec('分步演示:多对多保存', '', demo('ModelForm 多对多', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite', '没有验证:PostgreSQL 上同样的 SQL(INSERT ... ON CONFLICT DO NOTHING)、自引用多对多、through_defaults 的用法、大量选项时 ModelMultipleChoiceField 的性能'],
)
