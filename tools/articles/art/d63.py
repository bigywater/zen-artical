from lib import *
R = J('d63')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("模型字段的 validators 在 save() 时不运行:name='ROOT!!!'(违反小写字母正则)、age=999(超过 MaxValueValidator 150)照样 save() 成功、存进数据库;full_clean() 才会检查,得到 {'name': ['letters'], 'age': ['max_value']}。", t=tl(L('save_vs_clean')), n=fl([['save()', '不检查 validators'], ['full_clean()', '检查']], mark=[0], done=[1]), kv=KV([['save()', '不运行 validators'], ['full_clean()', '运行']], ['save()'])),
    step("字段的所有 validators 都会运行,错误累加:'ROOT12345' 同时得到 letters(正则)和 max_length(自动加入的 MaxLengthValidator);自定义函数 not_forbidden('root') 用 params 生成消息:用户名 root 被保留(code=reserved)。内置 MaxValueValidator 的 params 里带 limit_value / show_value / value。name 字段的 validators 顺序:自定义的在前,max_length 自动追加在最后。", t=tl(L('run_validators')), kv=KV([['错误累加', '不是遇到第一个就停']], ['错误累加'])),
    step("ModelForm 同样会运行模型字段的 validators:提交 name='ROOT'、age=200 → is_valid() False,errors 是 {'name': ['letters'], 'age': ['max_value']}。这些校验发生在 _post_clean() 里(调用 instance.full_clean)——表单字段自己带的校验器为空。", t=tl(L('modelform')), kv=KV([['ModelForm', '在 _post_clean 里跑模型校验']], ['ModelForm'])),
    step("unique 也是 validate_unique:full_clean() 查库,发现重复给 unique 错误(code = unique);直接 save() 则是数据库层面的 IntegrityError。前者友好、有竞态;后者是最终保证。", t=tl(L('unique')), kv=KV([['full_clean', '查库,有竞态窗口'], ['数据库约束', '最终保证']], ['数据库约束'])),
    step("可配置的校验器写成类:MaxWords(3) 的 __call__ 抛 ValidationError(code='max_words', params={'n': 2});要被迁移序列化必须加 @deconstructible(deconstruct() 返回 (路径, 参数, 关键字参数))。", t=tl(L('decon')), kv=KV([['deconstructible', '让迁移能写出校验器']], ['deconstructible'])),
]
A = dict(
    n=63, series='django', tags='Django,验证器,validators,真实验证,动画演示',
    desc='实测 Django 校验器:模型字段的 validators 在 save() 时不运行、full_clean() 才运行;所有 validators 错误累加;ModelForm 在 _post_clean 里运行模型校验;unique 由 full_clean 查库、save() 由数据库约束兜底;可配置校验器需要 @deconstructible。',
    lead='给字段加 validators 就能保证数据库里的值合法吗?不能。这篇验证校验器在 save()、full_clean()、ModelForm 里分别运行不运行,以及自定义校验器怎么写才规范。',
    facts=[('save() 不校验', 'validators 违反时 save() 照样成功;只有 full_clean() / ModelForm 才检查'), ('错误累加', '一个字段的所有 validators 都会运行,错误一起返回'), ('deconstructible', '可配置的校验器类要加它,迁移才能序列化')],
    body=[
        sec('save() vs full_clean()', '', term('', blk('d63', 1)), '<p>Django 认为「校验」是表单/序列化层的事,模型层只提供 <code>full_clean()</code> 让你主动调用。所以通过 shell、管理命令、<code>objects.create()</code> 写入的数据不会被校验器挡住。真正的数据完整性要靠数据库约束(<code>CheckConstraint</code>、<code>UniqueConstraint</code>,本文没有测)。</p>'),
        sec('validators 的运行', '', term('', blk('d63', 2)), '<p>一个校验器抛 <code>ValidationError</code> 后,同字段的其它校验器仍会执行,所有错误合并返回。</p>'),
        sec('ModelForm 与 unique', '', term('', blk('d63', 3)), term('', blk('d63', 4)), '<p>ModelForm 把模型校验接进了表单校验。<code>validate_unique</code> 先查再写,两个并发请求仍可能都通过,最终由数据库的唯一约束拒绝其中一个(第 35 篇)。</p>'),
        sec('可配置的校验器', '', term('', blk('d63', 5)), '<p>校验器实例要能比较相等(<code>__eq__</code>)并可序列化,否则每次 <code>makemigrations</code> 都会认为字段变了。</p>'),
        sec('分步演示:validators 在哪里运行', '', demo('validators', [('t', 'term', '输出'), ('n', 'flow', '对比'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。SQLite', '没有验证:validators 与 clean() 中 ValidationError 的 params 国际化、Model.clean() / clean_fields() 的调用顺序、CheckConstraint 的替代方案、DRF 序列化器里的校验器'],
)
