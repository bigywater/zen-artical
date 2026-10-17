from lib import *
def S(k): return [l for l in out('z6').split('== ')[k].splitlines()[1:] if l.strip()]
steps = [
    step("增改查:create /app hello → 「Created /app」;get /app → hello;set /app world 没有输出;get -s /app 多打印一整块 stat:cZxid=0x2、mZxid=0x5、dataVersion=1(改过一次)、dataLength=5、numChildren=0。ls / 列出 [app, zookeeper]——/zookeeper 是系统保留的节点。", t=tl(S(1)), kv=KV([['get -s', '数据 + stat'], ['/zookeeper', '系统保留节点']], ['get -s'])),
    step("子节点与递归:create /app/a、/app/b 后 ls -R /app 列出整棵子树;delete /app 在有子节点时报「Node not empty: /app」并以退出码 1 退出;要删整棵子树用 deleteall /app。", t=tl(S(2)), kv=KV([['delete', '只能删叶子节点'], ['deleteall', '递归删除']], ['deleteall'])),
    step("条件更新与错误:set -v 5 /v y(版本不对)→「version No is not valid : /v」;set -v 0 /v y 成功;get /nope →「Node does not exist」;create /v dup →「Node already exists」;create /a/b/c x(父节点不存在)→「Node does not exist」。ZooKeeper 不会自动创建父节点。", t=tl(S(3)), kv=KV([['-v 版本', '乐观锁:版本对才能改'], ['父节点', '不自动创建']], ['-v 版本'])),
    step("临时与顺序节点:create -e /tmp1 data 创建临时节点;create -s /job- x 返回 /job-0000000003、再来一次 /job-0000000004(10 位序号)。有意思的是 CLI 命令结束后,下一次 ls / 里 tmp1 还在——CLI 进程退出并没有立刻关闭会话,临时节点要等会话超时(第 8 篇量会话超时的时间)。", t=tl(S(4)), kv=KV([['-e', '临时节点,随会话'], ['-s', '顺序节点,10 位序号']], ['-e'])),
    step("其它:getAllChildrenNumber / 返回子孙节点总数(本例 7);ls -s / 同时显示 stat(cversion=5、numChildren=5);whoami 显示当前认证信息「Auth scheme: User / ip: 127.0.0.1」。help 里命令很多:addWatch、addauth、config、create、delete、deleteall、get、getAcl、getAllChildrenNumber……", t=tl(S(5)), kv=KV([['help', '列出全部子命令']], ['help'])),
]
A = dict(
    n=6, series='zookeeper', tags='ZooKeeper,zkCli,命令行,真实验证,动画演示',
    desc='用官方 ZooKeeperMain 逐条执行 create / get -s / set / ls -R / delete / deleteall / set -v / create -e / -s 等命令,看真实输出和错误信息:非空节点不能 delete、版本不对拒绝更新、父节点不自动创建,CLI 退出后临时节点还在会话超时之前。',
    lead='zkCli 是学 ZooKeeper 的第一个工具。这篇用官方的 ZooKeeperMain 类把基础命令挨个执行一遍,把每条命令的真实输出和各种错误信息记下来,方便以后对照。',
    facts=[('get -s', '一条命令同时得到数据和完整的 stat'), ('delete 只能删叶子', '非空节点报 Node not empty,要用 deleteall'), ('CLI 退出 ≠ 会话结束', '临时节点在下一次命令里还看得到')],
    body=[
        sec('增删改查', '', term('', blk('z6', 1))),
        sec('子节点与递归', '', term('', blk('z6', 2))),
        sec('版本号与错误信息', '', term('', blk('z6', 3)), '<p>失败命令的最后一行是 <code>Exiting JVM with code 1</code>,这是 ZooKeeperMain 在命令行模式下的行为:命令失败就以退出码 1 结束,写脚本时可以直接用退出码判断。</p>'),
        sec('临时节点与顺序节点', '', term('', blk('z6', 4))),
        sec('其它命令', '', term('', blk('z6', 5) + '\n' + blk('z6', 6))),
        sec('分步演示', '', demo('zkCli 命令', [('t', 'term', '输出'), ('kv', 'kv', '要点')], steps, '本步的对象')),
    ],
    refs=[ENV_Z + '。命令用 java -cp … org.apache.zookeeper.ZooKeeperMain -server 127.0.0.1:7300 <命令> 执行,每条命令一次连接(交互式 shell 里的 watch、会话内的临时节点行为与此不同);输出中的连接日志与空行已被去掉', '没有验证:交互式 zkCli.sh 的 tab 补全与历史、addauth / setAcl(第 71 篇)、config / reconfig(第 50 篇)、addWatch(第 15 篇)、quota 命令'],
)
