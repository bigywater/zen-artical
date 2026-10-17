from lib import *
S = SS('f56')
R = J('f56')
steps = [
    step("全局函数与全局值:@app.template_global() 的 utcnow() → {{ utcnow().year }} 得到 2026;@app.template_global('site_url') → https://example.test/a;add_template_global(initials, 'initials') → 张三四;直接写 jinja_env.globals['SITE_NAME'] 与 VERSION → bigywater v1.2.3;蓝图用 app_template_global 注册的 from_bp() 全局可用;@pass_context 的全局函数 current_path() 能读 request.path 与模板变量 title(/page|T)。不写括号时({{ utcnow }})输出的是函数对象的 repr(被转义成 &lt;function …&gt;)。", t=tl(S(1)), done=lidx(S(1), 'utcnow().year', 'site_url', 'initials', 'SITE_NAME'), mark=lidx(S(1), 'from_bp', 'current_path', '{{ utcnow }}'), kv=KV([['函数', '模板里调用 name()'], ['值', 'jinja_env.globals[...]'], ['pass_context', '能读 request 与模板变量']], ['pass_context'])),
    step("渲染时传进来的同名变量优先于全局:全局 SITE_NAME = bigywater,视图里 render_template_string('{{ SITE_NAME }}', SITE_NAME='被视图覆盖') 得到「被视图覆盖」。", t=tl(S(2)), done=lidx(S(2), '视图里传 SITE_NAME'), kv=KV([['同名变量', '渲染时传入的优先于全局']], ['同名变量'])),
    step("关键区别:导入的模板默认不带上下文,但能看到全局。宏模板 macros.html 里 show() 读 SITE_NAME(全局)、ctx_var(上下文处理器注入的)、request:不带 context 导入时得到「全局:bigywater|处理器变量:看不到|request:/page」—— 全局(以及 Flask 的 request 全局)看得到,处理器变量看不到;加 with context 导入后 show_ctx() 得到「处理器变量:来自上下文处理器」。需要在所有模板(包括被 import 的宏)里都能用的东西,要放全局。", t=tl(S(3)), done=lidx(S(3), 'import … 默认'), mark=lidx(S(3), 'import … with context'), kv=KV([['import(默认)', '看得到全局,看不到处理器变量'], ['import … with context', '处理器变量也可见']], ['import(默认)'])),
    step("Flask 默认就有的全局(jinja_env.globals):config、cycler、dict、g、get_flashed_messages、joiner、lipsum、namespace、range、request、session、url_for。所以 request、session、config、url_for 即使在不带 context 的宏里也能用。", t=tl(S(4)), done=lidx(S(4), "'config'"), kv=KV([['Jinja 自带', 'cycler、dict、joiner、lipsum、namespace、range'], ['Flask 加的', 'config、g、get_flashed_messages、request、session、url_for']], ['Flask 加的'])),
    step("全局值只在注册时求值一次:jinja_env.globals['STARTED_AT'] = time.time() 之后两次渲染得到相同的值(True);时间类的值要注册成函数:globals['now_ts'] = time.time,{{ now_ts() }} 两次渲染不同(True)。", t=tl(S(5)), done=lidx(S(5), '全局值 STARTED_AT', '全局函数 now_ts()'), kv=KV([['全局值', '注册时求值一次'], ['全局函数', '每次调用都执行']], ['全局值'])),
    step("执行次数对比:渲染 100 次不使用任何变量的模板,上下文处理器执行 100 次,全局函数执行 0 次。全局函数只在模板里被调用时才执行;处理器无论用不用都执行一次。", t=tl(S(6)), done=lidx(S(6), '渲染 100 次'), kv=KV([['上下文处理器', '100 次'], ['全局函数', '0 次(没被调用)']], ['全局函数'])),
]
A = mkartf('f56', 56, 'Flask,Jinja2,模板全局,template_global,真实验证,动画演示',
    '实测 Flask 的模板全局:template_global、add_template_global、jinja_env.globals、蓝图的 app_template_global、pass_context;渲染时传入的同名变量优先;被 import 的宏(不带 context)能看到全局但看不到上下文处理器的变量;全局值只求值一次;未被调用的全局函数执行 0 次。',
    '全局函数和上下文处理器有什么区别?为什么宏里看不到我注入的变量?时间值能不能直接放全局?这篇用同一个应用把它们对比一遍。',
    [('12 个', '本机 Flask 环境里默认的模板全局个数'), ('0 次', '渲染 100 次不使用变量的模板时,全局函数被执行的次数'), ('with context', '让被导入的宏看到上下文处理器变量的写法')],
    [('全局函数与全局值', '<p>上一篇:<a href="flask-custom-template-filter.html">自定义 Template Filter</a>;下一篇:<a href="flask-custom-template-test.html">自定义 Template Test</a>;上下文处理器:<a href="flask-context-processor.html">Context Processor</a>。</p>'), ('同名时谁优先', None), ('宏里的可见性', None), ('默认全局', None), ('求值时机', None), ('执行次数', None)],
    steps, [ENV_F, '没有验证:全局函数在异步模板里的 await 行为、国际化(gettext)全局的安装方式、模板里 {% set %} 与全局同名时的遮蔽、全局名字与过滤器同名时的行为'], '模板全局')
