from lib import *
S = SS('f110')
R = J('f110')
steps = [
    step("短命的访问令牌(演示用 2 秒)加较长的刷新令牌(5 秒):登录得到 access 与 refresh,/me 200;2 秒后访问令牌过期,/me 返回 401 ExpiredSignatureError;用 refresh 调 /refresh 得到 200,新的 access 与新的 refresh 都和旧的不同,新 access 访问 /me 又是 200。访问令牌丢了损失小(很快过期),刷新令牌只发给一个端点,暴露面小。", t=tl(S(1)), mark=lidx(S(1), '2 秒后'), done=lidx(S(1), '登录得到', '/refresh', '新 access'), kv=KV([['access', '短命,每个请求都带'], ['refresh', '长命,只用于换新令牌']], ['refresh'])),
    step("刷新令牌轮换与重用检测:每次刷新把旧 refresh 标记为已使用并发一个新的;把已经用过的旧 refresh 再用一次(像是被偷了)→ 401「refresh token reuse detected; family revoked」,此后连合法的新 refresh 也失效(401 family revoked)——整个登录「家族」被撤销,攻击者与真用户都要重新登录。", t=tl(S(2)), mark=lidx(S(2), '再用已经用过', '合法的新'), kv=KV([['轮换', '每次刷新换新的 refresh'], ['重用检测', '旧令牌再出现 → 撤销整个家族']], ['重用检测'])),
    step("正常用户的副作用:第一次 /refresh 成功但响应在路上丢了,客户端用同一个旧令牌重试 → 401 reuse detected,服务端已经发出的那个新令牌也作废了(401)。严格的轮换会把这种合法重试当成重用;常见缓解是给旧令牌几秒的宽限期,本篇没有实现、也没有验证。", t=tl(S(3)), mark=lidx(S(3), '重试', '作废'), done=lidx(S(3), '第一次 /refresh'), kv=KV([['响应丢失后重试', '被判定为重用'], ['后果', '用户被迫重新登录']], ['响应丢失后重试'])),
    step("登出与过期:登出(撤销家族)后用刷新令牌 → 401 family revoked;但登出前签发的访问令牌在过期前仍然可用(/me 200),所以访问令牌要足够短;刷新令牌放过期(5 秒)之后 → 401 refresh token expired;乱写的 → 401 unknown refresh token。刷新令牌存的是 sha256,不存明文。", t=tl(S(4)), done=lidx(S(4), '登出后', '乱写'), mark=lidx(S(4), '登出前签发', '放了'), kv=KV([['登出', '撤销 refresh,access 要等过期'], ['过期', 'refresh 也有 expires']], ['登出'])),
    step("刷新令牌放进 cookie:Set-Cookie: refresh=…; Max-Age=5; Secure; HttpOnly; Path=/refresh; SameSite=Strict——只对 /refresh 这个路径发送,带 HttpOnly(脚本读不到,浏览器里的实际表现我没有验证)、Secure、SameSite=Strict;登录响应正文里只有 access。", t=tl(S(5)), done=lidx(S(5), 'Set-Cookie', '响应正文'), kv=KV([['Path=/refresh', '只在刷新接口发送'], ['HttpOnly + Secure + SameSite', '降低泄漏与跨站风险']], ['Path=/refresh'])),
]
A = mkartf('f110', 110, 'Flask,Refresh Token,JWT,令牌轮换,真实验证,动画演示',
    '实测 Refresh Token:短命访问令牌过期后用刷新令牌换新、刷新令牌轮换与重用检测(旧令牌再用会撤销整个家族)、响应丢失后合法重试被误判、登出后访问令牌仍可用到过期、刷新令牌过期、放进限定路径的 HttpOnly cookie。',
    '为什么要有 refresh token?轮换是什么?令牌被偷了怎么发现?登出之后访问令牌还能用吗?这篇用真实的令牌流程把每种情况的状态码打印出来。',
    [('family revoked', '旧刷新令牌被重用后,整个登录家族被撤销'), ('401', '响应丢失后用旧刷新令牌重试得到的结果(合法用户被误伤)'), ('Path=/refresh', '刷新令牌 cookie 只发送给刷新接口')],
    [('访问令牌与刷新令牌', '<p>上一篇:<a href="flask-jwt-login.html">JWT 登录认证</a>;下一篇:<a href="flask-api-rate-limit.html">API 限流</a>。</p>'), ('轮换与重用检测', None), ('合法重试被误伤', None), ('登出与过期', None), ('放进 cookie', None)],
    steps, [ENV_F + '。PyJWT 2.15.1,令牌记录保存在内存字典里(演示用)', '没有验证:数据库持久化与并发刷新的竞争、宽限期的实现、跨设备的多个家族管理、浏览器里 HttpOnly 与 SameSite 的实际拦截效果、刷新令牌的滑动过期与绝对过期的取舍'], 'Refresh Token')
