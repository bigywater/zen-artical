import sys, os, re, time, subprocess, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dl import *
tee('c53')
img('alpine:3.20')
purge()
d = ctx('c53', {'Dockerfile': 'FROM alpine:3.20\nRUN apk add --no-cache iproute2\n'})
rc, o = build(d, 'bwlab-c53', '--provenance=false', '--sbom=false'); assert rc == 0, o[-300:]
def vm(cmd):
    rc, o = dk('run', '--rm', '--privileged', '--pid=host', *LAB, 'alpine:3.20', 'nsenter', '-t', '1', '-m', '-u', '-n', '-i', 'sh', '-c', cmd, raw=True)
    return o.strip()
print('== 一:容器的 eth0 在虚拟机里对应哪个 veth(Docker Engine 29.8.2)')
n = 'bwlab-c53a'
dk('run', '-d', '--name', n, *LAB, 'bwlab-c53', 'sleep', '300')
ci = dk('exec', n, 'sh', '-c', 'echo $(cat /sys/class/net/eth0/ifindex) $(cat /sys/class/net/eth0/iflink)')[1].split()
print(f'  容器里 eth0:ifindex = {ci[0]},iflink = {ci[1]}(iflink 是对端设备的编号)')
print('  容器里 ip link:' + dk('exec', n, 'sh', '-c', "ip -o link show eth0 | awk '{print $2}'")[1].strip())
peer = vm(f"for d in /sys/class/net/*; do [ -f $d/ifindex ] && [ \"$(cat $d/ifindex)\" = {ci[1]} ] && echo $(basename $d) ifindex=$(cat $d/ifindex) iflink=$(cat $d/iflink); done")
print(f'  虚拟机里 ifindex = {ci[1]} 的设备:{peer}')
vname = peer.split()[0]
print(f'  它的类型:{vm(f"ip -d link show {vname} | sed -n 3p | tr -s \" \" | cut -c1-40")};它挂在哪个网桥上(master):{vm(f"basename $(readlink /sys/class/net/{vname}/master)")}')
print(f'  容器主进程在虚拟机里的 PID {out("inspect", "--format", "{{.State.Pid}}", n)}:它的 net 命名空间 = {vm("readlink /proc/%s/ns/net" % out("inspect", "--format", "{{.State.Pid}}", n))}')
print('== 二:两端的计数器是同一份流量')
def rx(cmd): return int(cmd.strip().split()[0]) if cmd.strip() else -1
t0 = int(dk('exec', n, 'cat', '/sys/class/net/eth0/statistics/tx_bytes')[1])
v0 = int(vm(f'cat /sys/class/net/{vname}/statistics/rx_bytes'))
dk('exec', n, 'ping', '-c', '10', '-s', '1000', '-i', '0.2', '-q', '172.17.0.1')
t1 = int(dk('exec', n, 'cat', '/sys/class/net/eth0/statistics/tx_bytes')[1])
v1 = int(vm(f'cat /sys/class/net/{vname}/statistics/rx_bytes'))
print(f'  容器 eth0 发送增量 {t1 - t0} 字节;虚拟机 {vname} 接收增量 {v1 - v0} 字节(ping 10 个 1000 字节负载的包,两个增量{'相同' if t1 - t0 == v1 - v0 else '不同'})')
print('== 三:手动搭一对 veth:两个网络命名空间(在一个特权容器里,不影响虚拟机)')
rc, o = dk('run', '--rm', '--privileged', *LAB, 'bwlab-c53', 'sh', '-c', '''
ip netns add blue
ip link add v0 type veth peer name v1 netns blue
ip addr add 10.77.0.1/24 dev v0 && ip link set v0 up
ip netns exec blue sh -c "ip addr add 10.77.0.2/24 dev v1; ip link set v1 up"
echo "v0:ifindex=$(cat /sys/class/net/v0/ifindex) iflink=$(cat /sys/class/net/v0/iflink);v1:ifindex=$(ip netns exec blue cat /sys/class/net/v1/ifindex) iflink=$(ip netns exec blue cat /sys/class/net/v1/iflink)"
ping -c 3 -W 1 10.77.0.2 | tail -2
ip netns list
ip netns exec blue ip route''')
for l in o.strip().splitlines(): print('  ' + l)
dk('rm', '-f', n)
purge()
