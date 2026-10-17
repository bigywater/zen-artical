from lib import *
S = SS('m69')
steps = [
    step("三个分片,分片键 {region, uid}。addShardToZone 把 sh0 标成 EU、sh1 标成 US,sh2 不加区域;updateZoneKeyRange 声明键范围:region = 'eu' 的 [{eu, MinKey}, {eu, MaxKey}) 属于 EU,region = 'us' 的属于 US。config.shards 里 tags 是 sh0 ['EU']、sh1 ['US']、sh2 空;config.tags 里有这两条范围。", t=tl(S(1)), mark=lidx(S(1), "('sh0', ['EU'])", 'config.tags', "('EU'"), done=lidx(S(1), "分片的 zone"), kv=KV([['zone', '分片的标签'], ['键范围', 'updateZoneKeyRange 声明'], ['无 zone 的数据', '不受约束']], ['zone'])),
    step("写入 3 个区域各 8,000 个文档(共 24,000,每个约 1 KB)。balancer 关着时它们全在 primary 分片 sh1 上:eu 8,000、us 8,000、apac 8,000。", t=tl(S(2)), mark=lidx(S(2), "('sh1', 'eu'): 8000"), done=lidx(S(2), '各分片上各区域的文档数'), kv=KV([['balancer 关着', '数据都在 primary 分片 sh1']], ['balancer 关着'])),
    step("打开 balancer:150 秒后 eu 区域的 8,000 个文档进了 sh0(sh0 拥有 8,000);us 区域本来就在 US 对应的 sh1 上,留在原地;apac(没有 zone)的 8,000 个里 6,951 个被平衡到 sh2、其余 1,049 个留在 sh1。各分片拥有的文档数(不含孤儿):sh0 8,000、sh1 9,049、sh2 6,951。(直连计数里 sh1 还有 eu 的 8,000——那是已经迁走、尚未清理的孤儿文档。)", t=tl(S(3)), mark=lidx(S(3), "'sh0': 8000", "('sh2', 'apac'): 6951"), done=lidx(S(3), 'balancer 开了'), b=bars([['sh0 拥有(eu)', 8000, '8,000'], ['sh1 拥有(us + apac 余)', 9049, '9,049'], ['sh2 拥有(apac)', 6951, '6,951']], 9049, mark=[0], done=[1, 2]), kv=KV([['eu', '迁到 EU 分片 sh0'], ['us', '留在 US 分片 sh1'], ['apac(无 zone)', '平衡到 sh2']], ['eu'])),
    step("chunk 在 zone 边界被切开:共 19 个 chunk,sh0 8 个、sh1 4 个、sh2 7 个;跨 region 的几个 chunk(如 [apac/868601189, eu/MinKey)、[eu/MaxKey, us/MinKey)、[us/MaxKey, MaxKey/MaxKey))正好落在 zone 范围之间的空隙里,eu 和 us 的数据都在以 zone 边界为端点的 chunk 里。", t=tl(S(4)), mark=lidx(S(4), '跨 region 边界的 chunk'), done=lidx(S(4), '共 19 个 chunk'), kv=KV([['zone 边界', '(eu, MinKey) (eu, MaxKey) …'], ['chunk', '不会跨越 zone 边界']], ['zone 边界'])),
    step("改 zone:sh2 加入 US、sh1 退出 US,15 秒后各分片拥有的文档数变成 sh2 14,951、sh0 8,000、sh1 1,049;sh2 上 us 区域的文档 8,000——US 数据跟着 zone 搬到了 sh2。", t=tl(S(5)), mark=lidx(S(5), '改 zone 后 15 秒'), done=lidx(S(5), 'sh2 上 us 区域'), kv=KV([['改 zone', '数据跟着搬,不需要重写数据'], ['us', 'sh1 → sh2 共 8,000 个']], ['改 zone'])),
    step("不属于任何 zone 范围的键(region = 'apac'):balancer 当作普通数据处理。直连计数 sh1 8,000(含已迁走未清理的孤儿)、sh2 6,951、sh0 0;各分片拥有的文档数总计 sh0 8,000、sh1 1,049、sh2 14,951。", t=tl(S(6)), mark=lidx(S(6), 'apac 的 8,000 个文档'), done=lidx(S(6), 'apac'), kv=KV([['无 zone 的键', '普通平衡'], ['孤儿文档', '直连计数含它们']], ['无 zone 的键'])),
]
A = mkartm('m69', 69, 'MongoDB,zone sharding,区域分片,addShardToZone,updateZoneKeyRange,真实验证,动画演示',
    '实测 zone sharding:给分片打 zone 标签并用 updateZoneKeyRange 声明键范围后,balancer 把 eu 的 8,000 个文档迁到 EU 分片、us 的留在 US 分片,没有 zone 的 apac 平均分到其它分片;chunk 在 zone 边界被切开;改 zone 后 us 的数据又跟着搬到新的分片。',
    '怎么让某个区域的数据落在指定的分片上?zone sharding 怎么配、balancer 怎么执行、改 zone 会怎样?这篇给 3 个分片打 EU / US 标签,按 region 前缀的分片键验证数据的迁移。',
    [('8,000', 'eu 区域迁到 EU 分片 sh0 的文档数'), ('19 个', '配置 zone 后 chunk 数:边界上被切开'), ('15 秒', '改 zone 后 US 区域 8,000 个文档搬到新分片 sh2 所用的时间')],
    [('配置', '<p><code>addShardToZone</code> 给分片打标签,<code>updateZoneKeyRange</code> 把分片键范围绑定到 zone。分片键必须以区域字段为前缀。</p>'),
     ('迁移', '<p>balancer 按 zone 把数据迁到对应分片:eu 迁到 EU 分片 sh0,us 留在 US 分片 sh1。</p>'),
     ('chunk 边界', '<p>chunk 在 zone 范围的端点被切开,每个 chunk 要么完全属于某个 zone,要么在空隙里。</p>'),
     ('改 zone', '<p>把 US 范围从 sh1 改到 sh2 后,balancer 自动把 8,000 个文档搬过去,应用不用改。</p>'),
     ('无 zone 的数据', '<p>不属于任何 zone 范围的数据(apac)按普通方式平衡。</p>'),
     ('孤儿', '<p>直连分片看到的文档数包含迁走后尚未清理的孤儿文档。</p>')],
    steps,
    [ENV_M + '。3 个分片(各为单节点副本集),chunk 1 MB;zone 的 EU / US 只是标签,本机并没有地域延迟',
     '没有验证:zone 范围与 chunk 迁移限速;没有 zone 的分片能否接收有 zone 的数据(这里 apac 分到 sh2 和留在 sh1,是否因为 sh1 是无 zone 约束尚未细究);zone 与 hashed 分片键(需要 presplitHashedZones);读偏好与 zone 的联动(就近读);删除 zone 范围后数据是否回迁'],
    'zone sharding')
