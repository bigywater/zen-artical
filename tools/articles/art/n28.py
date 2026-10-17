from lib import *
S = SS('n28')
steps = [
    step("binding.Validator.Engine() 的类型就是 *validator.Validate,可以直接注册规则:RegisterValidation(\"weekday\", …)(用 FieldLevel 取字段值)和 RegisterAlias(\"code8\", \"len=8,alphanum\")。合格的请求通过;不合格时:Day 的 weekday 不通过,End 的 gtfield=Start(跨字段、time.Time)不通过,Code 的别名 code8 不通过(Tag 是别名 code8,Param 是内部 len=8 的 8)。", t=tl(S(1)), mark=lidx(S(1), 'Req.Day[tag=weekday', 'Req.End[tag=gtfield', 'Req.Code[tag=code8'), done=lidx(S(1), '*validator.Validate: true', 'nil(校验通过)'), kv=KV([['Engine()', '*validator.Validate'], ['RegisterValidation', '自定义规则,FieldLevel 取值'], ['RegisterAlias', '把多条规则起个名字']], ['RegisterAlias'])),
    step("带参数的规则 startswithx=ID-:FieldLevel 的 Param() 取到 \"ID-\";结构体级校验 RegisterStructValidation(跨字段,发现 Min > Max 时 ReportError 一个 gtefield_min 失败);合格的请求通过,不合格的同时报 Tag 与 Max。RegisterTagNameFunc 的时机很重要:在已经校验过的类型 Range 之后才注册,Range 的名字不变(仍是 Range.Tag);第一次校验的新类型 Range2 则用 json 名(Range2.tag)——validator 缓存了每个类型的字段信息。", t=tl(S(2)), mark=lidx(S(2), 'Range2 → Range2.tag', 'Range  → Range.Tag'), done=lidx(S(2), 'Range.Tag[tag=startswithx param="ID-"] Range.Max[tag=gtefield_min', 'nil(校验通过)'), kv=KV([['参数', 'fl.Param()'], ['结构体级', 'RegisterStructValidation + ReportError'], ['TagNameFunc', '要在类型第一次校验前注册']], ['TagNameFunc'])),
    step("在字段上用了没注册的规则 nosuchrule:路由注册完成、程序启动,没有任何报错;第一个请求校验时 panic(Undefined validation function 'nosuchrule' on field 'Name'),第二个请求同样 panic。规则名拼错只有跑到那条路径时才发现,所以要写一个单测对每个绑定结构体各校验一次。", t=tl(S(3)), mark=lidx(S(3), 'panic: Undefined validation function'), done=lidx(S(3), '到这里没有任何报错'), kv=KV([['启动时', '不检查 tag 是否存在'], ['第一次校验', 'panic: Undefined validation function'], ['对策', '给每个结构体写一个校验的单测']], ['对策'])),
    step("binding.Validator 是个 StructValidator 接口变量,可以整体替换:换成自己的实现后,每次绑定成功解码都会调用它的 ValidateStruct(第 1 次、第 2 次,参数是 *main.Req),返回的错误原样成为 ShouldBindJSON 的错误;设为 nil 则完全不校验:空 JSON {} 的 required 也通过,Name 保持空串。", t=tl(S(4)), mark=lidx(S(4), '自定义校验器第 1 次被调用', '自定义校验器第 2 次被调用'), done=lidx(S(4), 'Validator=nil'), kv=KV([['接口', 'ValidateStruct + Engine'], ['替换', '每次绑定都调用新实现'], ['nil', '完全不校验']], ['nil'])),
]
A = mkartn('n28', 28, 'Gin,validator,自定义校验,RegisterValidation,StructLevel,Go,真实验证,动画演示',
    '在 Gin v1.12.0 里实测自定义校验器:从 binding.Validator.Engine() 拿到 *validator.Validate 注册规则、别名、带参数的规则和结构体级校验;RegisterTagNameFunc 必须在类型第一次校验之前;使用未注册的规则名要到第一次校验时才 panic;binding.Validator 可以整体替换或设为 nil。',
    '内置规则不够用时怎么加自己的?注册要放在哪里、什么时候生效?规则名写错会在什么时候暴露?这篇从 Engine() 开始,把自定义规则、别名、结构体级校验、TagNameFunc 的坑和整体替换校验器的做法一一试出来。',
    [('*validator.Validate', 'binding.Validator.Engine() 返回的引擎类型'), ('第一个请求才 panic', '规则名没注册时,程序启动正常,第一次校验时 panic: Undefined validation function'), ('nil', 'binding.Validator 设为 nil 之后,required 的空 JSON 也能通过')],
    [('注册规则与别名', '<p><code>binding.Validator.Engine().(*validator.Validate)</code> 就是原生的 validator 引擎。<code>RegisterValidation</code> 注册一个 <code>func(fl FieldLevel) bool</code>,<code>RegisterAlias</code> 把一串规则起个名字;跨字段的规则(<code>gtfield=Start</code>)是内置的,可以直接用在 <code>time.Time</code> 上。别名失败时 <code>Tag()</code> 是别名本身。</p>'),
     ('参数、结构体级与 TagNameFunc', '<p>规则可以带参数,在 <code>fl.Param()</code> 里取。需要同时看多个字段时,用 <code>RegisterStructValidation</code> 在 <code>StructLevel</code> 里 <code>ReportError</code>。<code>RegisterTagNameFunc</code> 能让错误里的字段名换成 json 名,但 validator 会缓存每个类型的字段信息:<b>必须在这个类型第一次被校验之前注册</b>,否则对它不生效。</p>'),
     ('规则名写错', '<p>validator 在第一次校验某个结构体时才解析它的 tag。规则名拼错或忘了注册,启动时一切正常,第一个走到这个结构体的请求才会 panic(被 Recovery 捕获成 500)。给每个绑定用的结构体写一个最简单的校验单测,就能在 CI 里提前发现。</p>'),
     ('整体替换', '<p><code>binding.Validator</code> 是个接口变量,实现 <code>ValidateStruct</code> 与 <code>Engine</code> 两个方法就能替换。设成 <code>nil</code> 则所有绑定都不再校验(<code>binding</code> 标签完全失效),这在测试里有用,在线上是危险的。</p>')],
    steps,
    [ENV_N_GIN + '。校验器是 Gin 内置的 validator v10.30.1;每个实验是一个独立的进程(全局的 binding.Validator 互不影响);请求用 httptest 直接调用 ServeHTTP;每种情形各一次',
     '没有验证:并发注册规则的安全性(validator 文档说明不是线程安全的,没有测);RegisterCustomTypeFunc(自定义类型的取值);RegisterTranslation 的错误翻译;替换成其它校验库(如 ozzo-validation)的完整集成'],
    '自定义校验')
