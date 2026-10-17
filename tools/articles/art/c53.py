from lib import *
S = SS('c53')
steps = [
    step("容器里 eth0:ifindex = 11,iflink = 2364(iflink 是对端设备的编号),ip link 显示它是 eth0@if2364。到虚拟机里找 ifindex = 2364 的设备:是 veth8554796,它的 iflink = 11——两端互指。它的类型是 veth,master 是 docker0(挂在 docker0 网桥上)。容器主进程在虚拟机里的网络命名空间是 net:[4026534595]。一个容器的网卡 = 一对 veth,一端在容器的网络命名空间,一端挂在虚拟机的网桥上。", t=tl(S(1)), done=lidx(S(1), 'ifindex = 2364 的设备', '容器里 eth0'), mark=lidx(S(1), '它的类型', '容器里 ip link'), kv=KV([['容器端', 'eth0,ifindex 11,iflink 2364'], ['虚拟机端', 'veth8554796,ifindex 2364,iflink 11,master docker0']], ['虚拟机端'])),
    step("两端的计数器是同一份流量:往 172.17.0.1 ping 10 个 1000 字节负载的包,容器 eth0 的 tx_bytes 增加 10504 字节,虚拟机里 veth8554796 的 rx_bytes 也增加 10504 字节,两个增量相同。", t=tl(S(2)), done=lidx(S(2), '容器 eth0 发送增量'), b=bars([['容器 eth0 tx 增量', 10504, '10504'], ['veth rx 增量', 10504, '10504']], 10504, done=[0, 1]), kv=KV([['容器 eth0 发送', '+10504 字节'], ['虚拟机 veth 接收', '+10504 字节']], ['虚拟机 veth 接收'])),
    step("手动搭一对:在特权容器里 ip netns add blue,ip link add v0 type veth peer name v1 netns blue,给 v0 配 10.77.0.1/24、v1 配 10.77.0.2/24:v0 的 ifindex=12、iflink=11,v1 的 ifindex=11、iflink=12;ping 10.77.0.2 3 个包全部收到,ip netns list 里有 blue,blue 里的路由是 10.77.0.0/24 dev v1。veth 就是一根虚拟网线,两头各在一个命名空间。", t=tl(S(3)), done=lidx(S(3), '3 packets transmitted', 'v0:ifindex=12'), mark=lidx(S(3), 'blue (id: 1)', '10.77.0.0/24'), kv=KV([['v0', 'ifindex 12,iflink 11'], ['v1(在 blue 里)', 'ifindex 11,iflink 12'], ['ping', '3/3 成功']], ['v0'])),
]
A = mkartc('c53', 53, 'Docker,veth,网络命名空间,ifindex,iflink,docker0,真实验证,动画演示',
    '实测容器网卡的真身:容器里 eth0@if2364 的对端是虚拟机里的 veth8554796(两端 ifindex 与 iflink 互指,类型 veth,挂在 docker0 上),两端计数器的增量相同(10504 字节);并在特权容器里手动用 ip netns 和 veth 搭了一对连通的虚拟网线。',
    '容器里的 eth0 在宿主机上对应什么?veth 是什么?这篇从 /sys/class/net 的 ifindex 与 iflink 出发,找到容器网卡在虚拟机里的另一端,验证两端流量一致,再手动造一对 veth。',
    [('eth0@if2364', '容器 eth0 的对端编号 = 虚拟机里 veth8554796 的 ifindex'), ('10504 = 10504', '容器 eth0 发送增量与虚拟机 veth 接收增量'), ('ping 3/3', '手动搭的 v0 / v1 两个命名空间之间的连通性')],
    [('找到另一端', '<p>每个 veth 设备的 <code>iflink</code> 是对端的 <code>ifindex</code>。容器 eth0 的 iflink 是 2364,虚拟机里 ifindex 为 2364 的是 veth8554796,它的 iflink 又指回 11。这个 veth 挂在 docker0 网桥下(master)。</p>'),
     ('同一份流量', '<p>容器的 tx_bytes 和虚拟机端的 rx_bytes 增量完全一样,因为它们是同一根线的两头。</p>'),
     ('自己造', '<p>用 iproute2 在特权容器里建了命名空间 blue 和一对 veth,配上地址后互相 ping 通。这些都在那个特权容器自己的网络命名空间里,容器退出后一并消失,没有碰虚拟机的网络。iproute2 是我在镜像里 <code>apk add</code> 装的(busybox 的 ip 不支持把 veth 一端放进命名空间)。</p>')],
    steps,
    [ENV_C + '。ifindex / iflink / 计数器读自 /sys/class/net;虚拟机侧用特权容器加 nsenter 读取(方法见 c19);手动 veth 实验用 apk 装了 iproute2 的 alpine 镜像,在特权容器自己的网络命名空间里完成;设备编号每次运行都不同,文中取自最后一次运行;实验后已删除容器和镜像',
     '没有验证:Linux 宿主机上同样的对应关系、macvlan / ipvlan、veth 的 offload 与性能、网桥上的 MAC 学习与转发表、多网卡容器的第二对 veth(见 c46)'],
    'veth 与网络命名空间')
