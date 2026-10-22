from lib import *
S = SS('v29')
steps = [
    step("优先级矩阵。8 个 location:A 精确 /exact;B 前缀 /a/;C 前缀 /a/b/;D ^~ /static/;E 正则 ~ .php 结尾;F 正则 ~* .jpg/.png;G 正则 ~ ^/a/b/c;H 前缀 /。/exact 命中 A,/exact/ 和 /exact?x=1:/exact/ 落到 H,带查询串的 /exact?x=1 仍命中 A。/a/x 命中 B,/a/b/x 命中 C。/a/b/c/d 命中 G(正则胜过最长前缀 C)。/a/x.png 命中 F(正则胜过前缀 B)。/static/x.php 和 /static/a.jpg 都命中 D(^~ 前缀一旦是最长前缀就不再试正则)。/x.php、/a/x.php 命中 E,/pic.JPG 命中 F,/pic.jpg/ 落到 H(以斜杠结尾不匹配 .jpg$),/nothing 命中 H。", t=tl(S(1)), mark=lidx(S(1), '/a/b/c/d', '/static/x.php', '/a/x.png'), done=lidx(S(1), '/exact  ', '/a/x ', '/nothing'), b=bars([['/a/b/c/d → G(正则)', 1, 'G'], ['/static/x.php → D(^~)', 1, 'D'], ['/a/x.png → F(正则)', 1, 'F'], ['/exact/ → H', 1, 'H']], 1, mark=[0, 1, 2], done=[3]), kv=KV([['正则 vs 普通前缀', '正则胜出'], ['^~ 前缀', '最长时不再试正则'], ['= 精确匹配', '/exact 命中,/exact/ 不命中']], ['^~ 前缀'])),
    step("正则的顺序。/api/v1/users.json 同时匹配 ~ ^/api/ 和 ~ \\.json 结尾:R1 写在前,命中 R1;R2 写在前,命中 R2——正则按文件里的顺序试,第一个匹配的胜出。普通前缀 /api/ 和正则 ~ .json 结尾:前缀写在正则前或后,都是正则命中;把前缀换成 ^~ /api/:命中 ^~ 前缀,正则不再被试。普通前缀的先后顺序无关紧要,正则的先后顺序决定谁胜出,^~ 能保住前缀不被正则抢走。", t=tl(S(2)), mark=lidx(S(2), 'R2 写在前', '^~ /api/'), done=lidx(S(2), 'R1 写在前', '前缀 /api/ 写在正则前', '前缀 /api/ 写在正则后'), b=bars([['R1 在前 → R1', 1, 'R1'], ['R2 在前 → R2', 1, 'R2'], ['前缀在前/后 → 正则', 1, '正则 .json'], ['^~ /api/ → 前缀', 1, '前缀']], 1, done=[0, 2], mark=[1, 3]), kv=KV([['两个正则', '文件里先写的胜出'], ['前缀 + 正则', '正则胜出,与写的先后无关'], ['^~ 前缀', '保住前缀']], ['两个正则'])),
    step("规范化。同一份配置,/a/x 命中 B;//a//x(连续斜杠合并)、/%61/x(%61 解码成 a)、/a/./x、/a/b/../x(.. 段规范化后是 /a/x)、/a%2fx(%2f 解码成斜杠)都命中 B。/a/%2e%2e/exact 规范化后是 /exact,命中 A。/exact?x=1 命中 A(查询串不参与匹配),/exact%3Fx=1 命中 H(%3F 解码成字符 ?,但属于路径,不是查询串的开始)。nginx 在选 location 之前先把 URI 规范化。", t=tl(S(3)), mark=lidx(S(3), '/exact%3Fx=1', '/a/%2e%2e/exact'), done=lidx(S(3), '//a//x', '/%61/x', '/a%2fx'), b=bars([['//a//x → B', 1, 'B'], ['/%61/x → B', 1, 'B'], ['/a/%2e%2e/exact → A', 1, 'A'], ['/exact%3Fx=1 → H', 1, 'H']], 1, done=[0, 1], mark=[2, 3]), kv=KV([['连续斜杠 / 百分号 / . 与 ..', '先规范化再匹配'], ['?', '真的问号之后是查询串,不参与匹配'], ['%3F', '解码成路径里的字符']], ['%3F'])),
    step("大小写:同一份配置,macOS 上的 nginx 1.31.6 对 Linux 容器里的 nginx 1.27.5(版本也不同,所以只能说观察到不同)。/EXACT:macOS 命中 A,Linux 命中 H。/A/x:B 对 H。/A/B/x:C 对 H。/a/B/C/d:macOS 命中正则 G,Linux 命中 B。/A/b/c:G 对 H。/x.PHP:E 对 H。/STATIC/x.php:D 对 E。只有 ~* 的 /pic.JPG 两边都命中 F。这台 macOS 上前缀和 ~ 正则都不区分大小写,Linux 上都区分(~* 本来就不区分)。在 macOS 上开发、在 Linux 上部署,路径大小写相关的路由可能不一致。", t=tl(S(4)), mark=lidx(S(4), '/EXACT', '/A/b/c', '/x.PHP'), done=lidx(S(4), '/pic.JPG'), b=bars([['/EXACT:macOS', 1, 'A(命中)'], ['/EXACT:Linux', 0, 'H(没命中)'], ['/A/b/c:macOS', 1, 'G(命中)'], ['/pic.JPG:两边', 1, 'F(都命中)']], 1, mark=[0, 2], cur=[1], done=[3]), kv=KV([['macOS nginx 1.31.6', '前缀与 ~ 都不区分大小写'], ['Linux 容器 nginx 1.27.5', '前缀与 ~ 区分大小写'], ['~*', '两边都不区分']], ['macOS nginx 1.31.6'])),
]
A = mkartv('v29', 29, '微服务,网关,nginx,location,路由匹配,真实验证,动画演示',
    '实测 nginx location 匹配:正则胜过普通前缀、^~ 前缀不再试正则、多个正则按文件顺序;URI 先规范化(//、%61、..);这台 macOS 的 nginx 1.31.6 连 ~ 正则也不区分大小写,Linux 容器里的 nginx 1.27.5 区分。',
    'nginx 的 location 到底怎么选?= 、^~ 、~ 、~* 和普通前缀的优先级?正则的顺序有影响吗?路径里的 // 和 %61 会怎样?macOS 和 Linux 上的大小写行为一样吗?这篇用 8 个 location 的矩阵逐项量出来。',
    [('G 对 C', '/a/b/c/d 同时匹配前缀 /a/b/ 和正则 ~ ^/a/b/c 时,命中的是正则 G'), ('D 对 E', '/static/x.php 同时匹配 ^~ /static/ 和 ~ .php 结尾 时,命中的是 ^~ 前缀 D'), ('A 对 H', '/EXACT 在 macOS 的 nginx 1.31.6 上命中 = /exact(大小写不敏感),在 Linux 容器的 nginx 1.27.5 上落到 /')],
    [('优先级', '<p>= 精确 > ^~ 最长前缀 > 正则(按顺序) > 普通最长前缀。</p>'),
     ('正则顺序', '<p>正则按文件里的顺序试;普通前缀的先后无关紧要。</p>'),
     ('规范化', '<p>先合并斜杠、解码百分号、处理 . 和 .. 再匹配。</p>'),
     ('大小写', '<p>macOS 上前缀和 ~ 都不区分大小写,Linux 上区分。</p>')],
    steps,
    [ENV_V + '。nginx 是 Homebrew 的 1.31.6(macOS);Linux 对照是本机 Docker Desktop 里的 nginx:1.27-alpine(nginx/1.27.5);每个 location 直接 return 自己的名字,不经过上游;因为两边的 nginx 版本也不同,第四节的差别不能完全归因于操作系统;请求用原始 socket 发出,避免 client 库对路径做规范化',
     '没有验证:嵌套 location、命名 location(@name)、try_files 与 location 的相互作用;if 块的怪异行为;server_name 的通配符与正则匹配;nginx 官方文档的大小写说明原文(上面是凭记忆引用,已在实验输出里注明)'],
    '路由匹配')
