from lib import *
S = SS('f73')
R = J('f73')
steps = [
    step("先踩一个坑:字段用了 Email() 校验器,但没装 email_validator 包,提交表单会直接抛异常「Install 'email_validator' for email validation support.」(这是第一次运行时的真实报错,装上包之后才有下面的实验输出,最终输出只保留「已安装」一行)。", t=tl(S(1)), done=lidx(S(1), '已安装'), kv=KV([['Email()', '需要 email_validator 包'], ['没装', '提交时抛异常']], ['没装'])),
    step("GET 渲染表单时 hidden_tag() 输出 csrf_token 隐藏域。token 有 3 段,第 1 段 base64 解码是一个随机串(同时存在 session['csrf_token'] 里),不是用户信息;渲染之后 session 里多了 csrf_token 这个键。", t=tl(S(2)), done=lidx(S(2), '结构', 'session 里多了键'), kv=KV([['token 结构', '3 段,第一段是随机串'], ['session', '多了 csrf_token']], ['token 结构'])),
    step("提交校验:合法数据加 token 返回 200;合法数据没有 token 返回 400「The CSRF token is missing.」;用户名太短、自定义校验 validate_username(admin)、邮箱格式、年龄 17、年龄不是数字(Not a valid integer value. 加 18-120 两条)、两次密码不一致、不勾选同意,各自出现在对应字段的 errors 里;什么都不填则每个必填字段各一条错误。", t=tl(S(3)), done=lidx(S(3), '合法数据 + token', '什么都不填'), mark=lidx(S(3), '没有 token'), kv=KV([['errors', '按字段分组的列表'], ['自定义校验', 'validate_字段名 方法'], ['缺 CSRF', 'errors[\"csrf_token\"]']], ['errors'])),
    step("validate_on_submit() 只在 POST/PUT/PATCH/DELETE 时才校验;GET /signup 返回 ok False、submitted False、errors 为空,所以第一次打开表单不会满屏报错。", t=tl(S(4)), done=lidx(S(4), 'GET /signup'), kv=KV([['GET', 'validate_on_submit() 为 False,无错误']], ['GET'])),
    step("CSRF token 的几种失败:正常 200;用别的会话的 token → 「The CSRF tokens do not match.」;篡改末尾 → 「The CSRF token is invalid.」;WTF_CSRF_TIME_LIMIT=1 秒、等 2.5 秒再提交 → 「The CSRF token has expired.」(时间戳精度是秒);WTF_CSRF_ENABLED=False(测试里常用)→ 200。", t=tl(S(5)), done=lidx(S(5), '正常', 'WTF_CSRF_ENABLED'), mark=lidx(S(5), 'do not match', 'invalid', 'expired'), kv=KV([['别的会话', 'do not match'], ['篡改', 'invalid'], ['超时', 'expired']], ['别的会话'])),
    step("AJAX 把 token 放在 X-CSRFToken 请求头里,或把 JSON 当请求体:FlaskForm 都不认,仍然报「The CSRF token is missing.」(400)。头要由 CSRFProtect 来认。", t=tl(S(6)), mark=lidx(S(6), '400'), kv=KV([['FlaskForm', '只读表单字段 csrf_token'], ['请求头', '要靠 CSRFProtect']], ['FlaskForm'])),
    step("CSRFProtect 全局保护:不用 FlaskForm 的 /p 接口,POST 没有 token 返回 400(正文含 The CSRF token is missing.);带 token 的 POST 返回 200。", t=tl(S(7)), done=lidx(S(7), '带 token'), mark=lidx(S(7), '没有 token'), kv=KV([['CSRFProtect', '所有非安全方法都要 token']], ['CSRFProtect'])),
    step("文件上传校验:不传文件 → FileRequired 的「This field is required.」;a.exe → FileAllowed 的自定义信息「只允许 png/jpg」;a.png 通过。", t=tl(S(8)), done=lidx(S(8), 'a.png'), mark=lidx(S(8), 'a.exe', '没有文件'), kv=KV([['FileRequired', '没传文件'], ['FileAllowed', '按扩展名白名单']], ['FileAllowed'])),
]
A = mkartf('f73', 73, 'Flask,Flask-WTF,WTForms,CSRF,表单验证,真实验证,动画演示',
    '实测 Flask-WTF 的表单校验:Email() 依赖 email_validator;csrf_token 的结构与 session 的关系;各字段的错误信息;validate_on_submit 在 GET 时的行为;CSRF 的缺失、不匹配、篡改、过期四种报错;请求头与 JSON 为什么 FlaskForm 不认而要用 CSRFProtect;文件上传校验。',
    'Flask-WTF 的校验到底在哪一步报什么错?CSRF token 里装了什么、什么情况下会失败?AJAX 的 X-CSRFToken 请求头为什么有时候没用?这篇用 test_client 把每一种错误信息逐个打印出来。',
    [('4 种', 'CSRF 失败的报错:missing / do not match / invalid / expired'), ('3 段', 'csrf_token 的结构,第一段是 session 里的随机串'), ('0 条', 'GET 请求时 validate_on_submit() 的错误数')],
    [('Email() 的依赖', '<p>上一篇:<a href="flask-flask-login-flow.html">Flask-Login 登录流程</a>;下一篇:<a href="flask-flask-migrate-basics.html">Flask-Migrate 基础</a>。</p>'), ('csrf_token 的结构', None), ('各字段的错误信息', None), ('validate_on_submit', None), ('CSRF 的四种失败', None), ('请求头与 JSON 请求体', '<p>只有 FlaskForm 不认请求头;用了 CSRFProtect 就可以(见下一节)。</p>'), ('CSRFProtect', None), ('文件上传校验', None)],
    steps, [ENV_F + '。Flask-WTF 1.3.0、WTForms 3.2.2、email_validator', '没有验证:真实浏览器里 CSRF 攻击的复现、SameSite cookie 对 CSRF 的影响(见第 125 篇)、FieldList/FormField 嵌套表单、Flask-WTF 的 recaptcha、文件上传的大小限制(见相关篇)'], 'Flask-WTF 表单验证')
