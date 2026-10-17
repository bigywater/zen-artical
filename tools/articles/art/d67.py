from lib import *
R = J('d67')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("FormSet 靠 ManagementForm 记录「一共有几个表单」:未绑定时 management_form 的初始值是 TOTAL_FORMS=2(extra)、INITIAL_FORMS=0、MIN_NUM_FORMS=0、MAX_NUM_FORMS=1000,渲染成隐藏字段。提交时带上它,is_valid() 才成立;不带则 ValidationError:ManagementForm data is missing or has been tampered with(code = missing_management_form)。", t=tl(L('mgmt')), kv=KV([['TOTAL_FORMS', '由客户端提交,决定服务端处理几个表单']], ['TOTAL_FORMS'])),
    step("数量约束:min_num=2 + extra=1 → 未绑定时显示 3 个表单;validate_min=True 时只提交 1 个 → 'Please submit at least 2 forms.';max_num=3 + validate_max=True 时提交 5 个 → 'Please submit at most 3 forms.';can_delete=True 时第 2 个勾选 DELETE → cleaned_data 里 DELETE: True,deleted_forms = 1。", t=tl(L('limits')), kv=KV([['validate_min / validate_max', '校验提交的数量'], ['DELETE', '标记删除,由 save() 处理']], ['validate_min / validate_max'])),
    step("InlineFormSet:inlineformset_factory(Author, Book) 自动把 Book 的外键 author 关联到父对象(表单字段里有 author 隐藏字段);提交 2 本书,save() 只用 2 次查询(两条 INSERT),保存的对象 author_id 都是父对象。重新打开编辑页:2 个已有 + extra 2 = 4 个表单,INITIAL_FORMS = 2。", t=tl(L('inline')), kv=KV([['inline', '父对象 + 外键自动关联']], ['inline'])),
    step("N+1:10 本书、每本一个 editor 的下拉框(ModelChoiceField),渲染整个 FormSet 共 11 次查询:1 次取书 + 每个表单各 1 次 SELECT lab_editor 取选项。每个表单实例都独立求值选项 queryset。要避免可以给字段的 queryset 换成已缓存的选项(本文没有验证具体做法)。", t=tl(L('nplus')), mark=[0], kv=KV([['FormSet 里的 ModelChoiceField', '每个表单一次查询']], ['FormSet 里的 ModelChoiceField'])),
]
A = dict(
    n=67, series='django', tags='Django,FormSet,InlineFormSet,真实验证,动画演示',
    desc='实测 FormSet 与 InlineFormSet:ManagementForm 的字段与缺失时的错误(missing_management_form);min_num / max_num / validate_min / validate_max / can_delete;inline 自动关联父对象;10 个表单的外键下拉框渲染发出 11 次查询(N+1)。',
    lead='FormSet 是「一次提交多个同类表单」的机制。它靠什么知道有几个表单?怎么限制数量?inline 是怎么关联父对象的?为什么渲染时会发 N 次查询?这篇逐项验证。',
    facts=[('ManagementForm', '客户端提交的 TOTAL_FORMS 决定处理几个表单;缺失即校验失败'), ('11 次', '10 个表单各带一个外键下拉框时渲染 FormSet 的查询数(1 + 10)'), ('validate_min / max', '要显式打开,才会校验提交的表单数量')],
    body=[
        sec('ManagementForm', '', term('', blk('d67', 1)), '<p>模板里忘了渲染 <code>{{ formset.management_form }}</code>,提交时就是这个错误——看起来像「表单坏了」,其实是缺隐藏字段。</p>'),
        sec('数量与删除', '', term('', blk('d67', 2)), '<p><code>min_num</code>/<code>max_num</code> 默认只影响「显示几个」;要拒绝不符合数量的提交,必须 <code>validate_min</code>/<code>validate_max</code>。实测未绑定 FormSet 的 <code>MAX_NUM_FORMS</code> 初始值是 1000(没有测提交超过它时的行为)。</p>'),
        sec('InlineFormSet', '', term('', blk('d67', 3)), '<p>父对象通过 <code>instance=</code> 传入,外键字段由 Django 自动处理。</p>'),
        sec('N+1', '', term('', blk('d67', 4)), '<p>每个表单实例创建自己的 <code>ModelChoiceField</code> 选项,渲染时各自查询。表单数多、选项字段多时明显。</p>'),
        sec('分步演示:FormSet', '', demo('FormSet', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite', '没有验证:modelformset_factory 的保存行为、formset 里的 unique 校验(跨表单重复)、JS 动态增删表单时 TOTAL_FORMS 的维护、N+1 的具体解决办法'],
)
