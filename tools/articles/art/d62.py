from lib import *
R = J('d62')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("构造 Form 时什么都不做(LOG 为空),cleaned_data 属性也还不存在;errors 也是惰性的——直到调用 is_valid()(或访问 errors)才开始校验。", t=tl(L('order')[:3], cur=[0, 1, 2]), kv=KV([['构造', '不校验'], ['惰性', 'is_valid() / errors 才触发']], ['惰性'])),
    step("is_valid() 内部按字段声明顺序逐个处理:每个字段依次 to_python → validate → run_validators,紧接着调用该字段的 clean_<字段名>();所有字段处理完之后是表单级 clean(),此时 cleaned_data 里已有 a、b;最后是 _post_clean()(ModelForm 在这里做模型校验)。", t=tl([l for l in L('order') if l.startswith('  ')], cur=[0, 1, 2, 3], mark=[8, 9]), kv=KV([['字段级', 'to_python → validate → run_validators → clean_字段'], ['表单级', 'clean() → _post_clean()']], ['表单级'])),
    step("字段 a 校验失败(0 < min_value 1):它的 clean_a() 被跳过,cleaned_data 里没有 a,表单级 clean() 看到的键只有 ['b']——所以 clean() 里直接写 self.cleaned_data['a'] 会 KeyError,要用 .get()。b 不受影响,继续处理。错误:code = min_value。", t=tl([l for l in L('fail') if l.startswith('  ') or l.startswith('errors') or l.startswith('cleaned')]), kv=KV([['字段失败', 'clean_<field> 被跳过'], ['clean()', '拿不到失败的字段']], ['clean()'])),
    step("表单级错误:在 clean() 里 raise ValidationError('a 不能大于 b', code='order') 得到 non_field_errors;两个字段都失败时(a='x'、b='')错误按字段声明顺序:a: invalid、b: required。", t=tl(L('nonfield')), kv=KV([['non_field_errors', '表单级错误'], ['错误顺序', '字段声明顺序']], ['non_field_errors'])),
    step("其它:未绑定表单 is_valid() 永远 False、errors 为空;多余的提交字段(zzz)不会进入 cleaned_data;disabled 字段忽略提交的值、使用 initial(提交 99、cleaned_data 是 1);has_changed() 比较提交值与 initial。", t=tl(L('misc')), kv=KV([['disabled', '忽略提交值'], ['多余字段', '被忽略']], ['disabled'])),
]
A = dict(
    n=62, series='django', tags='Django,Form,表单校验,真实验证,动画演示',
    desc='用带日志的字段与表单实测 Form 完整校验流程:构造时不校验;is_valid() 触发;每个字段 to_python → validate → run_validators → clean_<field>;再表单级 clean() 与 _post_clean();字段失败时 clean_<field> 被跳过、cleaned_data 缺该键;disabled 与多余字段的处理。',
    lead='form.is_valid() 到底做了什么、按什么顺序?一个字段失败了,后面的钩子还执行吗?这篇给每个环节打点,把完整的校验流程按调用顺序排出来。',
    facts=[('惰性', '构造 Form 不校验;is_valid() / errors 才开始'), ('顺序', '每个字段:to_python → validate → run_validators → clean_<字段>;然后 clean() → _post_clean()'), ('缺键', '字段失败后 cleaned_data 里没有它,表单级 clean() 要用 .get()')],
    body=[
        sec('校验的触发', '', term('', blk('d62', 1)), '<p><code>is_valid()</code> 就是「<code>is_bound</code> 且 <code>errors</code> 为空」;<code>errors</code> 第一次访问时调用 <code>full_clean()</code>。</p>'),
        sec('字段失败之后', '', term('', blk('d62', 2)), '<p>字段自己的三个阶段任一失败就不再执行它的 <code>clean_&lt;field&gt;</code>。注意 Django 仍会继续处理其他字段,并且仍会调用表单级 <code>clean()</code>——所以 <code>clean()</code> 必须容忍字段缺失(本站另一篇《Forms 校验流水线》用真实的 KeyError 演示过这一点)。</p>'),
        sec('表单级错误与顺序', '', term('', blk('d62', 3)), '<p><code>ValidationError</code> 的 <code>code</code> 是给程序判断用的,<code>message</code> 是给人看的;需要给具体字段加错误用 <code>self.add_error(\'a\', ...)</code>(本文没有测)。</p>'),
        sec('几个细节', '', term('', blk('d62', 4)), '<p>未绑定表单(没有数据)<code>is_valid()</code> 永远是 <code>False</code>,<code>errors</code> 为空。请求里多余的字段被忽略。<code>disabled=True</code> 的字段用 <code>initial</code>,忽略用户提交的值,是防止篡改只读字段的正确做法(比只在前端 <code>readonly</code> 可靠)。</p>'),
        sec('分步演示:校验流程', '', demo('Form 校验流程', [('t', 'term', '调用日志'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。字段与表单的方法里加了日志打点', '没有验证:add_error 与 clean() 的组合、field 的 error_messages 覆盖、FileField / ChoiceField 的特殊路径、Form 的 field_order 对校验顺序的影响、异步视图里的表单使用'],
)
