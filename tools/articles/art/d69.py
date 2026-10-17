from lib import *
R = J('d69')
def L(k): return [l for l in R[k].splitlines() if l.strip()]
steps = [
    step("Django 没有「单个文件最大多少」的设置:1 MiB、5 MiB、30 MiB 的上传默认全都被接受(status 200),文件完整收下。", t=tl(L('nolimit'), done=[0, 1, 2]), kv=KV([['默认', '没有文件大小上限']], ['默认'])),
    step("自己在表单里限制(clean_f 里检查 f.size):500 KiB、1024 KiB 通过;1025 KiB、5000 KiB → too_big。但要注意:检查发生在文件已经被完整接收(并写进临时文件)之后——它防的是「存储」,防不了「占带宽和临时磁盘」。", t=tl(L('form'), done=[0, 1], mark=[2, 3]), kv=KV([['表单校验', '文件已收完才检查']], ['表单校验'])),
    step("DATA_UPLOAD_MAX_MEMORY_SIZE(默认 2621440)不计 multipart 里的文件字段:10 MiB 文件上传 status 200;但一个 3 MiB 的普通表单字段(非文件)→ 400 RequestDataTooBig。", t=tl(L('datalimit')), kv=KV([['DATA_UPLOAD_MAX_MEMORY_SIZE', '限制的是非文件数据']], ['DATA_UPLOAD_MAX_MEMORY_SIZE'])),
    step("DATA_UPLOAD_MAX_NUMBER_FILES(默认 100):同一个请求上传 100 个文件 → 200;101 个 → 400 TooManyFilesSent。", t=tl(L('nfiles')), kv=KV([['文件个数', '默认最多 100']], ['文件个数'])),
    step("所以真正的大小上限要放在更前面:反向代理(比如 nginx 的 client_max_body_size,本文没有测)在请求到达 Django 之前就拒绝;应用层再用表单校验兜底。仅靠 Django 无法阻止有人往你的临时目录里塞满大文件。", kv=KV([['上限的位置', '代理层 + 表单校验']], ['上限的位置'])),
]
A = dict(
    n=69, series='django', tags='Django,文件上传,大小限制,真实验证,动画演示',
    desc='实测 Django 的上传大小限制:没有单文件上限(30 MiB 也接受);表单里检查 file.size 发生在文件收完之后;DATA_UPLOAD_MAX_MEMORY_SIZE 不计文件字段(10 MiB 文件通过、3 MiB 普通字段被拒);DATA_UPLOAD_MAX_NUMBER_FILES 默认 100,101 个抛 TooManyFilesSent。',
    lead='想限制用户上传文件的大小,该配哪个设置?这篇把三个相关设置(FILE_UPLOAD_MAX_MEMORY_SIZE、DATA_UPLOAD_MAX_MEMORY_SIZE、DATA_UPLOAD_MAX_NUMBER_FILES)和表单校验各自管什么试出来。',
    facts=[('没有上限', 'Django 没有内置的单文件大小上限,30 MiB 默认被接受'), ('收完才检查', '表单里检查 f.size 时文件已经完整上传并落盘'), ('100', 'DATA_UPLOAD_MAX_NUMBER_FILES 默认值;101 个文件抛 TooManyFilesSent')],
    body=[
        sec('没有上限', '', term('', blk('d69', 1)), '<p>常见误解:<code>DATA_UPLOAD_MAX_MEMORY_SIZE</code> 或 <code>FILE_UPLOAD_MAX_MEMORY_SIZE</code> 是文件大小上限。都不是(见下)。</p>'),
        sec('表单校验', '', term('', blk('d69', 2)), '<p>在 <code>clean_&lt;field&gt;</code> 或校验器里检查 <code>size</code>,给用户友好提示。想在收完之前就拒绝,要看请求头 <code>Content-Length</code>(可伪造,本文没有做)或在代理层限制。</p>'),
        sec('三个设置各管什么', '', term('', blk('d69', 3)), term('', blk('d69', 4)), '<p><code>FILE_UPLOAD_MAX_MEMORY_SIZE</code>:文件留内存还是落盘(第 68 篇);<code>DATA_UPLOAD_MAX_MEMORY_SIZE</code>:非文件请求数据读进内存的上限;<code>DATA_UPLOAD_MAX_NUMBER_FILES</code>:一次请求最多几个文件。</p>'),
        sec('分步演示:上传限制', '', demo('上传大小限制', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。用 django.test.Client 上传(不经过真实 WSGI 服务器)', '没有验证:反向代理层的限制、Content-Length 预检、chunked 上传、DATA_UPLOAD_MAX_NUMBER_FIELDS 对文件上传的影响、TooManyFilesSent 最终的 HTTP 状态码(实验里视图自己转成了 400)'],
)
