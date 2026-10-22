from lib import *
S = SS('x66')
steps = [
    step("各个 starter 拉来多少依赖(单独解析完整 classpath,含传递依赖)。spring-boot-starter:21 个 jar,8.4 MB;spring-boot-starter-webmvc:39 个 jar,18.7 MB;webflux:65 个,33.6 MB;data-jpa:55 个,40.3 MB;security:28 个,14.2 MB;actuator:32 个,10.4 MB;validation:28 个,10.2 MB;test:50 个,23.2 MB。同样叫 starter,拉来的东西差别很大;webflux 的 jar 数几乎是 webmvc 的两倍。", t=tl(S(1)), mark=lidx(S(1), 'webflux', 'data-jpa'), done=lidx(S(1), 'spring-boot-starter  ', 'webmvc'), b=bars([['starter(核心)jar 数', 21, '21'], ['webmvc jar 数', 39, '39'], ['data-jpa jar 数', 55, '55'], ['webflux jar 数', 65, '65']], 65, done=[0, 1], mark=[2, 3]), kv=KV([['spring-boot-starter', '21 个 jar,8.4 MB'], ['webmvc', '39 个 jar,18.7 MB'], ['webflux', '65 个 jar,33.6 MB'], ['data-jpa', '55 个 jar,40.3 MB']], ['webflux'])),
    step("starter 自己的 jar 里是什么。spring-boot-starter-webmvc-4.0.8.jar 只有 4 个条目(MANIFEST、LICENSE、NOTICE 和目录),.class 文件 0 个,4749 字节;spring-boot-starter-data-jpa-4.0.8.jar 同样 4 个条目、0 个 .class、4761 字节。starter 本身没有任何代码,它存在的意义只是它的 pom。", t=tl(S(2)), mark=lidx(S(2), '.class 文件 0 个'), done=lidx(S(2), 'webmvc', 'data-jpa'), b=bars([['webmvc starter 的 .class 文件数', 0, '0'], ['data-jpa starter 的 .class 文件数', 0, '0'], ['webmvc starter jar 字节数', 4749, '4749']], 4749, mark=[0, 1], cur=[2]), kv=KV([['starter jar', '4 个条目,0 个 .class'], ['内容', 'MANIFEST、LICENSE、NOTICE'], ['作用', '靠 pom 把一组依赖打包在一起']], ['starter jar'])),
    step("starter-webmvc 的 pom 直接声明了 5 个依赖:spring-boot-starter、spring-boot-starter-jackson、spring-boot-starter-tomcat、spring-boot-http-converter、spring-boot-webmvc,全部是 compile 范围。Spring MVC 本体、Tomcat、Jackson 都是通过这几个传递进来的;自动配置类在 spring-boot-webmvc 这个模块里,不在 starter 里。", t=tl(S(3)), mark=lidx(S(3), 'spring-boot-webmvc'), done=lidx(S(3), 'starter-tomcat', 'starter-jackson'), b=bars([['pom 直接依赖个数', 5, '5'], ['其中 compile 范围', 5, '5']], 5, done=[0, 1]), kv=KV([['直接依赖', 'starter、jackson、tomcat、http-converter、webmvc'], ['范围', '全部 compile'], ['自动配置类', '在 spring-boot-webmvc 模块里']], ['自动配置类'])),
    step("同一份启动代码,换类路径。只有 spring-boot-starter:应用类型 NONE,Bean 总数 50,类路径上没有 DispatcherServlet,没有 Tomcat 的 Bean,启动用时 348 ms。换成 spring-boot-starter-webmvc:应用类型 SERVLET,Bean 总数 143,有 DispatcherServlet 和 Tomcat 的 Bean,启动用时 692 ms。代码一行没变,变的只是类路径,自动配置据此多注册了 93 个 Bean(算出来的差值)。", t=tl(S(4)), mark=lidx(S(4), 'spring-boot-starter-webmvc:'), done=lidx(S(4), '类路径 = spring-boot-starter:'), b=bars([['只有 spring-boot-starter:Bean 总数', 50, '50'], ['加了 webmvc:Bean 总数', 143, '143'], ['启动用时 ms(仅 starter → webmvc)', 692, '348 → 692']], 692, done=[0], mark=[1, 2]), kv=KV([['只有 starter', 'NONE 应用,50 个 Bean'], ['加 webmvc', 'SERVLET 应用,143 个 Bean'], ['启动用时', '348 → 692 ms(单次运行)'], ['原因', '自动配置按类路径上的类决定']], ['原因'])),
]
A = mkartx('x66', 66, 'Spring,Boot,starter,依赖,自动配置,真实验证,动画演示',
    '实测 Spring Boot 4 的 starter 到底是什么:starter 的 jar 里 0 个 .class,只有一个 pom;webmvc 的 pom 直接依赖 5 个;各个 starter 拉来的 jar 数差别很大(核心 21 个、webmvc 39 个、webflux 65 个、data-jpa 55 个);同一份启动代码,类路径从 starter 换成 starter-webmvc,Bean 数从 50 变成 143,应用类型从 NONE 变成 SERVLET。',
    'starter 里到底有什么?为什么加一个依赖就多出一个 Web 服务器?各个 starter 拉来多少 jar?这篇直接解析依赖、打开 starter 的 jar、对比同一份启动代码在不同类路径下的差别。',
    [('0 个', 'starter-webmvc / starter-data-jpa 的 jar 里 .class 文件的个数'), ('39 / 65', 'starter-webmvc 与 starter-webflux 拉来的 jar 个数'), ('50 → 143', '同一份启动代码,类路径加上 starter-webmvc 之后的 Bean 总数')],
    [('依赖量', '<p>不同的 starter 拉来的依赖数量差别很大。</p>'),
     ('jar 内容', '<p>starter 本身没有代码,只有 pom。</p>'),
     ('pom', '<p>直接依赖几个模块,自动配置在模块里。</p>'),
     ('效果', '<p>类路径变了,自动配置就跟着变。</p>')],
    steps,
    [ENV_X + '。依赖解析用 Maven 对 Boot 4.0.8 的 BOM 解析出完整 classpath,jar 个数与大小是本机解析结果;starter pom 取自本地仓库;最后一节是单次运行,启动用时没有重复测量',
     '没有验证:starter 依赖的 exclude 写法;第三方 starter 的命名约定(xxx-spring-boot-starter);optional 依赖对 classpath 的影响;Gradle 下的差别;jar 数里重复或版本冲突的情形;启动用时的多次重复测量'],
    'starter')
