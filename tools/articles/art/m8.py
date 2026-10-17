from lib import *
S = SS('m8')
steps = [
    step("数据:100,000 条日志样的文档,msg 是从 300 个词里随机拼成的 12~23 个词,BSON 总大小 19,784,644 字节,平均 197 字节;样例 {_id, user, level, ts, msg, host}。同一份数据按同样顺序放进 4 个集合,每个集合 createCollection 时指定不同的 block_compressor。", t=tl(S(1)), mark=lidx(S(1), '样例'), done=lidx(S(1), 'user'), kv=KV([['文档数', '100,000'], ['BSON 总大小', '19,784,644 字节'], ['4 个集合', 'none / snappy / zstd / zlib']], ['4 个集合'])),
    step("插入并 fsync 后的 storageSize:none 20,647,936(104%,比 BSON 总大小还多一点),snappy 9,158,656(46%),zstd 6,217,728(31%),zlib 6,934,528(35%);磁盘上 .wt 文件的大小与 storageSize 一致。同一份日志样的数据,snappy 压到不到一半,zstd 压到约三分之一。", t=tl(S(2)), mark=lidx(S(2), 'zstd', 'zlib'), done=lidx(S(2), 'none', 'snappy'), b=bars([['none', 104, '104%'], ['snappy', 46, '46%'], ['zstd', 31, '31%'], ['zlib', 35, '35%']], 104, mark=[2], done=[0, 1]), kv=KV([['none', '104%'], ['snappy', '46%'], ['zstd', '31%'], ['zlib', '35%']], ['zstd'])),
    step("collStats 里能看到创建时的配置串:c_snappy 是 block_compressor=snappy,c_zstd 是 block_compressor=zstd;没有指定压缩算法的 c_default 是 block_compressor=snappy(启动参数 getCmdLineOpts 里没有设置压缩);索引的配置串是 block_compressor= 加 prefix_compression=true,prefix_compression_min=4——索引不用块压缩,用前缀压缩。", t=tl(S(3)), mark=lidx(S(3), 'c_default', '索引的 creationString'), done=lidx(S(3), 'c_snappy', 'c_zstd', 'getCmdLineOpts'), kv=KV([['集合默认', 'snappy'], ['索引', '前缀压缩,不用块压缩'], ['指定方式', 'createCollection 的 storageEngine.wiredTiger.configString']], ['集合默认'])),
    step("插入 100,000 个文档(20 批)的耗时:none 247 ms、snappy 242 ms、zstd 260 ms、zlib 274 ms——差别不大(数据在缓存里,压缩发生在后台写盘时)。", t=tl(S(4)), mark=lidx(S(4), 'zlib'), done=lidx(S(4), 'none', 'snappy', 'zstd'), b=bars([['none', 247, '247 ms'], ['snappy', 242, '242 ms'], ['zstd', 260, '260 ms'], ['zlib', 274, '274 ms']], 274, mark=[3], done=[0, 1, 2]), kv=KV([['插入耗时', '四种差别在 15% 以内'], ['原因', '写入先进缓存,压缩在写盘时(未单独验证)']], ['插入耗时'])),
    step("冷缓存全表扫描(重启 mongod 清空 WiredTiger 缓存后,3 轮顺序打乱取中位数):none 45 ms、snappy 37 ms、zstd 91 ms、zlib 88 ms。解压更重的 zstd 与 zlib 扫描时间约是 none/snappy 的两倍;snappy 和 none 几乎一样。操作系统的文件缓存仍是热的,没有测真正读磁盘。", t=tl(S(5)), mark=lidx(S(5), 'zstd', 'zlib'), done=lidx(S(5), 'none', 'snappy'), b=bars([['none', 45, '45 ms'], ['snappy', 37, '37 ms'], ['zstd', 91, '91 ms'], ['zlib', 88, '88 ms']], 91, mark=[2, 3], done=[0, 1]), kv=KV([['snappy', '省空间,扫描几乎不慢'], ['zstd / zlib', '更省空间,扫描约慢一倍'], ['注意', 'OS 缓存热,没测磁盘 IO']], ['snappy'])),
    step("可压缩性决定一切:同样 100,000 个文档,payload 换成 200 字节随机字节(BSON 总大小 22,200,000),各压缩算法的 storageSize 是 none 23,040,000(104%)、snappy 22,925,312(103%)、zstd 22,642,688(102%)、zlib 22,646,784(102%)——几乎没压缩。", t=tl(S(6)), mark=lidx(S(6), 'zstd', 'zlib'), done=lidx(S(6), 'none', 'snappy', '随机字节文档'), kv=KV([['随机数据', '压缩几乎无效'], ['日志样数据', 'zstd 压到 31%'], ['结论', '收益取决于数据本身']], ['结论'])),
]
A = mkartm('m8', 8, 'MongoDB,压缩,snappy,zstd,zlib,WiredTiger,真实验证,动画演示',
    '实测 WiredTiger 的块压缩:同样 100,000 个日志样文档,none、snappy、zstd、zlib 的 storageSize 是 BSON 总大小的 104%、46%、31%、35%;插入耗时差别不大,冷缓存扫描 zstd 与 zlib 约是 snappy 的两倍;随机数据几乎不可压缩;集合默认 snappy,索引用前缀压缩。',
    '同一份数据用 snappy、zstd、zlib 存,分别占多少磁盘?压缩有没有拖慢写入和扫描?这篇给每个集合指定不同的 block_compressor,用同一份 10 万条日志样的数据对比,再换成随机字节看压缩什么时候无效。',
    [('46% / 31%', 'snappy 与 zstd 下日志样数据的 storageSize 占 BSON 总大小的比例'), ('37 → 91 ms', '冷缓存全表扫描:snappy 对 zstd'), ('102%', '随机字节数据用 zstd 压缩后仍是 BSON 总大小的 102%')],
    [('数据与方法', '<p>10 万条日志样的文档(约 19.8 MB BSON),放进 4 个集合,<code>createCollection</code> 时用 <code>storageEngine.wiredTiger.configString</code> 指定 <code>block_compressor</code>。</p>'),
     ('占多少磁盘', '<p>none 比原始数据还多 4%(页面开销);snappy 压到 46%,zstd 31%,zlib 35%。</p>'),
     ('默认值与索引', '<p>不指定时集合用 snappy;索引不用块压缩,用前缀压缩(<code>prefix_compression=true</code>)。</p>'),
     ('写入耗时', '<p>插入 10 万个文档,四种算法都在 242~274 ms,差别不大。</p>'),
     ('读取耗时', '<p>清空 WiredTiger 缓存后全表扫描:snappy 与 none 接近,zstd 和 zlib 约慢一倍,因为解压更耗 CPU。</p>'),
     ('可压缩性', '<p>随机字节本身不可压缩,所有算法下都接近原始大小。压缩收益取决于数据重复程度,上线前要用自己的数据测。</p>')],
    steps,
    [ENV_M + '。数据由固定种子生成,每个集合只插入一次;冷缓存扫描是重启 mongod 后各测一次,3 轮取中位数,操作系统文件缓存仍然是热的',
     '没有验证:真正读磁盘(冷操作系统缓存)的扫描时间;更大数据集上的压缩比;zstd 的压缩级别配置;网络消息压缩(networkMessageCompressors)与日志压缩;journal 的压缩;不同数据形态(嵌套、长字符串、数值)下的压缩比;CPU 占用的具体数字'],
    '压缩算法对比')
