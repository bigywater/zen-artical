# tools/articles — 文章实验与发布流水线

python(#71–#110)、redis(#39–#133)、django(#11–#136)、zookeeper(#1–#110)四个系列的文章都由这里的脚本生成:
**先在真实环境里跑实验 → 实验输出存进 `out/` → 文章生成器只从 `out/` 取数 → `publish.py` 写入 zen 库。**

## 目录
- `lib.py` 页面渲染器(`sec / term / demo / step`、`blk(name,k)` 取实验输出的第 k 节、`J(name)` 取 JSON)
- `exp/dNN.py`(django)、`exp/rNN.py`(redis)、`exp/zNN.py`(zookeeper) 实验脚本;`out/` 是它们的真实输出(`.txt` 给文章展示、`.json` 给数字)
- `art/dNN.py`、`art/rNN.py`、`art/zNN.py` 文章生成器(字典 `A`:标题数据、正文、演示步骤、边界说明)
- `publish.py` `python3 publish.py d101 d102 ... [--save]`:构建 html 到 `html/`,加 `--save` 写入 zen 库(Article 保存时自动镜像备份并重建站点)
- `dj.py` 在 `djtmp/<name>/` 生成真实的小 Django 项目;`PG(port)` 自己起临时 PostgreSQL;`sec.py`(用 EXTRA_SETTINGS 切换设置)、`asrv.py`(起 uvicorn / gunicorn / daphne)是它的辅助
- `rl.py` redis 实验的 RESP 客户端与 `Node()`(自己起 redis)
- ZooKeeper 系列(`zookeeper_topics.json`:编号 → slug、标题,url 是 `zookeeper-<slug>.html`;`python3 publish.py z1 z2 …`):
  - `zkl.py` 自己起 ZooKeeper 3.9.6(brew 的 jar,`java -cp … QuorumPeerMain`)的 `Node / Ensemble / NetEnsemble / DEnsemble`、四字命令 `four()`/`kv()`、kazoo 客户端 `client()`、官方命令行 `cli()`、TCP 代理 `Proxy`(丢包 / 黑洞 / 抓字节)、TLS 证书 `pki()`、`threads()`(jstack)
  - `etcdl.py`(etcd 3 节点 + HTTP/JSON 网关)、`kfl.py`(Kafka 3.9.2 的 ZooKeeper / KRaft 模式)、`hbl.py`(HBase 2.6.6 的 master / region server)、`cnl.py`(Consul 2.0.4 三节点)
  - `procs/`(锁持有者、选举候选、master / worker、两阶段提交、定时任务等被 kill -9 的子进程)、`jmxc/JmxProbe.java`
  - `ext/`:Curator(`Z92–Z100.java`)、Dubbo(Provider / Consumer)、Go(`main.go`)、HBase 客户端(`Hb.java`)、Spring Cloud 演示应用的源码与 pom(不含依赖与二进制)
- `django_topics.json` django 126 个主题(编号、slug、标题);`html/harness.html` 用 iframe 逐步点击每个页面的演示(`python3 -m http.server 8765` 在 `html/` 下,浏览器里 `window.runAll([...])`)

## 运行环境(没有随目录保存)
- `dj.py` 期望 `../djlab/` 是一个虚拟环境,装了 Django 6.1.1、psycopg、psycopg_pool、gunicorn、uvicorn、uvicorn-worker、daphne、whitenoise
- 实验会生成 `djtmp/`、`pgdata/`、`rdata/`,体积很大,不要提交
- 实验流量不要走代理:`dj.py` 在导入时清掉了 `HTTP(S)_PROXY`;`pip` 需要代理

## ZooKeeper 系列的环境(没有随目录保存)
- 端口:ZooKeeper 7300+ / 7400+ / 7500+,etcd 7600+,KDC 7650,Consul 7700+,Kafka 7900+(controller 7910),HBase 7960+,应用 7971+;数据目录 `zkdata/`(很大,不要提交)
- 依赖:JDK 17、`brew install zookeeper etcd krb5`、venv 里装 kazoo / cryptography / kafka-python-ng、Maven(经代理下载,`MAVEN_OPTS=-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=1087`)取 Curator 5.7.1 / Dubbo 3.3.6 / Spring Boot 3.3.5 + Spring Cloud 2023.0.4 的 jar,Go 1.27 + go-zookeeper v1.0.4;Kafka 3.9.2、HBase 2.6.6、ZooKeeper 3.8.4(滚动升级)、Consul 2.0.4 从官方下载站下载;kube-apiserver 由 kubernetes-src.tar.gz(v1.37.1)用 `GOFLAGS=-mod=vendor go build ./cmd/kube-apiserver` 编出;两块磁盘镜像(`hdiutil create`,挂载在 /Volumes/ZKSMALL、/Volumes/ZKMED)用于磁盘满的实验
- `exp/zNN.py` 用 `venv`(带 kazoo)运行;`publish.py ... --save` 要用系统 python3(有 lxml 与 Django)

## 禁区(写在代码里也要遵守)
- 不碰用户自己的 redis(6379)、mysqld、postgres,一律另起端口
- 不用 8181 / 9101 / 9333(用户自己的 weed / SeaweedFS);ZooKeeper 的 AdminServer 默认端口 8080 也是 weed,所以一律 `admin.enableServer=false`
- 不用 2181 和 brew 自带的 `/opt/homebrew/etc/zookeeper/zoo.cfg`;kubectl 要用空的 kubeconfig(否则会带上用户自己的凭据)
- 每个结论必须来自实验输出;没跑过的写进文章 refs 的「没有验证」

## 已知的小坑
- `art` 里 `R[k]`(来自实验里的 `o`)没有标题行,不要 `[1:]` 切片;`blk()` 取到的才是不含标题行的文本
- `dj.env` 设了 `PYTHONDONTWRITEBYTECODE=1`,避免同秒内改写同样大小的 `models.py` 时读到旧 .pyc
- 同一个 `Signal.disconnect` 要带上 `sender=`,否则按 `dispatch_uid` 断不开
- d126 的第四节(浏览器里的 iframe 结果)是手工检查后写进 `out/d126.txt` 的,重跑脚本会丢掉

## ZooKeeper 系列的小坑
- `Node.start` 会先 kill 占着同一个 cfg 或端口的残留进程;用 `keep_cfg` 才能保留手工改过的 zoo.cfg
- 四字命令白名单默认只有 srvr;`maxClientCnxns` 会把四字命令的连接也算进去,查 `cons` 要在压满连接之前
- `wchs` / `wchc` 不统计 child watch,要数 watch 总数用 `mntr` 的 `zk_watch_count`
- kazoo 的状态监听器里不能同步调用 `create`(监听器在连接线程里回调);kazoo 的 `DoubleBarrier.enter()` 没有超时参数;kazoo 没有持久递归 watch(用 Java 客户端)
- `lib.san()` 会把 `/private/tmp/claude-501/...` 与 `192.168.x.x` 替换成占位符;路径的正则不能吞反斜杠(否则会破坏 JSON 转义)
- 本机 Docker 无法拉取镜像,所以没有用 kind;Consul / etcd / Kafka 的杀进程实验要给每次试验用独立的 key,别复用上一次试验的锁

## Rust 系列(`rust_topics.json`:编号 → slug、标题,url 是 `rust-<slug>.html`;`python3 publish.py u1 u2 … [--save]`)
- `rsl.py`:`tryit()`(打印带行号的源码 + 真实编译器输出 + 运行输出)、`rustc()` / `cargo()` / `proj()` / `asm_of()` / `run()`;`ENVB` 用 brew 的稳定版 rustc 1.98.1(`RUSTC_BOOTSTRAP=1` 可用 `-Z unpretty=hir/expanded`、`-Z print-type-sizes`、`-Z print-mono-items`、`-Z time-passes`、`-Z build-std`);`ENVN` / `ncargo()` 用隔离安装的 nightly(rustup 装在 `rsdata/rustup_home`、`rsdata/rustup_cargo`,不碰 brew 的 rustc 与用户的 `~/.cargo`)
- `exp/uNN.py` 实验(`out/uNN.txt|json` 是真实输出),`art/uNN.py` 文章生成器;`lib.py` 里 `SS('uNN')(k)` 按「行首 `== `」取第 k 节输出(输出里可能含 `== `,不要用 split);`ENV_U`(稳定版)、`ENV_N`(nightly)是文章末尾的环境说明
- 参考资料里的原则:没跑过的写进「没有验证」;benchmark 里每个结果都要 `black_box`(u65、u136 曾因死代码消除得到假数字,已重跑)
- #163 Miri、#164 Sanitizer(ASan 直接 `-Zsanitizer=address`;TSan 要 `-Zbuild-std`)、#165 cargo-fuzz、#166 cargo-audit/cargo-deny、#168 cargo-bloat/cargo-llvm-lines、#169 交叉编译、#170 CI 都用 `ENVN`;#170 的工作流没有在 GitHub 上运行过,只用 actionlint 检查并在本机按 `run:` 步骤执行

## Rust 系列的环境(没有随目录保存)
- 全部产物在 `rsdata/`(cargo_home、target*、proj、src、bin、asm、wasm、httpsrv、cproj、rustup_home、rustup_cargo、gopath、zigw 等,几百 MB~GB,可整体删除,不要提交)
- crates.io、static.rust-lang.org、github.com(RustSec 漏洞库)都经代理访问:`rsl.py` 里 `ENVB.setdefault('HTTPS_PROXY','http://127.0.0.1:1087')`;rustup 用 `rustup-init -y --no-modify-path --profile minimal --default-toolchain nightly -c miri -c rust-src`(RUSTUP_HOME/CARGO_HOME 指到 `rsdata/`);再 `rustup target add x86_64-apple-darwin x86_64-unknown-linux-musl aarch64-unknown-linux-musl wasm32-unknown-unknown aarch64-apple-ios`
- 用 `cargo +nightly install --locked` 装 cargo-fuzz、cargo-audit、cargo-deny、cargo-bloat、cargo-llvm-lines;actionlint 用 `go install github.com/rhysd/actionlint/cmd/actionlint@latest`(GOPATH 在 `rsdata/gopath`)
- wasm:`-Z build-std=core` + zig 自带的 wasm-ld(`pip install ziglang` 装在 `../djlab`),在 node 里运行;Linux musl 交叉链接用 `rsdata/zigw/zcc-*`(`python -m ziglang cc -target …-linux-musl`),要加 `-C link-self-contained=no`,aarch64 还要过滤 `-Wl,--fix-cortex-a53-843419`
- `publish.py ... --save` 用系统 python3(有 Django 与 PyYAML 的那个)

## Rust 系列的小坑
- zsh 里 `$pre[0-9]` 会被当成数组下标,批量生成 token 用 Python(见 `rp_all.py`)
- macOS 的 `sed -i` 需要 `''`;嵌在 f-string 里的转义引号用 Python 的 replace 改文件更稳
- Miri 默认开着隔离,程序里的 `Instant` 是虚拟时钟,测耗时要加 `-Zmiri-disable-isolation`
- `cargo fuzz run` 默认带 debug assertions:`get_unchecked` 越界会先被标准库的前提检查拦下;要让 ASan 报告要加 `-O`,且 fuzz 目标里的返回值要 `black_box`,否则越界读被优化掉

## Flask 系列(`flask_topics.json`:编号 → slug、标题,url 是 `flask-<slug>.html`;`python3 publish.py f1 f2 … [--save]`,共 190 篇)
- `fl.py`:`app(name, files)` 把迷你应用写进 `fltmp/`;`Server(d, cmd, port=None, **env)` 起真实的 gunicorn / flask run / uvicorn / uwsgi(自己的进程组,`.get/.req/.logtext/.stop`);`free_port()`、`tidy()`(去掉路径、调试 PIN)、`py()` / `pyfile()`
- `exp/fNN.py` 实验(`out/fNN.txt|json` 是真实输出),`art/fNN.py` 文章生成器(`mkartf` + `ENV_F`);输出里「行首 `== `」的节数必须等于文章 `body` 的小节数,否则 publish 报 IndexError
- Series 行 `flask` / `Flask 内部机制` / `#4A5568` 是我自己建的,不是用户选的
- 旧的 `content/tech/articles/flask-001..190.html` 只有标题,是遗留文件,没有动
- 写进文章「没有验证」的主要项目:#178 Docker 没有构建过完整镜像、没有 docker run(本机拉不到 python 基础镜像:构建机制用 FROM scratch 验证,pip 安装、绑定地址、PYTHONUNBUFFERED、只读目录用本机 Flask 验证);#189 没有真正的容器,也不是 Linux(1 号进程的信号语义没验证);#183 没有连真实的 Sentry 服务;#179 没有运行 Kubernetes 探针
- 安全类文章(#119–#135)只做防御性验证(检查配置与防护是否生效),不演示攻击载荷

## Flask 系列的环境(没有随目录保存)
- venv `flenv`(Flask 3.1.3、Werkzeug 3.1.9、SQLAlchemy 2.1.1、gunicorn、uwsgi、gevent、uvicorn、sentry-sdk 2.71.0、pydantic、marshmallow、PyJWT、各 Flask 扩展);nginx 用 brew 装的,每次跑自己的配置、端口 9600+
- PostgreSQL 用 `dj.PG`(端口 9450+,`-o '-p PORT -k SOCK'`);Redis 端口 9650+;不要碰 6379、8181/9101/9333、用户自己的 5432
- 无头 Chrome(`--headless=new --dump-dom`)不会自己退出:用 Popen、读到 `</html>` 后 killpg
- 页面验证:`html/harness.html` 的 `runAll(files)` 逐步点完每个演示(Flask 的 190 页全部通过:无空面板、无横向溢出、无 JS 错误)

## Flask 系列的小坑
- 实验用 `../flenv/bin/python exp/fN.py > /tmp/fN.log 2>&1` 运行(`tee()` 已经写 `out/fN.txt`,不要再把输出重定向到它)
- Flask 在第一个请求之后拒绝注册路由/错误处理器:每个用例用新的应用
- `pg_ctl start/restart` 必须带 `-o '-p PORT -k SOCK'`、`-l`,stdout/stderr 用 DEVNULL(不带 -o 会落到默认 5432,那是用户自己的 PostgreSQL;用 capture_output 时守护进程会占着管道让 run() 卡住)
- 从 `from_prefixed_env` 读到的纯数字密钥会变成 int(#184)
- macOS 没有 `timeout` 命令;`sed -i` 要 `''`;Docker BuildKit 会缓存相同内容的层,做缓存实验要给文件加随机串(#178)

## Java 系列(`java_topics.json`:编号 → slug、标题,url 是 `java-<slug>.html`;`python3 publish.py j1 j2 … [--save]`,共 294 篇,写进已有的 Series `java` / `Java 内部原理` / `#E76F00`)
- 编号 `jN` 对应 `java_topics.json` 里的第 N 项;`JOFF=140`(库里原有 140 篇旧 java 文章,新文章的序号从 141 起);每篇 `exp/jN.py` → `out/jN.txt` → `art/jN.py` → `publish.py jN --save`
- `jl.py`:`jrun(name, files, main, jdk, jopts, …)` 写源码 → javac → java;`jdir / write / tidy`;`mcp(*coords)` 用 Maven 解析 classpath(代理 127.0.0.1:1087,结果缓存在 `jtmp/_cp_*.txt`);`jenv(jdk)`;`JDKS` = {'17' Temurin 17.0.20、'21' brew openjdk@21、'27' brew openjdk 27、'25g' GraalVM CE 25(用完已删除,需要时重新下载并改这条路径)};`jmhrun`(JMH);`PGI`(本机 PostgreSQL 16 实例,端口 9501)、`MYI`(MySQL);`jpal.py` 是 JPA / Hibernate 6.6.4 的辅助(`jpa(name, files, classes, …)`:生成 persistence.xml、`-parameters` 编译、`-Dorg.jboss.logging.provider=jdk`)
- `lib.py` 里 `mkartj(name, n, tags, desc, lead, facts[3], items, steps, refs, demo_title)` 渲染一篇文章,`ENV_J` 是统一的环境说明;`lidx(lines, *子串)` 给终端面板的 mark / done 定位,**子串匹配不到时会往 stderr 打 `[lidx 警告]`**(看到就要改)
- **`items` 数 == `out/jN.txt` 里行首 `== ` 的节数 == `steps` 数**(`S(k)` 与 steps 一一对应),不一致会 IndexError 或警告
- **文章里的数字必须从最终的 `out/jN.txt` 抄**:重跑实验会改数字(计时、指纹、字节数),读完数字之后不要再重跑
- 环境(没有随目录保存):JDK 17 / 21 / 27;OpenSSL 4.0.3;JUnit console-standalone 1.11.3(PIT / JaCoCo 用 1.9.2,没有 `execute` 子命令);Hibernate 6.6.4 + PostgreSQL 16;Jersey 3.1.9;ActiveMQ Artemis 2.37.0;Jetty 12.0.16;JaCoCo 0.8.12;PIT 1.17.1;BouncyCastle 1.78.1(含 bcpg);Gradle 9.8.0(#291 / #293 用,放在 scratchpad 的 `gradle/`,实验后删除);Maven 3.10.0;japicmp 0.23.1
- 禁区同上:不碰 5432、3306、6379、8181、9101、9333;自己起的服务用 9500 以上
- Docker:#239 之后本机有 Docker Desktop,但守护进程没配代理、拉不到 Docker Hub;`dpull.py <镜像:标签>` 在宿主机经 127.0.0.1:1087 下载 linux/arm64 镜像、打成 OCI tar 再 `docker load`(不改 Docker 的任何设置)。Testcontainers 1.20.4 连 Docker 29 要加 `-Dapi.version=1.44`(1.21.4 不用);用完 `docker rmi` 掉装入的镜像
- 小坑:JOL 在 macOS 上自我 attach 会让 JVM 停住,要加 `-Djol.skipHotspotSAAttach=true`(或改用 `Unsafe.objectFieldOffset`);`hdiutil` 要用 `bash -c` 调;slf4j 的 API 版本要与绑定一致;`ps eww` 在这台 macOS 上看不到环境变量;`FileChannel` 的锁在同一进程里关闭另一个指向同一文件的 channel 时会丢;PG 方言会忽略大于 0 的锁超时(会一直挂,用线程加超时去等);`System.setProperty("user.language", …)` 在启动后不起作用,`Locale.setDefault` 才会
- **scratchpad 在重启后会被清空**(`/private/tmp` 被清):工具(jl.py、lib.py、publish.py、rp_all.py、jpal.py)与实验已经同步到本目录,#238 之后的 `exp / art / out` 都在;**#1–#237 的 `exp / art / out`(含 #236、#237)在一次重启中丢失,文章仍在库里**,要改它们只能从库里读 body 再改
- 文章里写明的没有验证的东西:Testcontainers 只测了 postgres 一种容器、没测 reuse / Compose / Linux CI;只在 macOS arm64 上测过,Linux 特有的行为(cgroup、`/proc`、epoll、`TZ`)没有验证;#115 的串口用 pty 代替;预览特性(`--enable-preview`)的结果随 JDK 版本会变;jcstress 用的是快速模式;GraalVM 下载过又删除了
- 全部写完后,库里 java 系列 = 旧 140 + 新 294 篇;`content/tech/articles/java-*.html` 的 298 个旧草稿已经删除

## Kubernetes 系列(`k8s_topics.json`:编号 → slug、标题,url 是 `k8s-<slug>.html`;`python3 publish.py k1 k2 … [--save]`,共 105 篇;库里原有 6 篇旧文,新文章的显示序号 = 编号 + 6)
- 编号 `kN` 对应 `k8s_topics.json` 里的第 N 项;每篇 `exp/kN.py`(`from kl import *`,`tee('kN')` 把输出写进 `out/kN.txt`)→ `art/kN.py`(`from lib import *`,`S = SS('kN')`,`steps=[step(...)]`,`A = mkartk('kN', n, tags, desc, lead, facts[3], items, steps, refs, demo_title, PANELS)`)→ `publish.py kN`(只构建 `html/`)→ `publish.py kN --save`(入库 + public)→ 全部写完后 `publish.py --save --lists-only`
- `kl.py`:kind 实验辅助。`up('main')` 起/复用集群 `kx-main`(1 控制面 + 2 worker,Kubernetes v1.37.0,节点镜像 kindest/node:v1.37.0,containerd 2.3.4,cgroup v2 + systemd 驱动),`up('sched', cfg=config(workers=4))` 是 5 节点的 `kx-sched`,另有 `kx-evict`(k31)、`kx-audit`(k18,配置在 `ktmp/audit/`)、`kx-enc`(k59)、`kx-ipvs` / `kx-nft`(k66,用 `networking.kubeProxyMode`),用完 `down(name)`;`k() / ko() / kj()` 包 kubectl(每条都显式带 `ktmp/` 下的 kubeconfig,`KUBECACHEDIR` 指到 `ktmp/kcache`,不碰 `~/.kube`);`nx(node, cmd)` 是 `docker exec` 进 kind 节点;`load(image)` 在宿主机经代理下载镜像再 `kind load`(节点自己拉不到仓库;`dpull.py` 拉 Docker Hub,`kpull.py` 拉 registry.k8s.io);`pod_cgroup / container_cgroup / cgread` 读节点上的 cgroup;`install_metrics_server()`(v0.7.2,采集周期 15 秒);`kweb.py` 是集群里的 Python HTTPS webhook / 转换服务(k2、k4)
- Go 程序放在 `ktmp/<name>/`(`go.mod` + client-go v0.36.1,下载时设 `https_proxy=http://127.0.0.1:1087`,运行时去掉代理):k89 `informer`、k90 `workq`
- 页面检查:先在 `ktmp/site` 起 `python3 -m http.server 9801 --directory ktmp/site`,再 `python3 chk.py k8s-xxx.html …`(无头 Chrome 逐个点完每个演示的所有步骤,报空面板 / JS 错误 / 横向溢出;读 `html/` 目录,要先 `publish.py kN` 构建);`python3 shot.py <html> <步> <png>` 截图。全部 105 篇都跑过,没有问题
- **`items` 数 == `out/kN.txt` 里行首 `== ` 的节数 == `steps` 数**,不一致会报 `[段数不一致]`;`lidx` 匹配不到子串会往 stderr 打 `[lidx 警告]`;`fl()` 没有 `dim` 参数,要用 `dict(fl(...), dim=[..])`;自定义流程图面板要把 `PANELS` 作为 `mkartk` 的最后一个参数,漏了会退回默认面板
- **文章里的数字必须从最终的 `out/kN.txt` 抄**:重跑实验会改数字(计时、IP、uid),写完 `art/kN.py` 之后别再重跑;写 art 之前先 `cat out/kN.txt`
- 小坑:YAML 里 `y` / `n` / `yes` / `no` / `true` 会被当布尔(容器名、标签值、`values:` 里都踩过);flow 样式的双引号字符串里写 `\n` 会被折叠成空格,命令用 `json.dumps` 生成;kind 节点的 `/tmp` 是 tmpfs,`docker cp` 到 `/tmp` 会静默失败,用 `/root`;新建集群后 worker 还是 NotReady,要 `wait_nodes_ready()`;busybox 的 `nslookup` 对带点的名字不展开 search 域,要写完整域名;`kubectl logs -l` 多副本按 Pod 分组,要加 `--timestamps` 才能按时间排序;`/proc/net/ip_vs` 的条目数不可靠;f-string 里嵌套引号很容易出错,先算出变量再 print;改 `exp` 里的截断点别用 `s.index("down('x')")`(会取到文件开头的同名调用,整个脚本被复制一遍)
- 容器内无法访问外网:要用的镜像先 `load()`;访问 docker.io 的连接是黑洞(不通也不拒绝,拉取要等到超时),要快速失败的"拉不到"用 `localhost:5999` 这类没有服务的地址;要可控的仓库行为,在 worker 上用 hostNetwork Pod 起一个 Python 假仓库并给节点写 `/etc/containerd/certs.d/localhost:5000/hosts.toml`(k96、k97)
- 文章里写明的没有验证的东西:多控制面节点、真实云环境(LoadBalancer、云盘)、其他 CNI(Calico / Cilium)与运行时(CRI-O、Kata、gVisor)、IPv6 / 双栈、Windows 节点、大规模(几千个对象)下的性能、各种参数在不同 Kubernetes 版本里的差异;只在 macOS arm64 + Docker Desktop 的 kind 上测过,节点是共享同一台机器的容器,延迟、磁盘等数字不代表真实环境
- 做完后清理:`kind get clusters` 应只剩 `kx-main`、`kx-sched`(用 `down_all()` 或 `kind delete cluster --name …` 删除),关掉 9801 的 http.server

## Gin 系列(`gin_topics.json`:编号 → slug、标题,url 是 `gin-<slug>.html`;`python3 publish.py n1 n2 … [--save]`,共 52 篇;库里原有 4 篇旧文,新文章的显示序号 = 编号 + 4;Series `gin` / `Gin 框架内部原理` / `#C23B6B`)
- 编号 `nN` 对应 `gin_topics.json` 里的第 N 项;每篇 `exp/nN.py`(`from nl import *`,`tee('nN')` 把输出写进 `out/nN.txt`,行首 `== ` 分节)→ `art/nN.py`(`from lib import *`,`S = SS('nN')`,`A = mkartn('nN', N, tags, desc, lead, facts[3], items, steps, refs, demo_title)`)→ `publish.py nN`(只构建 `html/`)→ `publish.py nN --save`(入库 + public)→ 全部写完后 `publish.py --save --lists-only`。`items` 数 == `out/nN.txt` 的 `== ` 节数 == `steps` 数。`lib.py` 里加了 `NTOPICS`、`OFF['gin']=4`、`SERIES_COLORS['gin']`、`mkartn`、`ENV_N_GIN`,`publish.py` 的前缀字符加了 `n`。
- `nl.py`:Gin v1.12.0 + Go 1.27.1。模块缓存在 `gtmp/_gopath`(GOPROXY=off;`gtmp` 被删除后用 `python3 -c "import nl; nl.setup()"` 重新准备(下载 Gin v1.12.0 与依赖,要代理 127.0.0.1:1087)),`gin(name, 源码或 {文件: 内容}, args, env, race, patched)` 写 → `go build` → 运行(默认 `GIN_MODE=release`,`env=dict(GIN_MODE='debug')` 看调试输出),`out_lines(r)` 打印结果;`gtestn(...)` 跑 `go test`;`gsrcl(文件, 起, 止)` / `gfunc(文件, 函数名)` / `gfind(文件, 正则)` 把 Gin 自己的源码带行号原样打印进输出(模块缓存里的原文)。`patched=True` 用 `gtmp/gin_patched`(Gin 源码副本 + `zz_dump.go`,由 `nl_patch.py` 生成,只提供只读的 `DumpTree(method)` / `TreeMethods()`),看 Engine 内部的路由树时用。
- 用真实进程的实验(n47 优雅关机、n48 h2c / TLS / unix socket、n51 自定义方法、n52 goroutine panic、n43 的 r.Run)在 `exp` 里自己 `go build` 出二进制,用 Python 的 `subprocess` 起进程、`curl`(8.7.1,带 nghttp2)和 `urllib` 当客户端,端口 9731–9780;其余实验是进程内的 `httptest`(请求的 RemoteAddr 默认 192.0.2.1)。
- 小坑:Go 源码里 import 必须在其它声明之前(拼接公共前缀 + 代码时注意,不用的 import 要写 `var _ = pkg.X`);`lib.san()` 会把 `192.168.x.x` 换成占位符,实验里别用这个网段(用 172.16 / 10.x / 203.0.113.x);art 里 `facts` / `lead` 是原始 HTML,里面不能有字面量 `<script>`(要写 `&lt;script&gt;`,否则 publish 的内联脚本检查会失败);`lidx` 的子串必须真的出现在 `out` 里(`[lidx 警告]`);基准实验耗时很长(>120 秒会被放进后台),跑基准时不要同时编译别的东西,否则数字会被干扰;跑完 `exp` 后别再 `cat out`(重复输出),看结果用 `grep -v` 时注意别把形如 `    | ` 的行也过滤掉;`go test` 里 `gin.Mode()` 默认是 debug。
- 页面检查:`python3 -m http.server 9801 --directory ktmp/site` 后 `python3 chk.py gin-xxx.html …`;52 篇都跑过,没有问题。
- 文章里写明的没有验证的东西:除 macOS arm64 + Go 1.27.1 + Gin v1.12.0 之外的版本与平台、真实反向代理 / 浏览器 / 其它 HTTP 客户端、sonic / jsoniter 等替代 JSON 库(构建标签)、Windows、多核并发下的吞吐。
- 做完后清理:`gtmp/`(模块缓存与每个实验的临时目录,实验目录与构建缓存可达几 GB;只留 `_gopath`(约 200 MB 模块缓存)、`gin_base`、`gin_patched` 就能离线重跑,其余可随时删除,需要时 `nl.setup()` 重新生成)、关掉 9801 的 http.server。

## Git 系列(`git_topics.json`:编号 → slug、标题,url 是 `git-<slug>.html`;`python3 publish.py l1 l2 … [--save]`,共 74 篇;库里原有 4 篇旧文,新文章的显示序号 = 编号 + 4;Series `git`)
- 编号 `lN` 对应 `git_topics.json` 里的第 N 项;每篇 `exp/lN.py`(`from ll import *`,`tee('lN')` 把输出写进 `out/lN.txt`,行首 `== ` 分节)→ `art/lN.py`(`from lib import *`,`S = SS('lN')`,`A = mkarti('lN', N, tags, desc, lead, facts[3], items, steps, refs, demo_title)`;items == steps == out 的 `== ` 节数)→ `python3 publish.py lN`(看有没有 `[lidx 警告]` / `[段数不一致]`)→ `--save`;全部写完后 `python3 publish.py --save --lists-only`。
- `ll.py`:系统 git 2.54.0(Apple Git-157)+ Python 3.14,macOS arm64。实验目录 `ltmp/<name>/`,HOME 与全局 gitconfig 隔离在 `ltmp/_home`(`maintenance.auto=false`、`gc.auto=0`、`pack.threads=1`,否则自动维护会悄悄合并 pack、多线程 repack 不可复现);作者 Alice、时间固定(`t=N` 是 +N 分钟),hash 可复现。解析器:`parse_pack` / `apply_delta` / `obj_sha` / `ewah` / `parse_index`;`fast_import(d, n, merges_every, fname)` 一口气造大量提交。
- 小坑:reflog / gc / 时间相关的实验提交要用 `t='now'`(固定的 2026-01-01 对 gc 来说早已过期,其输出的 hash 会变,art 里别引用);重跑已完成的 exp 会改计时数字,别重跑;fast-import 里在自己上面接提交要写 `from <ref>^0`;sed 的替换里有 `/` 时换分隔符、`run()` 带 `errors='replace'`;fsmonitor 实验前后要 `pkill` 守护进程;`ltmp/_basic_git_server.py` 是 l71 的 Basic-auth http-backend 服务;zsh 里 `git $opts` 不会拆词,要拆的命令用 `bash -c`。
- 页面检查:`python3 -m http.server 9801 --directory ktmp/site` 后 `python3 chk.py git-xxx.html …`;74 篇都跑过,没有空面板 / JS 错误 / 溢出。
- 文章里写明的没有验证的东西:除 macOS arm64 + git 2.54.0(Apple Git-157)之外的版本与平台(Linux 文件系统、Windows)、真实远程服务(GitHub 等)与网络环境、真正百万级的大仓库、各篇列出的细节。
- 做完后清理:`ltmp/`(实验目录可达数 GB;只留 `_home`、`_ssh` 和小的辅助文件,其余可随时删除)、关掉 9801 的 http.server 与 `_basic_git_server`、fsmonitor 守护进程。

## MongoDB 系列(`mongo_topics.json`:编号 → slug、标题,url 是 `mongo-<slug>.html`;`python3 publish.py m1 m2 … [--save]`,共 80 篇;库里原有 8 篇旧文,新文章的显示序号 = 编号 + 8;Series `mongo` / `MongoDB` / `#1C7C74`)
- 编号 `mN` 对应 `mongo_topics.json` 里的第 N 项;每篇 `exp/mN.py`(`from ml import *`,`tee('mN')` 把输出写进 `out/mN.txt`,行首 `== ` 分节,`reset()` 杀掉上次遗留的 mongod)→ `art/mN.py`(`from lib import *`,`S = SS('mN')`,`A = mkartm('mN', N, tags, desc, lead, facts[3], items, steps, refs, demo_title)`;`items` 与 `steps` 的个数必须等于 out 里 `== ` 小节数,`publish.py` 会报 `[段数不一致]`,`[lidx 警告]` 是高亮锚点没匹配上)。写 art 前先数 out 的小节数,且数字一律取自最后一次运行的 out(重跑会改计时数字)。
- `ml.py`:MongoDB 9.0.2(Homebrew mongod / mongos)、mongosh 2.12.0、mongodump / mongorestore / mongostat / mongotop 100.16.1、pymongo 4.18.3(虚拟环境 `mtmp_venv`,用 `mtmp_venv/bin/python exp/mN.py` 运行)。实验目录 `mtmp/<name>/`,端口 9900 起,mongosh 的 HOME 在 `mtmp/_home`(关遥测)。提供 `Node`、`ReplSet(name, n)`、`Cluster(name, shards, chunk_mb).start()`(配置副本集 + 分片副本集 + mongos)、`msh`(打印 mongosh 真实输出,`note=` 加注释行)、`jv`、`bench`(中位数)、`fm`、`fill`。副本集 / 分片实验用 `enableTestCommands` + failpoint(`stopReplProducer`、`failCommand`)造复制延迟与重试;不带 lsid 的游标、retryable write 去重这类驱动会绕开的行为,用手写 OP_MSG 客户端;FTDC 用自己写的解码器。
- 小坑:macOS 上 mongod 不支持 `--fork`(用 Popen);线程要 `daemon=True`,否则异常会让进程挂住;每个实验结束 `rm -rf mtmp/<name>`(磁盘紧张,`_home` 要留);mongod 的连接上限参数是 `--maxConns`;9.0 里 `system.buckets.*` 不能直接访问(用 `rawData: true`);oplog 在实验里从不被截断,所以 ChangeStreamHistoryLost 用刚同步的成员造;`numInitialChunks` 在 9.0.2 里没有效果;`$where` 的 `sleep(N)` 单个操作会跑约 2.5 倍的时间;mongostat 的 qrw / arw 和 serverStatus 对不上;art 里的 lidx 不要匹配 `== X` 标题行(会被剥掉)。
- 页面检查:`python3 -m http.server 9801 --directory ktmp/site` 后 `python3 chk.py mongo-xxx.html …`;80 篇都跑过,没有空面板 / JS 错误 / 溢出,`<p>` 都是平衡的。
- 文章里写明的没有验证的东西:除 macOS arm64 + MongoDB 9.0.2 之外的版本与平台(Linux 的 ext4 / XFS、内存与 CPU 行为)、真实多机网络、Atlas / 云环境、大规模数据下的性能、TLS / x.509 / LDAP、各篇列出的细节;计时和空间数字来自单台笔记本上的多个 mongod 进程,不代表生产环境。
- 做完后清理:`mtmp/`(只留 `_home`,其余可随时删除)、关掉 9801 的 http.server 与遗留的 mongod / mongos。

## Scrapy 系列(`scrapy_topics.json`:编号 → slug、标题,url 是 `scrapy-<slug>.html`;`python3 publish.py s1 s2 … [--save]`,共 50 篇;新建 Series `scrapy` / `Scrapy 内部原理` / `#2F8F4E`,库里原来没有旧文,显示序号 = 编号)
- 每篇 `exp/sN.py`(`from sl import *`,`tee('sN')` 把输出写进 `out/sN.txt`,行首 `== ` 分节)→ `art/sN.py`(`from lib import *`,`S = SS('sN')`,`A = mkarts('sN', N, …)`,items == steps == 小节数)。`bars()` 的第二个值是真实数值、第四个参数是最大值(宽度 = 值 / 最大值);写完每篇跑 `python3 chknum.py sN` 核对 art 里的数字是否都在 out 里(重跑 exp 后数字会变,必须以最后一次 out 为准)。
- `sl.py`:在 `stmp_venv`(Scrapy 2.19.0 / Twisted 26.4.0 / Python 3.14.8;pip 默认的清华镜像连不上,要 `-i https://pypi.org/simple`;另装了 uvloop 0.23.0、h2 4.4.1)里跑实验;`Srv`(来自 `pl.py` 的本机测试服务器)、`Track`(服务器端按 Host 记并发峰值与到达时间)、`sdir` / `write` / `scrapy` / `runspider` / `py` / `stats` / `ev` / `keep`;spider 文件开头自动带 `EV()` 往 `events.jsonl` 记事件;`runspider` 默认关掉 telnet 与 remote control;`env` 参数里值为 `None` 表示从子进程环境里删掉该变量(`pl.py` 会往环境里塞 `NO_PROXY=127.0.0.1,localhost`,做代理实验要清掉)。
- 小坑:每篇都要读 `stmp_venv/lib/python3.14/site-packages/scrapy` 的源码核实,不能凭旧版本印象;不要写没有源码依据的“2.19 新增”(只有 docstring 里有 `versionadded` 才能写版本);`signals.connect` 只存弱引用,实验里的局部函数要自己持有;mac 上用 python 做文本替换,别用 `sed -i`;`publish.py --save` 偶尔 database is locked,重试即可。
- 这个系列实测出的几个与文档或直觉不一致的结果(都在对应文章里):2.19.0 默认的 asyncio reactor 下 `CONCURRENT_REQUESTS_PER_DOMAIN` / `PER_IP` / `DOWNLOAD_SLOTS` 的并发限制拦不住一次性涌入的请求(SelectReactor、无 reactor、aiohttp 处理器下生效);`start_requests()` 被完全忽略且没有警告;`start()` 不是惰性消费;`FormRequest.from_response` 已弃用且会带上 disabled 字段;`HTTPAUTH_DOMAIN` 匹配含端口的 netloc;`CloseSpider` 只在回调和 `start()` 里生效;async 信号处理函数只对用 `send_catch_log_async` 触发的信号运行。
- 页面检查:`python3 -m http.server 9801 --directory ktmp/site` 后 `python3 chk.py scrapy-xxx.html …`;50 篇都跑过,没有空面板 / JS 错误 / 溢出,正文里的 `<p>` 平衡。
- 文章里写明的没有验证的东西:除 macOS arm64 + Scrapy 2.19.0 之外的版本与平台、真实网络与真实网站、大规模数据、各篇列出的细节;计时和内存数字来自单台笔记本上的本机回环服务器,不代表生产环境。
- 做完后清理:`stmp/`(用 `python sl.py` 清空)、`ptmp/nx_*`、关掉 9801 的 http.server 与遗留的 nginx / scrapy 进程;`stmp_venv` 保留。

## RabbitMQ 系列(`rabbitmq_topics.json`:编号 → slug、标题,url 是 `rabbitmq-<slug>.html`;前缀 `q`:`python3 publish.py q1 q2 … [--save]`,共 36 篇;新建 Series `rabbitmq` / `RabbitMQ 内部原理` / `#D9531E`,库里原来没有旧文,显示序号 = 编号)
- 每篇 `exp/qN.py`(`from ql import *`,`tee('qN')` 把输出写进 `out/qN.txt`,行首 `== ` 分节;用 `qtmp_venv/bin/python exp/qN.py` 运行)→ `art/qN.py`(`from lib import *`,`S = SS('qN')`,`A = mkartq('qN', N, …)`,items == steps == 小节数,`bars()` 用真实数值)。写完每篇跑 `python3 chknum.py qN`。
- `ql.py`:Homebrew 的 RabbitMQ 4.3.6(Erlang/OTP 28)本机多节点助手——`Node`(独立数据目录 / 配置 / 端口 9500+ / 节点名 `名字@localhost`,`HOME=qtmp/_home` 自己的 cookie,不读全局配置)、`.ctl()` / `.sh()`(真实 rabbitmqctl 输出)、`.qinfo()`(用 rabbitmqctl 实时读队列字段;管理 API 的统计有 5 秒延迟)、`.api()`(管理 API)、`cluster(name, k)`(k 节点集群)、`Proxy`(自己写的 AMQP 0-9-1 帧解析 TCP 代理,支持黑洞 / 单向延迟 / 断开)、`async_publish()`(带 confirm 的异步发布基准)、`KafkaNode`(Homebrew Kafka 4.3.1 单节点 KRaft,仅 q34 用)。`qwork.py`、`qcons.py` 是多进程发布 / 消费子进程。pika 1.4.4、aio-pika、confluent-kafka 装在 `qtmp_venv`(pip 要 `-i https://pypi.org/simple`)。
- 实测出的与旧印象不一致的结果(都在对应文章里):默认不允许“非持久、非排他”的队列(541,整条连接被关);ha-mode 镜像策略已移除;`global_qos` 默认被拒绝但 `basic.qos(global=True)` 不报错、按每消费者处理;非持久 exchange 重启后仍在、非持久队列被清;transient 与 persistent 消息写盘量相同;quorum 队列按完整 0–255 优先级排序但不能带 `x-max-priority`;`x-consumer-timeout` 队列参数经典队列返回 406;`pause_minority` 在 4.3.6 上没让少数派节点暂停;经典队列所在节点被杀后客户端访问要等约 66 秒才 404。
- 没能验证的(文章里如实写了):`consumer_timeout` 配成 5/10 秒、等 4~7 分钟也没观察到 channel 被关(q24);这台 macOS 上 broker 读不到磁盘剩余空间,磁盘告警无法触发(q20);fd / socket / disk_free 的读数在 macOS 上是 0(q31)。
- 小坑:后台跑实验用 `(cmd; echo done > /tmp/xdone) &` 加 Monitor 等标志文件,不要在前台 sleep;`reset()` 会杀掉 `qtmp/` 下所有节点,同一时间只能跑一个实验;真分区的做法是改被隔离节点自己的 Erlang cookie 并断开连接(rabbitmqctl 用 `--erlang-cookie` 访问它);`rabbitmqctl close_connection` 要传 pid;计数类实验要在停止消费者之前取快照(停止时卡住的消息会回队列被别人拿走);基准一律交替多轮取中位数。
- 页面检查:`python3 -m http.server 9801 --directory ktmp/site` 后 `python3 chk.py rabbitmq-xxx.html …`;36 篇都跑过,没有空面板 / JS 错误 / 溢出,正文里的 `<p>` 平衡。
- 文章里写明的没有验证的东西:除 macOS arm64 + RabbitMQ 4.3.6 之外的版本与平台、真实多机网络、Linux 上真实 fsync 与磁盘、TLS、大规模连接与队列;计时数字来自单台笔记本上的本机回环。
- 做完后清理:`qtmp/`(整体可删,先 `pkill -f qtmp/`)、`ktmp` 不动、关掉 9801 的 http.server;`qtmp_venv` 保留。

## 网络协议系列(`network_topics.json`:编号 → slug、标题、分组,url 是 `network-<slug>.html`;前缀 `w`:`python3 publish.py w1 w2 … [--save]`,共 105 篇;新建 Series `network` / `网络协议原理` / `#40678F`,库里原来没有旧文,显示序号 = 编号)
- 九组:基础与链路层(w1–8)、IPv4 与 ICMP(w9–22)、IPv6(w23–27)、UDP 与组播(w28–36)、TCP(w37–65)、DNS(w66–73)、HTTP 与 Web 协议(w74–89)、TLS 与安全传输(w90–97)、其它常见协议(w98–105)。
- 每篇 `exp/wN.py`(开头 `sys.path.insert(0, 上级目录)`,`from netl import *`,`tee('wN'); reset()`;用 `wtmp_venv/bin/python exp/wN.py` 运行)→ `out/wN.txt`(行首 `== ` 分节)→ `art/wN.py`(`from lib import *`,`S = SS('wN')`,`A = mkartw('wN', N, …)`,**items == steps == out 里 `== ` 节数**,否则 `publish.py` 报“段数不一致”)。写完每篇跑 `python3 chknum.py wN` 核对数字都来自 out。`exp/` 下有旧系列遗留的 `h2.py` 会遮住 `h2` 库,用到 `h2` 的脚本开头要把 `exp/` 从 `sys.path` 去掉。
- `netl.py`:`Cap(...)`(后台 tcpdump,`write=True` 写 pcap,`dpkt` 解析)、`lossy(loss, delay, bw)`(调用 netlab)、`lab_port()`、`tcp_info(sock)`(macOS 的 TCP_CONNECTION_INFO)、`sysout/sysrun`(经 `sysd.py` 执行 arp / ndp / netstat / ifconfig / sysctl 等系统命令:Homebrew 的 python 里这些命令看不到邻居表,所以每个会话先 `nohup /usr/bin/python3 tools/articles/sysd.py &`)、`reset()`(杀掉所有 tcpdump、关掉 netlab)。`lib.py` 的 `san()` 会把任何完整的 192.168.x.y 换成“<本机局域网IP>”。
- **需要的本机权限**:抓包需要 `/dev/bpf*` 可读(用户跑过 `osascript … chmod o+r /dev/bpf*`,**重启后失效**,失效了要重跑);netlab 是我装的 dummynet 辅助脚本 `netlab_src/netlab`(装到 `/Library/netlab/netlab` 和 `/etc/sudoers.d/netlab`,只管 lo0 的 TCP/UDP 端口 9400–9499,丢包上限 50%、延迟 ≤ 1000 ms)。**卸载**:先 `sudo /Library/netlab/netlab off`(清掉 dummynet 管道与 pf 锚点、恢复 /etc/pf.conf),再 `sudo rm -rf /Library/netlab /etc/sudoers.d/netlab`。
- 实测出的与旧印象不一致的结果(都在对应文章里):`netstat -s -p tcp` 的 TCP 计数全是 0;macOS 拒绝自连接(`EINVAL`)、`TCP_MAXSEG` 在 connect 前设置返回 `EINVAL`、清除 `TCP_NOPUSH` 不会冲出缓冲的数据、`SO_REUSEPORT` 没有负载均衡(全给最后绑定的监听者);全连接队列满时服务端仍回 SYN-ACK 随后 RST;客户端内核会悄悄停用对某目的地的 TCP Fast Open;`keepalive` 探测包不带时间戳选项;Python 默认 ClientHello 带 `X25519MLKEM768`;Python 默认不检查证书吊销;example.com(Cloudflare)关闭 0-RTT、忽略 `Accept-Encoding` 里的 `q=0`、检查 SNI 与 Host 一致、对多段 Range 返回 200。
- **环境里的网络干预(文章里如实写了,只限这台机器所在的网络)**:对部分域名(如 www.bbc.co.uk)的明文 UDP 53 查询,应答被路径上的设备抢先伪造(几 ms 内到达、答案互相矛盾、带 RA 位),连 DoT / DoH 到阿里解析器拿到的也是同一类异常地址;Cloudflare / Google / Quad9 / AdGuard 的 DoT(853)与 DoH(443)全部连不上,只有阿里 223.5.5.5 通;www.google.com 的 UDP 443 不通。
- 没能验证的(文章里如实写了):w21 向局域网发过一次 DHCPDISCOVER(伪造 MAC,没发 REQUEST);w105 的 IPIP 隧道没测、外层 IPv6 的额外字节是计算值;DNS 应答被路径设备伪造 / Cloudflare 等 DoT、DoH 连不上的来源(要换出口对照,**仍未验证**);w60 里 macOS 的 `net.inet.tcp.clear_tfocache` 没有试(没给它免密权限)。
- **后来补测的(系列写完之后)**:w105 改成在 Docker Desktop 的 Linux 虚拟机里(两个容器 ta/tb,`wtmp_lab/` 里是 Dockerfile 和辅助脚本)建真的 GRE / VXLAN / WireGuard / IPsec ESP 隧道,实验是 `exp/w105.py`(旧版保留为 `exp/w105_old.py`);**在这个 Docker 虚拟机里创建 ipip 接口会让 Docker 后端崩溃**(要 `open -a Docker` 重启),所以排除了;VXLAN 不指定 `dev` 时接口 MTU 是 1500 而不是 1450;内核对 VXLAN 会学到路径 MTU 例外(`ip route show cache`,约 600 秒),测 TCP 的 MSS 前要删掉再加回直连路由(两端都要)才能清掉。w86 补测:**最初版本的 session ticket 回调写进了 `QuicConfiguration`,aioquic 悄悄忽略,正确写法是传给 `connect(session_ticket_handler=...)`**;example.com 能会话恢复但 ticket 不允许 early data;本机 aioquic 服务端上 0-RTT 实测省一个往返;3% 丢包下 aioquic 对 aioquic 14606 ms,换成 curl 8.22 + Caddy 2.11 后 HTTP/3 964 ms、HTTP/2 702 ms。补测用到的脚本是 `exp/w86b.py`(本机 0-RTT 和 2×2 对照)与 `exp/w86c.py`(对 example.com 的会话恢复),它们的输出合并进了 `out/w86.txt`(顺序:一 二 三[w86c] 四 五[原第四节] 六[w86b])。补测装了 `brew install curl caddy`(curl 是 keg-only,路径 `/opt/homebrew/opt/curl/bin/curl`;卸载:`brew uninstall curl caddy && brew autoremove`);Docker 镜像 `netlab-tun`、`netlab-tun2` 已删,需要时用 `wtmp_lab/Dockerfile`、`Dockerfile2` 重建。
- 补测 w86 时 `curl --http3-only` 的 `--resolve localhost:PORT:127.0.0.1` 必须写;Caddy 要在全局选项里加 `skip_install_trust`,否则 `tls internal` 会尝试把根证书装进系统信任库。
- 小坑:后台跑实验用 `(cmd; echo done > /tmp/wNdone) &` 加 Monitor 等标志文件,不要在前台 sleep;`reset()` 会杀掉所有 tcpdump 并关闭 netlab,同一时间只能跑一个实验;dummynet 会让同一个包在 lo0 上被抓到多份,统计前按 (源端口, 序号, 标志) 去重;抓 en0 时 mDNS 会带进整个局域网的设备名和地址,**必须过滤成 `src host <本机IP>` 再只保留自己的包**;quoted heredoc 里写换行要用单个反斜杠;Python 里 `except socket.timeout` 会吞掉 `ETIMEDOUT`(它也是 TimeoutError),要看 `e.errno`;`SSLContext` 恢复会话必须复用同一个对象。
- 页面检查:`python3 -m http.server 9801 --directory ktmp/site` 后 `python3 chk.py network-xxx.html …`(每批 6 个);105 篇都跑过,没有空面板 / JS 错误 / 溢出,正文里的 `<p>` 平衡。
- 做完后清理:`wtmp/`(抓包文件,整体可删)、`pkill -f sysd.py`、关掉 9801 的 http.server;`wtmp_venv` 保留。
- **w60 TCP Fast Open 补测(用户给了 root 权限之后)**:用户在自己终端装了一个只允许 4 件事的免密脚本 `/Library/netlab/tfolab`(`mode 0-3` 设 `net.inet.tcp.fastopen`;`key <32 位十六进制>` 设 `net.inet.tcp.fastopen_key`,读回永远是空的;`alias add|del 1-50` 在 lo0 增删 `127.77.0.N`;`show`)和 `/etc/sudoers.d/tfolab`。**卸载**:`sudo rm -f /Library/netlab/tfolab /etc/sudoers.d/tfolab`。`fastopen_key` 是我设的值,重启后恢复,测完 `mode` 已设回 3。实验:`exp/tfo_common.py`(共用函数)、`w60b.py`(干净对照 + 密钥轮换)、`w60c.py`(30% 丢包触发停用)、`w60e.py`(停用范围 + 每 60 秒轮询 40 分钟)、`w60d.py`(Docker 里 Linux 对照/重放/丢弃带数据的 SYN,镜像 `netlab-tfo` 由 `wtmp_lab/Dockerfile.tfo` 构建,`tfo_srv.py` `tfo_cli.py` 是辅助);`out/w60.txt` 是 `exp/merge60.py` 合并的(一/三/四/五 来自 `out/w60_base.txt`,即旧的 `exp/w60.py` 输出,别重跑 `exp/w60.py` 覆盖)。发现:macOS 在 SYN 带数据重传 3 次(30% 丢包下)后对**该目的地址**停用 TFO(换端口无效,别的地址不受影响),至少 40 分钟不恢复;服务端换密钥后旧 cookie 被拒、SYN+ACK 带新 cookie、数据握手后重发不丢;Linux 容器里对不支持的服务端安全回退、SYN 数据可被重放(重放前要重算校验和,出站抓包的 TCP 校验和是卸载占位值)、带数据的 SYN 被丢弃时每个连接多等约 1 秒,且这个虚拟机内核的 `tcp_fastopen_blackhole_timeout_sec` 是 0。
