from lib import *
R = J('d20')
steps = [
    step("QueryDict('a=1&a=2&b=x&tag=py&tag=django&tag=orm&empty=')。q['a'] 与 q.get('a') 取到的都是最后一个值 '2';q.getlist('a') = ['1', '2'];getlist('tag') 三个全在;getlist('missing') 是 [],get('missing') 是 None;空值 empty= 得到 ''。", t=tl(R['dups'].splitlines()[1:8], cur=[0, 1, 2, 3], mark=[0]), kv=KV([['重复参数', '下标 / get 取最后一个,getlist 取全部']], ['重复参数'])),
    step("dict(q) 得到的是 {'a': ['1','2'], …}(值是列表);q.dict() 才是 {'a': '2', …}(只留最后一个);list(q.items()) 也只给最后一个,list(q.lists()) 给全部。len(q) 是 key 的个数(4),不是参数个数(7)。", t=tl(R['dups'].splitlines()[8:13], cur=[3, 4], mark=[0, 1, 2]), kv=KV([['dict(q)', '值是列表'], ['q.dict()', '值是最后一个']], ['q.dict()'])),
    step("QueryDict 默认不可变:q['a'] = '3' → AttributeError: This QueryDict instance is immutable;要改先 q.copy()。copy 之后 appendlist、setlist 都可用,urlencode() 得到 a=3&a=4&b=x&b=y;中文和 & 会被正确编码解码。", t=tl(R['mutable'].splitlines(), cur=[1, 2, 3, 4], mark=[0]), kv=KV([['不可变', 'copy() 才能改']], ['不可变'])),
    step("在请求里:?ids=1&ids=2&ids=3 → request.GET.get('ids') = '3'、int(request.GET['ids']) = 3,只拿到最后一个;getlist('ids') = ['1','2','3']。POST 表单里同名字段同样。", t=tl(R['request'].splitlines(), cur=[0, 2], mark=[1]), kv=KV([['取多个值', '必须 getlist']], ['取多个值'])),
    step("DATA_UPLOAD_MAX_NUMBER_FIELDS 默认 1000:POST 表单 1000 个字段正常;1001 个 → TooManyFieldsSent;GET 查询串同样,1000 个正常、1001 个抛 TooManyFieldsSent。", t=tl(R['limit'].splitlines(), cur=[0, 2], mark=[1, 3]), kv=KV([['字段数上限', '1000'], ['超过', 'TooManyFieldsSent']], ['字段数上限'])),
]
A = dict(
    n=20, series='django', tags='Django,QueryDict,请求参数,真实验证,动画演示',
    desc='实测 QueryDict:重复参数下 q[key]、get、getlist、dict()、q.dict() 各返回什么;默认不可变、copy() 后才能改;GET / POST 里同样只有 getlist 能取全部;字段数上限 1000,超过一个即 TooManyFieldsSent。',
    lead='?ids=1&ids=2&ids=3 进了 request.GET 变成什么?为什么 int(request.GET["ids"]) 只拿到 3?这篇把 QueryDict 的每个取值方式都在同一组数据上跑一遍,再看字段数量限制。',
    facts=[('最后一个', 'q[key] / q.get(key) / q.dict() / q.items() 都只给最后一个值;q.getlist / q.lists() / dict(q) 给全部'), ('不可变', '请求里的 QueryDict 默认不可变,copy() 才能改'), ('1000', 'DATA_UPLOAD_MAX_NUMBER_FIELDS 默认值,GET 与 POST 超过一个都抛 TooManyFieldsSent')],
    body=[
        sec('重复参数怎么取', '', term('', blk('d20', 1)), '<p>QueryDict 是「一个 key 对应多个值」的字典:大部分接口(下标、<code>get</code>、<code>items</code>、<code>dict()</code> 方法)只返回最后一个,少数(<code>getlist</code>、<code>lists</code>、内置 <code>dict(q)</code>)返回全部。</p>'),
        sec('不可变与编码', '', term('', blk('d20', 2)), '<p><code>request.GET</code> / <code>request.POST</code> 是不可变的;构造新的查询串用 <code>copy()</code> + <code>urlencode()</code>,中文与保留字符自动编码。</p>'),
        sec('在请求里', '', term('', blk('d20', 3)), '<p>多选框、多个同名参数,一定要用 <code>getlist</code>。JSON 请求体里没有「重复 key」这回事,那是解析后的数组。</p>'),
        sec('字段数上限', '', term('', blk('d20', 4)), '<p>GET 查询串也受限制(实验里是在访问 <code>len(request.GET)</code> 时抛出)。1000 个刚好通过,1001 个抛 <code>TooManyFieldsSent</code>。</p>'),
        sec('分步演示:QueryDict 的取值', '', demo('QueryDict', [('t', 'term', '实测输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。请求由 RequestFactory 构造', '没有验证:超大单个参数值的限制、非 UTF-8 编码的查询串(DEFAULT_CHARSET 与 request.encoding)、QueryDict 在 multipart 下与文件字段并存时的行为、第一次访问 request.GET 时才抛 TooManyFieldsSent 这一说法只按代码路径推断(实验里是在访问 len() 时触发)'],
)
