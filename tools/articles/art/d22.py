from lib import *
R = J('d22'); tt = R['ttfb']; bg = R['big']; bb = bg['big_buffered']; bs = bg['big_streaming']
steps = [
    step(f"5 段内容,每段之间服务端睡 0.3 s(gunicorn 同步 worker)。HttpResponse:要等全部生成完才发,首字节 {tt['buffered']['first_ms']:.0f} ms,带 Content-Length: {tt['buffered']['headers']['Content-Length']}。", b=bars([['HttpResponse 首字节(ms)', tt['buffered']['first_ms'], f"{tt['buffered']['first_ms']:.0f}"], ['收完(ms)', tt['buffered']['total_ms'], f"{tt['buffered']['total_ms']:.0f}"]], tt['buffered']['total_ms'] * 1.1, mark=[0]), kv=KV([['Content-Length', tt['buffered']['headers']['Content-Length']]], ['Content-Length'])),
    step(f"StreamingHttpResponse:每段一出来就发出去,首字节 {tt['streaming']['first_ms']:.0f} ms(≈ 第一段的生成时间),整体收完仍是 {tt['streaming']['total_ms']:.0f} ms;响应没有 Content-Length,用 Transfer-Encoding: chunked。", b=bars([['Streaming 首字节(ms)', tt['streaming']['first_ms'], f"{tt['streaming']['first_ms']:.0f}"], ['收完(ms)', tt['streaming']['total_ms'], f"{tt['streaming']['total_ms']:.0f}"]], tt['buffered']['total_ms'] * 1.1, done=[0]), kv=KV([['Transfer-Encoding', 'chunked'], ['Content-Length', '无']], ['Transfer-Encoding'])),
    step("StreamingHttpResponse 对象:streaming = True;读 r.content → AttributeError(This StreamingHttpResponse instance has no `content` attribute. Use `streaming_content` instead.);没有 Content-Length 头。", t=tl(R['attrs'].splitlines(), cur=[0], mark=[1, 2]), kv=KV([['没有 .content', '只能迭代 streaming_content']], ['没有 .content'])),
    step(f"200 MiB 的响应:一次性 HttpResponse 时 worker 从 {bb['base']:.0f} MiB 涨到峰值约 {bb['peak_mb']:.0f} MiB(整个体都在内存里);用生成器(每次 1 MiB)流式发送,峰值只有约 {bs['peak_mb']:.0f} MiB。", b=bars([['HttpResponse 峰值 RSS(MiB)', bb['peak_mb'], f"{bb['peak_mb']:.0f}"], ['Streaming 峰值 RSS(MiB)', bs['peak_mb'], f"{bs['peak_mb']:.0f}"], ['起始 RSS(MiB)', bb['base'], f"{bb['base']:.0f}"]], bb['peak_mb'] * 1.1, mark=[0], done=[1]), kv=KV([['内存', f"{bb['peak_mb']:.0f} vs {bs['peak_mb']:.0f} MiB"]], ['内存'])),
]
A = dict(
    n=22, series='django', tags='Django,StreamingHttpResponse,流式响应,真实验证,动画演示',
    desc=f'在 gunicorn 上实测 StreamingHttpResponse:同样 5 段、每段 0.3 s,HttpResponse 首字节 {tt["buffered"]["first_ms"]:.0f} ms,流式 {tt["streaming"]["first_ms"]:.0f} ms;200 MiB 响应的 worker 峰值内存 {bb["peak_mb"]:.0f} MiB vs {bs["peak_mb"]:.0f} MiB;流式响应没有 .content 也没有 Content-Length。',
    lead='StreamingHttpResponse 是「边生成边发」还是「只是换了个写法」?这篇在真实的 gunicorn 上量首字节时间和大响应的内存占用,再看它跟普通响应在属性上的不同。',
    facts=[(f'{tt["buffered"]["first_ms"]:.0f} → {tt["streaming"]["first_ms"]:.0f} ms', '5 段、每段 0.3 s 的响应,HttpResponse → StreamingHttpResponse 的首字节时间'), (f'{bb["peak_mb"]:.0f} vs {bs["peak_mb"]:.0f} MiB', '200 MiB 响应时 gunicorn worker 的峰值内存:一次性 vs 生成器流式'), ('chunked', '流式响应没有 Content-Length,用 Transfer-Encoding: chunked')],
    body=[
        sec('首字节时间', '', term('', blk('d22', 1)), '<p>gunicorn 同步 worker,一个 worker。客户端用 <code>read1</code> 读取,记录第一个字节到达的时刻(用 <code>read(n)</code> 会因为凑不够 n 字节而被自己拖慢,这是我第一次量时踩的坑)。总耗时都是 ≈1.5 s——流式改变的是「用户什么时候开始看到内容」,不是总时间。</p>'),
        sec('对象的差别', '', term('', blk('d22', 2)), '<p>流式响应没有 <code>.content</code>,只能迭代 <code>streaming_content</code>;中间件里如果读 <code>response.content</code> 就会炸,所以对流式响应要判断 <code>response.streaming</code>。</p>'),
        sec('内存', '', term('', blk('d22', 3)), '<p>每种方式都用全新的 worker 进程测(RSS 在释放后不一定回落,共用一个进程会污染下一次测量——我第一次就这样量错了)。流式方式内存基本不涨。</p>'),
        sec('什么时候用', '', '<p>大文件下载、导出、服务端事件推送。注意:压缩(GZipMiddleware)对流式响应的处理、反向代理是否会缓冲(nginx 的 <code>proxy_buffering</code>)都会影响「首字节」效果,这两点本文没有测。同步 worker 下,一个慢的流式响应会占住整个 worker(本文只用了 1 个 worker)。</p>'),
        sec('分步演示:首字节与内存', '', demo('StreamingHttpResponse', [('b', 'bars', '数据'), ('t', 'term', '对象属性'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_D + '。gunicorn 26.2 同步 worker ×1;内存每 20 ms 用 ps 采样 worker 进程 RSS', '没有验证:多 worker / gthread、uvicorn(ASGI)下的流式行为、反向代理缓冲、GZipMiddleware 与流式的交互、客户端中途断开时服务端生成器是否被及时关闭'],
)
