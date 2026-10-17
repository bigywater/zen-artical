from lib import *
R = J('d21')
steps = [
    step("最普通的 HttpResponse('hello') 经过 CommonMiddleware 后带两个响应头:Content-Type: text/html; charset=utf-8、Content-Length: 5。charset 默认 utf-8。", t=tl(R['plain'].splitlines(), cur=[1, 2, 3]), kv=KV([['默认', 'text/html; charset=utf-8']], ['默认'])),
    step("响应头名字大小写不敏感:先 resp['X-Custom'] = 'a' 再 resp['x-custom'] = 'b',只留一个,值是 b,且名字以最后一次赋值的写法(x-custom)保存;resp['x-CUSTOM'] 也能读到 b。resp.headers['X-Other'] 与下标赋值等价。set_cookie 产生的是 Set-Cookie 头,带 HttpOnly、Max-Age、Path、SameSite。", t=tl(R['hdr'].splitlines(), cur=[0, 1, 3], mark=[2]), kv=KV([['响应头', '大小写不敏感,后写覆盖前写']], ['响应头'])),
    step("JsonResponse 用 DjangoJSONEncoder:datetime 变 ISO 字符串、Decimal 变字符串 '9.90'、UUID 变字符串。传入非 dict(列表)要加 safe=False,否则 TypeError;不可序列化的对象(set)直接 TypeError。", t=tl(R['json'].splitlines(), cur=[0, 1, 2], mark=[3, 4]), kv=KV([['Content-Type', 'application/json'], ['非 dict', '需要 safe=False']], ['非 dict'])),
    step("响应头注入:往头部值里塞 \\r\\n(想借机注入 Set-Cookie)被 Django 拦下,抛 BadHeaderError: Header values can't contain newlines。", n=fl([["resp['X-Evil'] = 'a\\r\\nSet-Cookie: …'", 'BadHeaderError']], mark=[0]), t=tl(R['inject'].splitlines(), mark=[0]), kv=KV([['换行', '被拒绝']], ['换行'])),
    step("Content-Length 是谁加的?不带中间件时响应头只有 Content-Type;是 CommonMiddleware 在响应阶段补上了 Content-Length(带它时是 5)。", t=tl(['带 CommonMiddleware:Content-Length: 5', R['nocommon']], cur=[0], mark=[1]), kv=KV([['Content-Length', 'CommonMiddleware 补的']], ['Content-Length'])),
]
A = dict(
    n=21, series='django', tags='Django,HttpResponse,JsonResponse,真实验证,动画演示',
    desc='实测 HttpResponse / JsonResponse:默认头与 charset;响应头大小写不敏感且后写覆盖;JsonResponse 对 datetime / Decimal / UUID 的编码与 safe=False 的含义;响应头里的换行会被 BadHeaderError 拒绝;Content-Length 由 CommonMiddleware 补上。',
    lead='视图返回的 HttpResponse 到底带哪些头?JsonResponse 会怎么序列化 datetime、Decimal?头部能不能被注入换行?这篇不看文档,把这些行为一条条试出来。',
    facts=[('BadHeaderError', '响应头的值里带 \\r\\n 会被拒绝,不能借此注入 Set-Cookie'), ('safe=False', 'JsonResponse 传列表必须 safe=False;datetime / Decimal / UUID 会被编码成字符串'), ('Content-Length', '不带 CommonMiddleware 时响应里没有 Content-Length')],
    body=[
        sec('默认响应头', '', term('', blk('d21', 1)), '<p>视图只返回 <code>HttpResponse(\'hello\')</code>,得到的 <code>Content-Type</code> 带 charset。<code>Content-Length</code> 不是 <code>HttpResponse</code> 自己算的(见第五节)。</p>'),
        sec('响应头与 Cookie', '', term('', blk('d21', 2)), '<p><code>response.headers</code> 是大小写不敏感的字典;重复赋值以最后一次为准。Cookie 通过 <code>set_cookie</code> 写入 <code>Set-Cookie</code> 头,可以直接指定 <code>httponly</code>、<code>samesite</code>、<code>max_age</code>。</p>'),
        sec('JsonResponse', '', term('', blk('d21', 3)), '<p>默认序列化器是 <code>DjangoJSONEncoder</code>,认识 datetime、Decimal、UUID 等;它不认识 <code>set</code>。<code>safe=True</code>(默认)只允许 dict 作为顶层,列表要显式 <code>safe=False</code>——这是历史上防 JSON 劫持的保守选择(这一条来自文档说法,本文没有验证其安全性)。</p>'),
        sec('头部注入', '', term('', blk('d21', 4)), '<p>值里带换行会立刻抛 <code>BadHeaderError</code>,而不是等到发送时。</p>'),
        sec('Content-Length', '', term('', blk('d21', 5)), '<p>响应阶段由 <code>CommonMiddleware</code> 加上。流式响应没有它(第 22 篇)。</p>'),
        sec('分步演示:响应头', '', demo('HttpResponse', [('t', 'term', '实测输出'), ('n', 'flow', '过程'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。用 django.test.Client 读取响应', '没有验证:真实 WSGI 服务器对头部的二次处理、GZipMiddleware 对 Content-Length 的影响、Cookie 的 secure / domain 属性、headers 里非 ASCII 值的编码'],
)
