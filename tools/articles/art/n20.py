from lib import *
S = SS('n20')
steps = [
    step("ShouldBindBodyWith 的源码:先看 c.Keys 里有没有缓存的 body(BodyBytesKey = \"_gin-gonic/gin/bodybyteskey\"),没有就 io.ReadAll(c.Request.Body) 读完整个 body 并 c.Set 存起来,然后用 bb.BindBody(body, obj) 解析。以后再调用都从缓存里取,不再读 Request.Body。", t=tl(S(1)), mark=lidx(S(1), 'io.ReadAll(c.Request.Body)', 'c.Set(BodyBytesKey, body)'), done=lidx(S(1), 'c.Get(BodyBytesKey)', 'bb.BindBody(body, obj)', 'BodyBytesKey ='), kv=KV([['第一次', 'ReadAll,存进 c.Keys'], ['以后', '从缓存取,不再读 Body'], ['解析', 'bb.BindBody(缓存, obj)']], ['第一次'])),
    step("同一个 23 字节的 JSON 请求:连续两次 ShouldBindJSON,第二次 err=EOF、结构体是零值(Body 只能读一次);两次 ShouldBindBodyWith(JSON) 都成功,缓存了 23 字节(就是整个 body);同一份缓存再用 YAML 解析也成功(JSON 是 YAML 的子集);GetRawData 读完 body 之后再 ShouldBindJSON 同样是 EOF。", t=tl(S(2)), mark=lidx(S(2), 'err=EOF'), done=lidx(S(2), '缓存了 23 字节', 'YAML err=<nil>'), kv=KV([['ShouldBindJSON × 2', '第二次 EOF'], ['ShouldBindBodyWith × 2', '都成功,缓存 23 字节'], ['GetRawData 之后', '再 ShouldBindJSON → EOF']], ['ShouldBindJSON × 2'])),
    step("中间件先 io.ReadAll(c.Request.Body)(比如验签),handler 再 ShouldBindJSON:没有还原 Body 时 handler 的绑定 err=EOF;中间件读完后用 io.NopCloser(bytes.NewReader(b)) 把 Body 放回去,handler 就能正常绑定出 {Name:ann Age:30}。", t=tl(S(3)), mark=lidx(S(3), '中间件还原 Body=false'), done=lidx(S(3), '中间件还原 Body=true'), kv=KV([['不还原', 'handler 绑定 EOF'], ['还原', 'c.Request.Body = io.NopCloser(bytes.NewReader(b))'], ['替代', '全程用 ShouldBindBodyWith']], ['还原'])),
    step("代价:1.06 MB(20000 个对象)的 JSON 请求体,每请求的耗时与分配(7 轮中位数):ShouldBindJSON(流式解码)11.03 ms、11.91 MB;ShouldBindBodyWith(JSON)11.10 ms、14.16 MB;对照 ReadAll + json.Unmarshal 9.84 ms、11.91 MB。ShouldBindBodyWith 多分配约 2.25 MB(body 大小的 2 倍多),耗时几乎一样(第二轮 11.06 / 11.24 ms)。", t=tl(S(4)), mark=lidx(S(4), 'ShouldBindBodyWith(JSON)'), done=lidx(S(4), 'ShouldBindJSON(流式)', 'ReadAll + json.Unmarshal'), b=bars([['ShouldBindJSON:分配', 11.91, '11.91 MB'], ['ShouldBindBodyWith:分配', 14.16, '14.16 MB'], ['ReadAll + Unmarshal:分配', 11.91, '11.91 MB']], 14.16, done=[0, 2], mark=[1]), kv=KV([['多分配', '2.25 MB(body 1.06 MB 的 2 倍多)'], ['耗时', '11.03 vs 11.10 ms,几乎相同'], ['建议', '只有需要多次绑定时才用 BodyWith']], ['多分配'])),
]
A = mkartn('n20', 20, 'Gin,请求体,ShouldBindBodyWith,Body只能读一次,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测请求体只能读一次:连续两次 ShouldBindJSON 第二次 EOF;ShouldBindBodyWith 把整个 body 缓存进 c.Keys 之后可多次绑定;中间件读完 body 后必须还原;1 MB 的 JSON 上 ShouldBindBodyWith 多分配约 2.25 MB、耗时几乎不变。',
    '为什么在中间件里读了一次 body,handler 里的 ShouldBind 就报 EOF?ShouldBindBodyWith 又是怎么解决的、代价多大?这篇从源码到 1 MB 请求体的内存对比,把这件事讲清楚。',
    [('EOF', '同一个请求第二次 ShouldBindJSON 的错误'), ('23 字节', 'ShouldBindBodyWith 缓存到 c.Keys[BodyBytesKey] 的内容 = 整个 body'), ('+2.25 MB', '1.06 MB 的 JSON 请求体上 ShouldBindBodyWith 比 ShouldBindJSON 多分配的内存')],
    [('缓存的实现', '<p>请求体是一个只能读一次的流。<code>ShouldBindBodyWith</code> 的做法很直接:第一次把整个 body <code>ReadAll</code> 出来,存进 <code>c.Keys</code> 的一个固定 key,之后每次都用缓存解析。所以它也受 Keys 的生命周期约束:只在当前请求内有效。</p>'),
     ('哪些读法会让 Body 失效', '<p>任何读完 <code>Request.Body</code> 的操作都会让后面的 <code>ShouldBindJSON</code> 得到 EOF:再来一次 <code>ShouldBindJSON</code>、<code>GetRawData</code>、<code>io.ReadAll</code>。<code>ShouldBindBodyWith</code> 可以连续用不同格式解析同一份缓存(JSON 与 YAML 都成功,因为 JSON 是 YAML 的子集)。</p>'),
     ('中间件里读 body', '<p>验签、审计日志等中间件常要读 body。读完之后一定要把 <code>c.Request.Body</code> 换成一个新的 <code>io.NopCloser(bytes.NewReader(b))</code>;否则 handler 里的绑定拿到的就是 EOF。如果后面的所有绑定都用 <code>ShouldBindBodyWith</code>,就不需要手工还原。</p>'),
     ('代价', '<p>流式的 <code>ShouldBindJSON</code> 与 <code>ReadAll + Unmarshal</code> 的分配相同(11.91 MB),<code>ShouldBindBodyWith</code> 还要多留一份 body 并经过 <code>ReadAll</code> 的扩容,约多 2.25 MB。耗时几乎没有差别。所以它的成本主要是内存,请求体越大越明显;只绑定一次时不要用它。</p>')],
    steps,
    [ENV_N_GIN + '。前三节用 httptest 直接调用 ServeHTTP;第四节用 gin.CreateTestContext 与 testing.Benchmark,7 轮中位数,整个实验跑了两轮;JSON 编解码用 Gin 默认的 encoding/json;请求体 1057791 字节',
     '没有验证:真实网络里流式解码与先读完再解码的差别(这里 body 在内存里);其他 JSON 库(sonic、jsoniter、go-json)下的分配;MaxBytesReader 与 ShouldBindBodyWith 的组合;表单、multipart 请求(它们由 ParseForm 缓存,不受这个限制)'],
    'Body 只能读一次')
