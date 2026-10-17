from lib import *
S = SS('f107')
R = J('f107'); sq = R['seq']; rc = R['race']
nv, at = rc['朴素:先查,没有再写'], rc['原子:先 INSERT key 占位']
steps = [
    step(f"没有幂等键:服务端处理要 1 秒,客户端 0.3 秒就超时(TimeoutError)并重试,重试得到 201;但第一次请求服务端其实继续处理完了,库里有 {R['plain']} 个订单,而用户只下了一单。网络超时重试会让 POST 重复创建。", t=tl(S(1)), mark=lidx(S(1), '库里有'), done=lidx(S(1), '重试'), kv=KV([['超时后重试', '第一次其实成功了'], ['结果', f"{R['plain']} 个订单"]], ['结果'])),
    step(f"带 Idempotency-Key 顺序重试:第一次 201 {{id: 1}}(耗时 {sq[5]:.0f} ms,包含处理时间),第二次同一个 key 直接返回同样的 201 {{id: 1}} 并带 Idempotent-Replayed: true(耗时 {sq[6]:.0f} ms,没有重新处理),库里只有 {R['seq_count']} 个订单。同一个 key 换了请求体 → 422「Idempotency-Key reused with a different request body」(用请求体的 sha256 指纹比对);不带 key → 400。", b=bars([['第一次(处理)', sq[5], f'{sq[5]:.0f} ms'], ['重放', max(sq[6], 0.5), f'{sq[6]:.0f} ms']], sq[5], mark=[0], done=[1]), t=tl(S(2)), done=lidx(S(2), '第一次', '第二次'), mark=lidx(S(2), '换了请求体', '不带 key'), kv=KV([['同 key 同请求', '返回已保存的结果,不重复处理'], ['同 key 不同请求', '422'], ['没带 key', '400']], ['同 key 同请求'])),
    step(f"并发的重复请求(同一个 key 同时发 6 个):「先查有没有,没有再写」的朴素实现状态码分布 {nv[0]},库里 {nv[1]} 个订单——6 个请求都在写入记录之前查询,全都放行;「先 INSERT key 占位(ON CONFLICT DO NOTHING)」的原子实现 {at[0]},库里 {at[1]} 个订单——只有抢到占位的那个处理,其余返回 409「request in progress」(调用方稍后重试会拿到保存的结果)。检查和占位必须是同一个原子操作。", b=bars([['朴素实现 订单数', nv[1], str(nv[1])], ['原子实现 订单数', at[1], str(at[1])]], 6, mark=[0], done=[1]), t=tl(S(3)), mark=lidx(S(3), '朴素'), done=lidx(S(3), '原子'), kv=KV([['先查再写', '并发下全部放行'], ['先占位', '数据库唯一约束保证只有一个']], ['先占位'])),
]
A = mkartf('f107', 107, 'Flask,API,幂等,Idempotency-Key,并发,真实验证,动画演示',
    f'在真实的 PostgreSQL 与 gunicorn 上实测 Idempotency-Key:没有 key 时超时重试造成 {R["plain"]} 个订单、有 key 时重放返回同一结果(Idempotent-Replayed)、同 key 不同请求体 422、并发 6 个相同请求时「先查再写」写入 {nv[1]} 个而「先占位」只写 {at[1]} 个。',
    '网络超时重试会不会重复下单?Idempotency-Key 怎么实现?并发的重复请求怎么挡?这篇用真实的超时重试与 6 个并发请求,把朴素实现和原子实现的差别量出来。',
    [(f'{R["plain"]} 个订单', '没有幂等键,超时重试后库里的订单数(用户只下了一单)'), (f'{nv[1]} → {at[1]}', '6 个并发的相同请求:朴素实现与先占位实现写入的订单数'), ('409 / 422', '请求处理中与同 key 不同请求体时的状态码')],
    [('超时重试', '<p>上一篇:<a href="flask-restful-url-design.html">RESTful URL 设计</a>;下一篇:<a href="flask-api-token-auth.html">API Token 认证</a>。</p>'), ('顺序重试', None), ('并发重复请求', '<p>6 个线程同时发出相同 key 的请求,服务端处理时间 0.5 秒来放大竞争窗口。</p>')],
    steps, [ENV_F + '。Flask-SQLAlchemy 3.1.1、psycopg 3.3.6、自己起的 PostgreSQL(非默认端口)、gunicorn gthread', '没有验证:key 的过期清理(TTL)、处理中途进程崩溃留下 processing 记录的恢复、把 key 存在 redis 里的实现、保存的响应里的头与状态码的完整重放、IETF Idempotency-Key 草案的全部细节'], 'Idempotency-Key', panels=[('t', 'term', '实验输出'), ('b', 'bars', '耗时 / 订单数'), ('kv', 'kv', '要点')])
