from lib import *
R = J('d19')
O = R['orders'].splitlines(); lim = R['limit'].splitlines()
def pick(kind): return [l for l in O if l.startswith(f'[{kind}')]
steps = [
    step("表单体(urlencoded)先读 request.POST 再读 request.body:两个都成功,因为 Django 在解析 POST 前已经把体缓存进 _body;先读 body 再读 POST 同样成功。", t=tl(pick('urlencoded')[:2], cur=[0, 1]), kv=KV([['urlencoded', 'POST 与 body 谁先都可以']], ['urlencoded'])),
    step("但先用 request.read() 读了流,再取 request.body → RawPostDataException(You cannot access body after reading from request's data stream);先 read() 再取 request.POST → 不报错,却是空的 {}。这是静默失败。", t=tl(pick('urlencoded')[2:], mark=[0, 1]), kv=KV([['read() 之后', 'body 抛异常,POST 静默为空']], ['read() 之后'])),
    step("multipart 表单:先 POST 再 body → RawPostDataException(流已被解析消耗,没有缓存整体);先 body 再 POST 则两者都成功(POST 从缓存的 body 解析)。JSON 体:request.POST 永远是空,内容在 request.body 里。", t=tl(pick('multipart')[:2] + pick('json')[:2], cur=[1, 2, 3], mark=[0]), kv=KV([['multipart', '先 POST 再 body 会失败'], ['JSON', 'POST 为空,读 body']], ['multipart'])),
    step("PUT / PATCH 的表单体不会被解析成 request.POST:POST 有 {'a': ['1'], 'b': ['2']};同样的体用 PUT、PATCH 发,request.POST = {},内容只在 request.body 里(b'a=1&b=2')。", t=tl(R['put'].splitlines(), cur=[0], mark=[1, 2]), kv=KV([['PUT / PATCH', 'request.POST 为空']], ['PUT / PATCH'])),
    step("DATA_UPLOAD_MAX_MEMORY_SIZE 默认 2621440 字节(2.5 MiB):恰好这么大的体 → 200;多 1 字节 → RequestDataTooBig(视图里读取 request.body 时抛出,这里的探测视图把它转成了 400)。multipart 请求体整体超过 2.5 MiB 时,request.body 同样抛出——这是对 body 属性的限制,不等于 POST 解析对文件字段的限制(第 68、69 篇)。", t=tl(lim[:4], cur=[1], mark=[2, 3]), kv=KV([['默认上限', '2.5 MiB'], ['超过', 'RequestDataTooBig → 400']], ['默认上限'])),
    step("内部:读取前 request._stream 是 LimitedStream,还没有 _body;读取 body 后有 _body(缓存,第二次 request.body 是同一个对象),并且 _stream 换成了 BytesIO——所以之后 read() 还能读到数据。", t=tl(R['internals'].splitlines(), cur=[0, 1, 2, 3]), kv=KV([['body', '读一次并缓存']], ['body'])),
]
A = dict(
    n=19, series='django', tags='Django,HttpRequest,请求体,真实验证,动画演示',
    desc='实测 HttpRequest 的请求体:body / POST / read() 三种读取的先后顺序在 urlencoded、multipart、JSON 下各是什么结果(read() 之后 POST 会静默为空);PUT / PATCH 不解析 POST;DATA_UPLOAD_MAX_MEMORY_SIZE 默认 2.5 MiB 超过一字节即被拒。',
    lead='request.body、request.POST、request.read() 都在读同一个流,先读谁、读没读过,结果大不相同。这篇把 3 种内容类型 × 4 种读取顺序全部跑一遍,再看大小限制。',
    facts=[('静默为空', '先 request.read() 再取 request.POST,不报错但得到空 QueryDict'), ('multipart', '先 POST 再 body 会抛 RawPostDataException;先 body 再 POST 都成功'), ('2.5 MiB', 'DATA_UPLOAD_MAX_MEMORY_SIZE 默认值;超过一字节即 RequestDataTooBig')],
    body=[
        sec('读取顺序矩阵', '', term('', blk('d19', 1)), '<p>规律:<code>request.body</code> 会把整个体读进内存并缓存;<code>POST</code> 的解析在 urlencoded 时基于缓存的体,在 multipart 时直接消耗流。所以 multipart 的「先 POST 再 body」失败。一旦手动 <code>read()</code> 过,流就被消耗了:<code>body</code> 明确报错,而 <code>POST</code> 静默变空,后者更危险。</p>'),
        sec('PUT / PATCH', '', term('', blk('d19', 2)), '<p>Django 只对 <code>POST</code> 方法解析表单体。REST 风格的 PUT / PATCH 要自己解析 <code>request.body</code>(或用 DRF 之类的框架)。</p>'),
        sec('大小限制', '', term('', blk('d19', 3)), '<p><code>DATA_UPLOAD_MAX_MEMORY_SIZE</code> 限制「读进内存」的请求体:读取 <code>request.body</code> 时,体超过限制就抛 <code>RequestDataTooBig</code>(探测视图里我把它转成了 400)。multipart 请求整体超过限制时读 <code>body</code> 也一样;而 multipart 解析出的文件字段走另一套上传处理器与阈值(第 68、69 篇),这次没有单独测 <code>request.POST</code> / <code>request.FILES</code> 遇到大文件时的行为。</p>'),
        sec('内部状态', '', term('', blk('d19', 4)), '<p>读取 <code>body</code> 后 <code>_stream</code> 被换成 <code>BytesIO</code>,所以之后还能 <code>read()</code>;反过来则不行。</p>'),
        sec('分步演示:读取顺序', '', demo('请求体解析', [('t', 'term', '实测结果'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。用 RequestFactory 构造请求对象并调用属性(不经过 WSGI 服务器);大小限制用 Client 打真实视图', '没有验证:真实 WSGI 服务器(gunicorn)与 ASGI 下体的读取差别、Transfer-Encoding: chunked、Content-Length 与实际体长度不一致的情形、multipart 里文件字段超过内存上限时的落盘阈值(FILE_UPLOAD_MAX_MEMORY_SIZE,第 68 篇)'],
)
