from lib import *
S = SS('n29')
steps = [
    step("required 的判定在 validator 的 hasValue 里:切片、map、指针、接口、channel、函数看是不是 nil;其它类型先看“是不是指针解引用来的”,否则 field.IsValid() && !field.IsZero()——也就是值类型字段只要等于零值就不通过。", t=tl(S(1)), mark=lidx(S(1), 'return !field.IsNil()', 'return field.IsValid() && !field.IsZero()'), done=lidx(S(1), 'case reflect.Slice, reflect.Map, reflect.Ptr', 'fldIsPointer'), kv=KV([['引用类型', '只看是不是 nil'], ['值类型', '等于零值就不通过'], ['指针指向的值', '解引用后不再按零值判断']], ['值类型'])),
    step("同样的 JSON 传给值类型字段和指针字段:{\"age\":18,…} 两者都通过;{\"age\":0,\"name\":\"\",\"admin\":false,\"score\":0} 值类型 4 个字段全部 required 失败,指针字段 4 个全部通过(指针非 nil,0 是合法值);{}(不传)和 null,两者都失败。所以“允许传 0 / false / 空串,但必须传”要用指针。", t=tl(S(2)), mark=lidx(S(2), '"age":0,"name":""'), done=lidx(S(2), '"age":18'), b=bars([['值类型,传零值', 4, '4 项失败'], ['指针类型,传零值', 0, '0 项失败'], ['值类型,不传', 4, '4 项失败'], ['指针类型,不传', 4, '4 项失败']], 4, mark=[0, 2, 3], done=[1]), kv=KV([['值类型 + required', '0、""、false 都当作没传'], ['指针 + required', '传了就算,null / 不传才失败'], ['想要“必传但可为 0”', '用指针']], ['指针 + required'])),
    step("其它类型:切片和 map 传空集合 [] / {} 通过(非 nil),不传才失败;字符串 \"   \"(三个空格)通过(不是空串);time.Time 的零值 0001-01-01 和不传都失败;嵌套的结构体字段 In 本身不检查,检查的是里面的 In.X(传 {} 时报 T.In.X);指针结构体 PIn 不传时报 T.PIn,传 {} 时报 T.PIn.X。", t=tl(S(3)), mark=lidx(S(3), '空集合', '三个空格', '零时间', 'at 不传', 'in:{}', 'pin 不传', 'pin:{}'), done=lidx(S(3), '全部给出且非零', 's、m 不传'), kv=KV([['[] 与 {}', '通过(非 nil)'], ['"   "', '通过(不是空串)'], ['嵌套结构体', '不检查自身,检查里面的字段']], ['[] 与 {}'])),
    step("查询串:缺失的键不会调用 setter,零值就是零值,于是 ?age=0、?age=(空值)、不传 age 对 required 的结果都是失败;指针 Page 不传时保持 nil(required 失败),传 page=0 或 page=(空值)时是指向 0 的非 nil 指针,required 通过——?age=0&page=0&gt=0 那一行的失败项只有 Age 和 Gt,没有 Page。gt=0 与 required 一样挡住零值;omitempty 配合 gt=0 让“不传 / 传 0”都通过,传负数才失败。", t=tl(S(4)), mark=lidx(S(4), '/x?age=0&page=0&gt=0', '/x?age=&page=&gt=', '/x?age=5&page=2&gt=1&opt=-3'), done=lidx(S(4), '/x?age=5&page=2&gt=1  ', '/x?age=5&page=2&gt=1&opt=0'), kv=KV([['?age=0', 'required 失败'], ['不传的指针', '保持 nil,required 失败'], ['omitempty,gt=0', '零值直接放行,负数才报错']], ['omitempty,gt=0'])),
]
A = mkartn('n29', 29, 'Gin,validator,required,零值,指针,omitempty,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测 required 对零值的陷阱:值类型字段传 0 / 空串 / false 都当作没传,指针字段传零值则通过、不传或 null 才失败;空切片 [] 与全空格字符串通过;time.Time 零值失败;嵌套结构体自身不检查;查询串里缺失的键与 0 都是零值。',
    '前端传了 {"age":0},后端却说 age 是必填?binding:"required" 对零值的判定常常出乎意料。这篇从 validator 的 hasValue 源码出发,用 JSON 和查询串把值类型、指针、切片、map、字符串、时间、嵌套结构体的“零值”与“没传”对比一遍。',
    [('4 / 4', '值类型字段传 0 / "" / false / 0 时 required 失败的个数'), ('0 / 4', '指针字段传同样的零值时失败的个数'), ('[] 通过', '空切片 [] 与全空格字符串通过 required;不传才失败')],
    [('required 看的是什么', '<p><code>required</code> 对切片、map、指针这类引用类型只看是不是 nil;对其它类型看是不是零值。所以 <code>int</code> 的 0、<code>string</code> 的空串、<code>bool</code> 的 false 都被当作“没提供”——这与 JSON 里“显式传了 0”是两回事。</p>'),
     ('指针区分“没传”和“零值”', '<p>要区分这两种情况,把字段改成指针:<code>*int</code> 配 <code>required</code>,传 0 时指针非 nil 通过,不传或 <code>null</code> 时是 nil 失败。代价是业务代码里要解引用。如果只想要“不能为空”,值类型的 <code>required</code> 恰好合适。</p>'),
     ('其它类型的细节', '<p>空数组 <code>[]</code> 和空对象 <code>{}</code> 解码出来是非 nil 的空集合,通过 <code>required</code>,想要“非空”要用 <code>min=1</code>;只含空格的字符串不是空串,也通过,需要 <code>TrimSpace</code> 或自定义规则;<code>time.Time</code> 的零值失败;嵌套结构体字段自身不被 <code>required</code> 检查,检查的是它里面的字段;指针结构体没传时报它自己。</p>'),
     ('表单与查询串', '<p>表单绑定里缺失的键根本不会调用 setter,字段保持零值,所以 <code>?age=0</code>、<code>?age=</code>、不传 age 三种情况对值类型的 <code>required</code> 没有区别,<code>gt=0</code> 同理。要让“不传”合法而“传了就必须合法”,用 <code>omitempty,gt=0</code>。</p>')],
    steps,
    [ENV_N_GIN + '。校验器是 Gin 内置的 validator v10.30.1;JSON 请求用 httptest 直接调用 ServeHTTP,查询串用 ShouldBindQuery;hasValue 的源码来自模块缓存里 validator@v10.30.1 的 baked_in.go;每种情形各一次',
     '没有验证:validator 的 WithRequiredStructEnabled 选项(Gin 没有开启,没有跑);required_if / required_with 等条件规则对零值的处理;自定义类型实现 Zero 判断的情形;XML、YAML 绑定下的零值行为'],
    'required 与零值')
