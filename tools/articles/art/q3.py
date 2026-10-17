from lib import *
S = SS('q3')
steps = [
    step("不声明任何 exchange、不建任何 binding,直接往名字为空串的 exchange 发一条 routing key = hello 的消息,list_queues 显示队列 hello 里有 1 条,basic_get 取到 'hi'。list_bindings 里有一行:source_name 为空串(就是默认 exchange)、destination 是 hello、routing key 也是 hello——这一行不是我建的,队列一声明 broker 就自动加上。", t=tl(S(1)), mark=lidx(S(1), 'hello\t1', 'list_bindings 里的第一列'), done=lidx(S(1), 'basic_get', '\thello\thello'), kv=KV([['默认 exchange', '名字是空串,direct 类型'], ['绑定', '每个队列自动绑上,key = 队列名'], ['不用声明', '没有 exchange 声明、没有 bind']], ['默认 exchange'])),
    step("routing key 写了一个不存在的队列名:不加 mandatory 时发布没有任何错误,消息就是没有地方可去,悄悄丢弃;加上 mandatory=True 并开启 publisher confirm 后,pika 抛 UnroutableError: 1 unroutable message(s) returned,才知道没送到;对存在的队列 mandatory=True 正常成功。(mandatory 与 return 的细节见本系列专门一篇。)", t=tl(S(2)), mark=lidx(S(2), 'UnroutableError', '不加 mandatory'), done=lidx(S(2), '对存在的队列'), kv=KV([['队列名写错', '默认丢弃,发布方不知道'], ['mandatory + confirm', '得到 UnroutableError'], ['存在的队列', '正常成功']], ['队列名写错'])),
    step("默认 exchange 被保护:删它、往它上面 bind 或 unbind、用 fanout 重新声明它,都是 403 ACCESS_REFUSED,消息 operation not permitted on the default exchange;自己声明名字以 amq. 开头的 exchange 也是 403(reserved prefix)。管理 API 里它叫 amq.default,type direct、durable 为 true、internal 为 false。", t=tl(S(3)), mark=lidx(S(3), 'exchange_delete', 'queue_bind', 'queue_unbind', 'exchange_declare(\"\"', 'amq.foo'), done=lidx(S(3), '管理 API'), kv=KV([['删除 / 绑定 / 解绑 / 重新声明', '全部 403 ACCESS_REFUSED'], ['amq. 前缀', '保留给系统,不能自己声明'], ['管理 API 中的名字', 'amq.default']], ['删除 / 绑定 / 解绑 / 重新声明'])),
    step("队列名的细节:不给名字(空串)时 broker 生成 amq.gen-… 的名字(共 30 个字符),用这个名字当 routing key 照样能经默认 exchange 投到;a.b.c、带空格、中文、大写字母的队列名都能用;255 字节的名字声明成功,256 字节的名字在客户端就被 pika 拒绝(ShortStringTooLong,AMQP 的短字符串上限 255 字节,routing key 同理)。队列删掉后 list_bindings 里它的默认绑定也一并消失(a.b.c 删除前 True,删除后 False)。", t=tl(S(4)), mark=lidx(S(4), '255 字节的名字', '256 字节的名字', 'routing key 256 字节'), done=lidx(S(4), 'amq.gen-', 'a.b.c', 'with space', '中文队列', 'UPPER', '删除队列前'), kv=KV([['空队列名', 'broker 生成 amq.gen-…'], ['名字上限', '255 字节(短字符串)'], ['删除队列', '默认绑定随之消失']], ['名字上限'])),
    step("速度:各发 20000 条 100 字节的消息(不开 confirm),默认 exchange 和一个显式 direct exchange(绑了同一个队列)交替跑 7 轮取中位数:默认 exchange 中位数 545 ms(最小 532、最大 672),显式 direct exchange 中位数 536 ms(最小 530、最大 685),差别小于轮与轮之间的波动——默认 exchange 只是省了你声明和绑定的步骤,并不是更快的路径。", t=tl(S(5)), mark=lidx(S(5), '默认 exchange:'), done=lidx(S(5), '默认 exchange:'), b=bars([['默认 exchange', 545, '545 ms'], ['显式 direct', 536, '536 ms']], 545, mark=[0], done=[1]), kv=KV([['默认 exchange', '中位数 545 ms'], ['显式 direct', '中位数 536 ms'], ['结论', '差别小于轮间波动']], ['结论'])),
]
A = mkartq('q3', 3, 'RabbitMQ,默认exchange,routing key,队列名,真实验证,动画演示',
    '在 RabbitMQ 4.3.6 上看默认 exchange:空串名字、每个队列自动绑上 key=队列名的绑定;写错队列名消息被丢弃,mandatory + confirm 才有 UnroutableError;它不能被删、绑、重新声明(403);队列名上限 255 字节;20000 条消息走默认 exchange(中位数 545 ms)与显式 direct(536 ms)没有可测的差别。',
    '教程里“直接往队列发消息”其实是发给一个名字为空的 exchange。它是什么、有哪些限制、写错队列名会怎样、会比显式 exchange 更快吗?这篇一项项在 RabbitMQ 4.3.6 上验证。',
    [('403', '对默认 exchange 做删除、绑定、解绑、重新声明,全部是 ACCESS_REFUSED'), ('255 字节', '队列名与 routing key 的长度上限(AMQP 短字符串)'), ('545 vs 536 ms', '20000 条消息走默认 exchange 与显式 direct exchange 的耗时中位数,差别小于波动')],
    [('它是什么', '<p>默认 exchange 的名字是空串,direct 类型。每个队列声明时 broker 自动给它加一个以队列名为 key 的绑定,所以 <code>basic_publish(exchange=\'\', routing_key=队列名)</code> 就等于“直接发到这个队列”。这个绑定在 <code>list_bindings</code> 里能看到,删除队列时跟着消失。</p>'),
     ('发给不存在的队列', '<p>routing key 对不上任何队列时,消息被悄悄丢弃,发布方没有错误。要得到反馈需要 <code>mandatory</code> 加 publisher confirm(得到 UnroutableError)。</p>'),
     ('被保护', '<p>不能删除、绑定、解绑或重新声明默认 exchange(403 ACCESS_REFUSED);自己声明的 exchange 名字也不能以 <code>amq.</code> 开头。管理 API 里默认 exchange 的名字是 <code>amq.default</code>。</p>'),
     ('队列名', '<p>空队列名由 broker 生成 <code>amq.gen-…</code>;中文、空格、大写都可以;名字和 routing key 都是 AMQP 短字符串,上限 255 字节,超出时 pika 在客户端就拒绝。</p>'),
     ('性能', '<p>20000 条消息走默认 exchange 与走显式 direct exchange 耗时一样(中位数 545 ms 与 536 ms,轮间波动更大)。默认 exchange 的好处是少两步声明,不是更快。</p>')],
    steps,
    [ENV_Q + '。mandatory 的实验开了 confirm_delivery;速度对比不开 confirm,两种方式交替跑 7 轮,每轮 purge 后重发,最后一次 queue_declare(passive) 往返确保 broker 处理完',
     '没有验证:集群里队列在别的节点时默认 exchange 的转发;quorum 队列和 stream 队列通过默认 exchange 的行为(第 15、17 篇会涉及队列类型);非 ASCII 队列名的编码边界(UTF-8 字节数);vhost 隔离下的默认 exchange;消息体更大时的速度差异'],
    '默认 exchange')
