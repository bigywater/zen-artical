import sys, os, re, time, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kl import *
tee('k20')
cn, _ = up('main')
NS = ns('k20')
k('create', 'sa', 'app', '-n', NS)
def tok(*a): 
    rc, o = k('create', 'token', 'app', '-n', NS, *a, raw=True); return rc, o.strip()
print(f'集群 {cn};TokenRequest:POST /api/v1/namespaces/<ns>/serviceaccounts/<name>/token,返回一个有时限、可绑定到对象的 JWT;kubectl create token 就是它的命令行')

print('== 一:有效期——默认值、指定值、下限和上限')
for label, args in (('不指定(默认)', ()), ('--duration=20m', ('--duration=20m',)), ('--duration=10m(下限)', ('--duration=10m',)), ('--duration=5m(低于下限)', ('--duration=5m',)), ('--duration=87600h(10 年)', ('--duration=87600h',))):
    rc, o = tok(*args)
    if rc == 0:
        c = jwt_claims(o); print(f'  {label}:退出码 0;exp-iat={c["exp"] - c["iat"]} 秒({(c["exp"] - c["iat"]) / 3600:.2f} 小时);aud={c["aud"]}')
    else: print(f'  {label}:退出码 {rc};{re.sub(r"^.*Invalid value: ", "Invalid value: ", o)[:200]}')

print('== 二:受众(audience)——同一个 SA,令牌给不同的服务用')
rc, t_def = tok(); rc, t_foo = tok('--audience=my-service')
for label, t in (('默认受众', t_def), ('--audience=my-service', t_foo)):
    c = jwt_claims(t); st, ui = whoami(t)
    print(f'  {label}:aud={c["aud"]};拿去调用 API Server(SelfSubjectReview):HTTP {st}' + (f' username={ui["username"]}' if st == 201 or st == 200 else ''))
def review(t, auds=None):
    spec = {'token': t}
    if auds: spec['audiences'] = auds
    st, j = api('POST', '/apis/authentication.k8s.io/v1/tokenreviews', None, {'apiVersion': 'authentication.k8s.io/v1', 'kind': 'TokenReview', 'spec': spec}) if False else (None, None)
    rc, o = k('create', '-f', '-', '-o', 'json', input=json.dumps({'apiVersion': 'authentication.k8s.io/v1', 'kind': 'TokenReview', 'spec': spec}), raw=True)
    r_ = json.loads(o)['status']; r_.setdefault('authenticated', False); return r_
s = review(t_foo, ['my-service']); print(f'  TokenReview(spec.audiences=[my-service])验证 my-service 的令牌:authenticated={s["authenticated"]};status.audiences={s.get("audiences")};user={s.get("user", {}).get("username")}')
s = review(t_foo); print(f'  TokenReview(不指定 audiences,按 API Server 自己的受众)验证同一个令牌:authenticated={s["authenticated"]};error={s.get("error", "")[:120]}')
s = review(t_foo[:-6] + 'AAAAAA', ['my-service']); print(f'  把令牌最后 6 个字符改掉(签名不对):authenticated={s["authenticated"]};error={s.get("error", "")[:120]}')

print('== 三:绑定对象——令牌随着被绑定的对象一起失效')
k('apply', '-f', '-', input=f'apiVersion: v1\nkind: Pod\nmetadata: {{name: holder, namespace: {NS}}}\nspec:\n  serviceAccountName: app\n  terminationGracePeriodSeconds: 0\n  containers: [{{name: c, image: busybox:1.36, command: [sleep, "3600"]}}]\n')
until(lambda: ko('get', 'pod', 'holder', '-n', NS, '-o', 'jsonpath={.status.phase}') == 'Running', 60)
rc, tb = tok('--bound-object-kind=Pod', '--bound-object-name=holder')
rc0, o0 = k('create', 'token', 'other-sa-not-exist', '-n', NS, raw=True) if False else (0, '')
k('create', 'sa', 'other', '-n', NS); rcx, ox = k('create', 'token', 'other', '-n', NS, '--bound-object-kind=Pod', '--bound-object-name=holder', raw=True)
print(f'  把 SA other 的令牌绑到 SA app 的 Pod holder 上:退出码 {rcx};{ox.strip()[:170]}')
cb = jwt_claims(tb); st, ui = whoami(tb)
print(f'  --bound-object-kind=Pod --bound-object-name=holder:claims 的 kubernetes.io.pod={cb["kubernetes.io"].get("pod")};调用 API:HTTP {st} username={ui["username"] if isinstance(ui, dict) else ui};extra={sorted(ui.get("extra", {})) if isinstance(ui, dict) else ""}')
def survive(label, t):
    t0 = time.time(); last_ok = None
    while time.time() - t0 < 60:
        st, ui = whoami(t)
        if st == 201: last_ok = time.time() - t0
        else: return f'{label}:删除后 {last_ok:.0f} 秒内这个令牌还能通过认证,第 {time.time() - t0:.0f} 秒起 HTTP {st}({ui if not isinstance(ui, dict) else ""})' if last_ok is not None else f'{label}:删除后第一次检查就是 HTTP {st}'
        time.sleep(1)
    return f'{label}:60 秒后仍然有效'
k('delete', 'pod', 'holder', '-n', NS, '--wait=true', timeout=60)
print('  ' + survive('删除被绑定的 Pod holder', tb))
st, ui = whoami(t_def); print(f'  同一时刻没有绑定对象的令牌 t_def(绑定的是 ServiceAccount 本身)还有效:HTTP {st} username={ui["username"] if isinstance(ui, dict) else ui}')
k('create', 'sa', 'temp', '-n', NS); rc, t_tmp = k('create', 'token', 'temp', '-n', NS, raw=True); t_tmp = t_tmp.strip()
st1, _ = whoami(t_tmp); k('delete', 'sa', 'temp', '-n', NS)
print(f'  给 SA temp 签一个令牌(HTTP {st1})再删掉 SA temp:' + survive('删除 SA temp', t_tmp))

print('== 四:TokenReview 看到的信息')
s = review(t_def, None)
print(f'  默认令牌的 TokenReview:authenticated={s["authenticated"]};user.username={s["user"]["username"]};user.uid={s["user"]["uid"][:8]}…;user.groups={s["user"]["groups"]}')
print(f'    status.audiences={s.get("audiences")};user.extra={json.dumps(s["user"].get("extra"), ensure_ascii=False)}')
rmns(NS)
