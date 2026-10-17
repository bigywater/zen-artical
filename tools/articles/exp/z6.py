import sys, os, time, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zkl import *
tee('z6'); R = {}
n = Node('z6', 7300).start()
def run(*cmds):
    outs = cli(7300, *cmds)
    for c, o in zip(cmds, outs):
        print(f'  [zk] {c}'); [print('      ' + l) for l in (o.splitlines() or ['(无输出)'])]
    return outs
print('== 一:增删改查:create / get / set / stat / delete(官方 ZooKeeperMain,每条命令一次连接)')
R['crud'] = run('create /app hello', 'get /app', 'set /app world', 'get -s /app', 'ls /')
print()
print('== 二:子节点与递归:create 子节点、ls -R、delete 非空节点、deleteall')
R['tree'] = run('create /app/a 1', 'create /app/b 2', 'ls -R /app', 'delete /app', 'deleteall /app', 'ls /')
print()
print('== 三:条件更新(版本号)与错误信息')
R['errors'] = run('create /v x', 'set -v 5 /v y', 'set -v 0 /v y', 'get /nope', 'create /v dup', 'create /a/b/c x')
print()
print('== 四:临时节点与顺序节点:-e / -s;注意 CLI 退出后再 ls,临时节点还在不在')
R['types'] = run('create -e /tmp1 data', 'ls /', 'create -s /job- x', 'create -s /job- x', 'ls /')
print()
print('== 五:查看节点数、配置、客户端身份')
R['misc'] = run('getAllChildrenNumber /', 'ls -s /', 'whoami')
print()
print('== 六:help 里的命令(前 12 个)')
h = cli(7300, 'help')[0].splitlines(); [print('  ', l) for l in h[:13]]; R['help'] = h[:13]
n.stop(); save('z6', R)
