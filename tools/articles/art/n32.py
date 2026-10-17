from lib import *
S = SS('n32')
steps = [
    step("缺失的字段保持绑定前的值,所以可以预填默认值:预填 Page=1 Size=20 Sort=id Tag=预填标签 后,JSON {} → 全部保持;{\"page\":3} 只改 Page;{\"page\":0,\"sort\":\"\"} 把 Page 改成 0、Sort 改成空串(传了就覆盖,哪怕是零值);null 对非指针字段是空操作(Page=1 Size=20 Sort=id 不变),对指针 Tag 则设为 nil;未知字段忽略。查询串同理:?page=0&sort= 覆盖,?page=&size= 把 Page 与 Size 改成 0。", t=tl(S(1)), mark=lidx(S(1), '{"page":0,"sort":""}', '{"page":null', '/x?page=0&sort=', '/x?page=&size='), done=lidx(S(1), 'JSON {}  ', '{"page":3}', '{"unknown":1}', '/x   '), kv=KV([['缺失', '保持预填值'], ['传了零值', '覆盖成零值'], ['null', '非指针:不变;指针:设为 nil']], ['传了零值'])),
    step("预填的复合值遵循 encoding/json 的规则:预填的 map 合并(M={keep:1 over:2} 加上 {over:22,new:3} → {keep:1 new:3 over:22});切片整体替换([9 9 9 9] → [1 2]);数组短于预填时多出的位置清零([7 7 7] → [1 0 0]);嵌套结构体逐字段合并(In 的 A 改成 50,B 仍是 6);非 nil 指针原地改写——P 指向的是一个共享的 *Sub,请求之后共享的值被改成 {A:100 B:999},“同一个 *Sub 被改写:true”;null 会把 map、切片、指针置为 nil。", t=tl(S(2)), mark=lidx(S(2), 'M=map[keep:1 new:3 over:22]', '同一个 *Sub 被改写:true err=<nil>', 'M=map[](nil:true)'), done=lidx(S(2), 'JSON {}'), kv=KV([['map', '合并(旧键保留)'], ['切片', '整体替换'], ['非 nil 指针', '原地改写,别预填共享对象']], ['非 nil 指针'])),
    step("出错时已经写进去的字段:类型错误不会中止解码,后面的字段照样赋值,最终只报第一个错误——a 的类型错了,b、c、d 仍被赋值(A:0 B:ok C:3 D:[1 2]);b 类型错时 a、c 已赋值;c 错了 d 里 [\"q\"] 也产生了 [0]。语法错误(; 或缺 })则一个字段都不赋值,因为 Go 先整体检查语法再解码。所以绑定出错时不要使用结构体里的任何值。", t=tl(S(3)), mark=lidx(S(3), '"a":"x"', '"a":1,"b":2', '"c":"z"'), done=lidx(S(3), '; "c":3', '"c":3  '), kv=KV([['类型错误', '其它字段照常赋值,只报第一个错'], ['语法错误', '一个字段都不赋值'], ['结论', '出错就别用这个结构体']], ['结论'])),
    step("要区分“没传 / null / 零值”(PATCH 语义):指针只能区分 nil(没传或 null)与非 nil;json.RawMessage 能区分没传(空)、null(\"null\")、有值,但要自己再解析;自定义泛型类型 Opt[T] 实现 UnmarshalJSON:没传时方法根本不被调用(Set=false),null 时 Null=true,零值时 Val 是 0 或空串且 Set=true——三种状态完全分开。", t=tl(S(4)), mark=lidx(S(4), 'Age=没传 Name=没传', 'Age=null Name=null', 'Age=值=0 Name=值='), done=lidx(S(4), 'Age=值=30 Name=值=ann'), kv=KV([['*T', '没传和 null 分不开'], ['json.RawMessage', '能分开,但要自己解析'], ['Opt[T] + UnmarshalJSON', '没传 / null / 零值三态分明']], ['Opt[T] + UnmarshalJSON'])),
]
A = mkartn('n32', 32, 'Gin,JSON绑定,缺失字段,多余字段,PATCH,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测多余字段与缺失字段:缺失字段保持预填值、传了零值会覆盖、null 对非指针字段是空操作;预填的 map 合并、切片替换、非 nil 指针原地改写;类型错误不会中止解码;用 *T、RawMessage、自定义 Opt[T] 区分“没传 / null / 零值”。',
    '前端少传了字段、多传了字段、传了 null,绑定之后结构体里到底是什么?预填默认值能不能用?绑定出错时部分字段是不是已经被赋值?这篇把这些边界一个个试出来,最后给 PATCH 场景做个能区分没传、null、零值的类型。',
    [('保持预填值', '缺失字段不改动:JSON {} → Page:1 Size:20'), ('map 合并', '预填的 map 与请求里的 m 合并,旧键保留,而切片被整体替换'), ('3 种状态', 'Opt[T] 区分没传 / null / 零值,普通的 *T 只能区分两种')],
    [('缺失与零值', '<p>缺失的字段不会被碰,所以可以预先把默认值填进结构体再绑定(JSON 与查询串都是这样)。传了零值就是覆盖成零值:<code>{"page":0}</code> 会把预填的 Page=1 改成 0,而不是保留默认值。<code>null</code> 对非指针字段是空操作,对指针则置为 nil。</p>'),
     ('预填的复合值', '<p>预填的 map 会与请求里的对象<b>合并</b>(旧键保留),切片整体替换,较短的数组把多出的位置清零,嵌套结构体逐字段合并,非 nil 的指针会被原地改写——如果预填的指针指向共享对象,一个请求会永久改掉它。绑定用的结构体每次都应该新建,不要预填共享的指针或 map。</p>'),
     ('出错之后的状态', '<p>JSON 类型错误不会中止解码,所以出错时结构体可能处在“一部分字段已赋值”的状态;语法错误则整体不赋值。绑定返回错误之后应当直接返回 400,不要使用结构体里的任何值。</p>'),
     ('三态字段', '<p>PATCH 接口要区分“没传(保持原值)”“传了 null(清空)”“传了零值”。指针字段分不开前两种;<code>json.RawMessage</code> 能分开但要二次解析;给泛型类型加一个 <code>UnmarshalJSON</code> 最直接:没传时这个方法根本不会被调用,所以 <code>Set</code> 保持 false。</p>')],
    steps,
    [ENV_N_GIN + '。请求用 httptest 直接调用 ServeHTTP;预填值在 handler 里创建结构体时设置;Opt[T] 是实验里自己写的泛型类型;每种情形各一次',
     '没有验证:XML、YAML 绑定下缺失与 null 的行为;自定义类型实现 UnmarshalJSON 时与 binding 校验标签的交互;表单绑定里切片与 map 的预填合并规则(只验证了标量);encoding/json 在不同 Go 版本里对数组、null 的细节差异'],
    '缺失与多余字段')
