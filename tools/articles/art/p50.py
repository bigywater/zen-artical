from lib import *
S = SS('p50')
steps = [
    step("正确的登录流程(本机服务器,账号 alice / secret),用 requests.Session 自动带 cookie。① GET /login → 200,响应设置 sid cookie,页面里的表单字段(含隐藏字段)是 csrf_token、form_id=login-v2、next=/account、username、password、website(一个 CSS 隐藏的空输入框);② POST /login 带上全部字段和账号密码 → 302,Location=/account,并且换了一个新的 sid(登录前后 cookie 值不同);③ GET /account → 200 \"welcome alice\"。", t=tl(S(1)), done=lidx(S(1), '② POST /login', '③ GET /account'), mark=lidx(S(1), '会话 cookie 在登录前后'), kv=KV([['GET /login', '设会话 cookie,返回带 csrf_token 的表单'], ['POST /login', '带全部字段 → 302 + 新的会话 id'], ['GET /account', '200,已登录']], ['POST /login'])),
    step("故意做错的每一步,服务器怎么拒绝:没先 GET 表单、没有 cookie 就 POST → 403 'no session';有 cookie 但漏了 csrf_token → 403 'csrf token mismatch';csrf_token 值不对 → 403 同样;token 对但漏了另一个隐藏字段 form_id → 400 'missing form_id';把页面上所有输入框都填了(包括 CSS 隐藏的 website)→ 400 'honeypot filled';用会话 A 的 token 配会话 B 的 cookie → 403 'csrf token mismatch'。表单应当像浏览器那样原样提交:隐藏字段取默认值,只填用户名和密码。", t=tl(S(2)), done=lidx(S(2), '没先 GET 表单'), mark=lidx(S(2), '漏了 csrf_token', 'csrf_token 值不对', '漏了另一个隐藏字段', '蜜罐', '会话 A 的 token'), b=bars([['403 的情形', 4, '4'], ['400 的情形', 2, '2']], 6, mark=[0, 1]), kv=KV([['没有 cookie / token 不对 / 跨会话', '403'], ['缺隐藏字段 / 填了不该填的', '400'], ['做法', '表单原样提交,只覆盖账号密码']], ['做法'])),
    step("token 在登录失败后轮换:密码错误 → 401,服务器换了新的 token;这时还用旧 token 再提交正确密码 → 403 'csrf token mismatch';重新 GET 表单拿新 token 后再提交 → 302 成功。所以失败重试之前必须重新取表单,不能反复提交同一个 token。", t=tl(S(3)), done=lidx(S(3), '重新 GET 表单拿新 token'), mark=lidx(S(3), '还用旧 token'), kv=KV([['密码错误', '401,token 轮换'], ['旧 token + 正确密码', '403'], ['重新 GET 表单', '拿到新 token 后 302 成功']], ['旧 token + 正确密码'])),
    step("AJAX 风格:token 放在 <meta name=\"csrf-token\"> 里,请求头 X-CSRF-Token 回传。只发 JSON、不带头 → 403 'csrf header mismatch';带上 X-CSRF-Token → 200 {\"ok\": true}。token 从页面的 meta 里取,不在表单字段里。", t=tl(S(4)), done=lidx(S(4), '带 X-CSRF-Token'), mark=lidx(S(4), '只发 JSON'), kv=KV([['不带头', '403'], ['带 X-CSRF-Token', '200'], ['token 来源', 'meta 标签,不是表单字段']], ['token 来源'])),
    step("通用地收集表单字段的做法:取表单里所有带 name 的 input,隐藏字段取页面给的默认值,只覆盖用户名、密码。在这个页面上字段是 csrf_token、form_id、next、password、username、website 六个;其中除了账号密码,其余四个都是原样带回去(website 保持空)。", t=tl(S(5)), done=lidx(S(5), '字段 = '), kv=KV([['字段', '6 个:csrf_token、form_id、next、username、password、website'], ['只覆盖', 'username 和 password'], ['其余', '取页面的默认值,原样提交']], ['其余'])),
]
A = mkartp('p50', 50, '爬虫,CSRF,登录,表单,隐藏字段,Session,Cookie,requests,Python,真实验证,动画演示',
    '在本机登录页上完整走一遍并故意做错:要先 GET 表单拿会话 cookie 和 csrf_token,POST 时带上全部隐藏字段;没有 cookie 或 token 不对返回 403,缺 form_id 或填了隐藏输入框返回 400;登录失败后 token 轮换,旧 token 再提交 403;登录成功后会话 id 换了;AJAX 的 token 通过 X-CSRF-Token 头回传。',
    '登录一个有 CSRF 保护的表单,请求序列比想象的长:先取页面拿 cookie 和 token,再带着所有隐藏字段 POST,失败后 token 还会换。这篇在本机写一个登录页,逐步走通正确的流程,再逐个故意做错,看服务器怎么拒绝。',
    [('403 / 400', '漏掉 token 或 cookie 是 403;缺隐藏字段或多填了不该填的是 400'), ('2 个 cookie', '登录成功前后会话 cookie 的值不同——服务器在登录时换了新的会话 id'), ('旧 token → 403', '登录失败后 token 轮换,用旧 token 再提交正确密码被拒绝')],
    [('正确的流程', '<p>先 <code>GET /login</code> 拿到会话 cookie 和页面里的 <code>csrf_token</code>,再 <code>POST /login</code> 带上表单里所有字段(隐藏字段取默认值,只填账号密码),成功后 302 跳转并换新的会话 id。<code>requests.Session</code> 负责 cookie 的往返。</p>'),
     ('常见的错误', '<p>不先取表单、漏 token、token 不对、拿别的会话的 token,都是 403;缺别的隐藏字段是 400;把页面上所有输入框都填了(包括 CSS 隐藏的)会被服务器拒绝。做法是像浏览器一样提交:收集所有带 name 的 input,隐藏字段原样带回,只覆盖账号密码。</p>'),
     ('token 轮换', '<p>登录失败后服务器换了新 token,旧 token 再提交被拒绝。重试要重新 GET 表单。</p>'),
     ('AJAX 与 meta', '<p>前端发 JSON 请求时,token 常放在 <code>&lt;meta name="csrf-token"&gt;</code> 里,用 <code>X-CSRF-Token</code> 请求头回传;只发 JSON 不带头会被拒绝。</p>'),
     ('收集表单字段', '<p>在这个页面上表单共有 6 个字段,爬虫只覆盖 <code>username</code> 和 <code>password</code>,其余按页面原样提交。</p>')],
    steps,
    [ENV_P + '。本机服务器自己实现的登录页:会话 cookie(sid)、与会话绑定的 csrf_token(失败后轮换)、隐藏字段 form_id 与 next、CSS 隐藏的 website 输入框、登录成功时更换会话 id、/api/profile 要求 X-CSRF-Token 头;lxml 6.1.1 解析表单;全部在本机完成,不涉及任何真实网站的登录',
     '没有验证:真实站点的登录(验证码、短信、设备指纹、速率限制、多步验证);SameSite、Secure 等 cookie 属性的影响;CSRF token 绑定到 cookie 本身(双重提交 cookie)的实现;JavaScript 在提交前动态生成的字段或签名;OAuth/SSO 登录流程;会话固定与会话劫持的防护细节'],
    '表单与 CSRF')
