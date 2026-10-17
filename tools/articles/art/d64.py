from lib import *
R = J('d64')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("ModelForm 按模型字段自动生成表单字段:CharField→CharField/TextInput,TextField→Textarea,ForeignKey→ModelChoiceField/Select,BooleanField→CheckboxInput,SlugField→SlugField;有 blank=True / default 的变成 required=False。auto_now_add 的 created 和自增 id 因为不可编辑,不出现在表单里。", t=tl(L('gen')), kv=KV([['字段映射', '自动'], ['不可编辑', 'created、id 不生成']], ['字段映射'])),
    step("批量赋值风险:Meta.fields = '__all__' 时,用户在请求里额外提交 is_featured / published,保存后 is_featured = True、published = True;改成白名单 fields = ['title', 'body', 'slug', 'author'] 后,同样的提交这两个字段被忽略(False)。永远用白名单。", t=tl(L('mass')), n=fl([["fields = '__all__'", '用户能改 is_featured'], ["fields = [白名单]", '多余字段被忽略']], mark=[0], done=[1]), kv=KV([["'__all__'", '会暴露以后新增的每个字段']], ["'__all__'"])),
    step("ModelForm 的校验包含模型校验:slug 重复 → unique 错误(消息 %(model_name)s with this %(field_label)s already exists.);title 超长 → max_length;slug 格式错 → invalid;author 指向不存在的行 → invalid_choice。", t=tl(L('valid')), kv=KV([['ModelForm', '表单校验 + 模型校验(unique / validators)']], ['ModelForm'])),
    step("instance 与校验:编辑时传 instance=p,校验失败(slug 空)后内存里的 p.title 已经被改成用户提交的 'changed',库里仍是 orig;校验通过但还没 save() 时库里也是 orig,save() 之后才是 changed。所以校验失败时不要继续使用那个 instance 去渲染其他页面。", t=tl(L('instance')), kv=KV([['校验失败之后', 'instance 已被部分修改(内存)']], ['校验失败之后'])),
]
A = dict(
    n=64, series='django', tags='Django,Form,ModelForm,真实验证,动画演示',
    desc='实测 Form 与 ModelForm 的区别:字段自动生成、fields = "__all__" 让用户改到 is_featured(白名单则被忽略)、校验包含 unique 与模型 validators、校验失败后 instance 在内存里已被改写。',
    lead='ModelForm 相比 Form 多做了什么?最危险的一点是什么?这篇看字段是怎么生成的,再用两个 Meta.fields 写法演示批量赋值风险,最后看 instance 在校验前后的状态。',
    facts=[("'__all__'", '用户额外提交的 is_featured 被保存;白名单写法则被忽略'), ('unique', 'ModelForm 校验会查库检查 unique,错误 code = unique'), ('instance', '校验失败后内存中的 instance 已经被用户提交的值改写')],
    body=[
        sec('字段自动生成', '', term('', blk('d64', 1)), '<p>模型的 <code>editable=False</code> 字段(自增主键、<code>auto_now_add</code>)不会出现。生成的表单字段和 widget 可以在 <code>Meta.widgets</code> / <code>Meta.labels</code> 里覆盖(本文没有测)。</p>'),
        sec('Meta.fields 与批量赋值', '', term('', blk('d64', 2)), '<p>ModelForm 只处理 <code>fields</code> 列出的字段。用 <code>\'__all__\'</code> 或 <code>exclude</code> 意味着以后给模型加任何字段,都会自动变成用户可提交的字段。</p>'),
        sec('校验', '', term('', blk('d64', 3)), '<p>这些错误来自三个来源:表单字段(<code>invalid_choice</code>)、模型字段类型与 validators(<code>max_length</code>、<code>invalid</code>)、<code>validate_unique</code>(<code>unique</code>)。</p>'),
        sec('instance', '', term('', blk('d64', 4)), '<p>ModelForm 在 <code>_post_clean()</code> 里把 <code>cleaned_data</code> 写到 <code>instance</code> 上再校验。失败时对象已被改。</p>'),
        sec('分步演示:ModelForm', '', demo('ModelForm', [('t', 'term', '输出'), ('n', 'flow', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite', '没有验证:Meta.exclude 的行为、formfield_callback、对 JSONField / ArrayField 的自动映射、instance 与 commit=False 的组合(第 65 篇)'],
)
