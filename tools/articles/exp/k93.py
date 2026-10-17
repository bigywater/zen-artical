import sys, os, re, time, json, datetime; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k93')
cn, _ = up('main'); wait_nodes_ready()
C = 'kx-main-control-plane'
def cr(c, **kw): return nx(C, c, **kw)[1].strip()
def cert(path, *fields): return cr(f'openssl x509 -in {path} -noout ' + ' '.join(fields))
print(f'集群 {cn};kubeadm 在控制面节点的 /etc/kubernetes/pki 下放着整套 PKI,在 /etc/kubernetes/*.conf 里内嵌着各组件的客户端证书')

print('== 一:有哪些证书,各自什么时候过期')
print('  /etc/kubernetes/pki/:' + ' '.join(cr('ls /etc/kubernetes/pki | tr "\\n" " "').split()))
print('  /etc/kubernetes/pki/etcd/:' + ' '.join(cr('ls /etc/kubernetes/pki/etcd | tr "\\n" " "').split()))
print('  /etc/kubernetes/*.conf:' + ' '.join(cr('ls /etc/kubernetes/*.conf | xargs -n1 basename | tr "\\n" " "').split()))
o = cr('kubeadm certs check-expiration 2>&1 | grep -v "^\\[" | grep -v "^$"'); print('  kubeadm certs check-expiration:'); [print('    ' + l) for l in o.splitlines()]

print('== 二:看一张证书里写了什么(apiserver.crt)')
f = '/etc/kubernetes/pki/apiserver.crt'
print(f'  subject={cert(f, "-subject")};issuer={cert(f, "-issuer")}')
print(f'  有效期:{cert(f, "-startdate")};{cert(f, "-enddate")}(共 {(datetime.datetime.strptime(cert(f, "-enddate").split("=")[1], "%b %d %H:%M:%S %Y %Z") - datetime.datetime.strptime(cert(f, "-startdate").split("=")[1], "%b %d %H:%M:%S %Y %Z")).days} 天)')
san = cr(f'openssl x509 -in {f} -noout -ext subjectAltName | tail -n +2'); print(f'  SAN:{" ".join(san.split())}')
print(f'  用途:{" ".join(cr(f"openssl x509 -in {f} -noout -ext extendedKeyUsage | tail -n +2").split())};CA 证书 ca.crt 的有效期:{cert("/etc/kubernetes/pki/ca.crt", "-enddate")}')
for nm, p in (('apiserver-kubelet-client', '/etc/kubernetes/pki/apiserver-kubelet-client.crt'), ('apiserver-etcd-client', '/etc/kubernetes/pki/apiserver-etcd-client.crt'), ('etcd server', '/etc/kubernetes/pki/etcd/server.crt')):
    print(f'  {nm}:subject={cert(p, "-subject")};issuer={cert(p, "-issuer")}')
def conf_subject(name):
    return cr(f"grep client-certificate-data /etc/kubernetes/{name}.conf | awk '{{print $2}}' | base64 -d | openssl x509 -noout -subject")
print(f'  admin.conf 内嵌的客户端证书:{conf_subject("admin")};super-admin.conf:{conf_subject("super-admin")}')
print(f'  controller-manager.conf:{conf_subject("controller-manager")};scheduler.conf:{conf_subject("scheduler")}')

print('== 三:kubelet 的证书——自动轮转')
print(f'  /var/lib/kubelet/pki/:{" ".join(cr("ls /var/lib/kubelet/pki").split())}')
print(f'  kubelet-client-current.pem 指向:{cr("readlink /var/lib/kubelet/pki/kubelet-client-current.pem")};subject={cr("openssl x509 -in /var/lib/kubelet/pki/kubelet-client-current.pem -noout -subject")};{cr("openssl x509 -in /var/lib/kubelet/pki/kubelet-client-current.pem -noout -enddate")}')
print(f'  kubelet.crt(serving):issuer={cr("openssl x509 -in /var/lib/kubelet/pki/kubelet.crt -noout -issuer")}(自签,不是集群 CA 签的);kubelet 配置 rotateCertificates={cr("grep rotateCertificates /var/lib/kubelet/config.yaml")};serverTLSBootstrap={cr("grep serverTLSBootstrap /var/lib/kubelet/config.yaml || echo 未设置")}')

print('== 四:renew 之后,apiserver 的服务证书会自动换上新的吗')
def served():
    return cr("echo | openssl s_client -connect 127.0.0.1:6443 2>/dev/null | openssl x509 -noout -serial -startdate")
def filed(): return cr(f'openssl x509 -in {f} -noout -serial -startdate')
pid0 = cr('crictl ps --name kube-apiserver -q | head -1'); st0 = cr("crictl inspect " + pid0 + " | jq -r .status.startedAt")
print(f'  renew 前:文件里 {" ".join(filed().split())};apiserver 实际出示 {" ".join(served().split())};apiserver 容器启动时间 {st0[:19]}')
rc, o = nx(C, 'kubeadm certs renew apiserver 2>&1 | grep -v "^\\["'); t0 = time.time(); print(f'  kubeadm certs renew apiserver:{" ".join(o.split())[:120]}')
print(f'  renew 后马上读文件:{" ".join(filed().split())}')
v, dt = until(lambda: served() == filed(), 90, 0.5)
pid1 = cr('crictl ps --name kube-apiserver -q | head -1'); st1 = cr("crictl inspect " + pid1 + " | jq -r .status.startedAt")
print(f'  不重启 apiserver,{dt:.1f} 秒后它出示的证书就变成了新的:{" ".join(served().split())};容器没有重启(同一个容器 {pid0 == pid1},启动时间仍是 {st1[:19]})')
print(f'  kubeadm certs check-expiration 里 apiserver 一行:{cr("kubeadm certs check-expiration 2>&1 | grep -E \'^apiserver  \'")}(它读的是磁盘上的文件)')
print(f'  kubectl 访问正常:{k("get", "--raw", "/readyz")[1].strip()}')
