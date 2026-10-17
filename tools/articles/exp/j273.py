import sys, os, re, time, shutil, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j273'); R = {}
data = JT / 'j273data'; shutil.rmtree(data, ignore_errors=True); data.mkdir(parents=True)
OSSL = shutil.which('openssl')
def sh(*a, **k): return subprocess.run(list(a), capture_output=True, text=True, **k)
sh(OSSL, 'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-keyout', str(data / 'ca.key'), '-out', str(data / 'ca.pem'), '-subj', '/CN=Local Test CA', '-days', '2', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign')
def mkcert(name, cn, san):
    sh(OSSL, 'req', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-keyout', str(data / f'{name}.key'), '-out', str(data / f'{name}.csr'), '-subj', f'/CN={cn}')
    (data / f'{name}.ext').write_text('basicConstraints=CA:FALSE\n' + (f'subjectAltName={san}\n' if san else ''))
    sh(OSSL, 'x509', '-req', '-in', str(data / f'{name}.csr'), '-CA', str(data / 'ca.pem'), '-CAkey', str(data / 'ca.key'), '-CAcreateserial', '-out', str(data / f'{name}.pem'), '-days', '2', '-extfile', str(data / f'{name}.ext'))
names = ['localhost', 'localhost.', 'wrong.test', 'right.test', 'cn.test', 'a.wild.test', 'wild.test', 'a.b.wild.test', 'w1.part.test', 'upper.test', 'dot.test', 'ex.test']
(data / 'hosts').write_text(''.join(f'127.0.0.1 {n}\n' for n in names))
CASES = [  # (证书标签, 证书 CN, SAN, [要连接的主机名])
    ('A SAN=DNS:localhost', 'x', 'DNS:localhost', ['localhost', 'LOCALHOST', 'localhost.']),
    ('B SAN=DNS:other.test(证书是给另一个域名的)', 'x', 'DNS:other.test', ['right.test']),
    ('C 只有 CN=cn.test,没有 SAN', 'cn.test', None, ['cn.test']),
    ('D SAN=DNS:*.wild.test', 'x', 'DNS:*.wild.test', ['a.wild.test', 'wild.test', 'a.b.wild.test']),
    ('E SAN=IP:127.0.0.1', 'x', 'IP:127.0.0.1', ['127.0.0.1', 'localhost']),
    ('F SAN=DNS:127.0.0.1(把 IP 写成 DNS 名)', 'x', 'DNS:127.0.0.1', ['127.0.0.1']),
    ('G SAN=DNS:w*.part.test(部分通配)', 'x', 'DNS:w*.part.test', ['w1.part.test']),
    ('H SAN=DNS:UPPER.TEST(大写)', 'x', 'DNS:UPPER.TEST', ['upper.test']),
    ('I SAN=DNS:dot.test + CN=wrong.test(SAN 与 CN 不一致)', 'wrong.test', 'DNS:dot.test', ['dot.test', 'wrong.test']),
]
for i, (lab, cn, san, hs) in enumerate(CASES): mkcert(f'c{i}', cn, san)
MAIN = r'''
import javax.net.ssl.*; import java.io.*; import java.net.*; import java.net.http.*; import java.nio.file.*; import java.security.*; import java.security.cert.*; import java.util.*;
public class Main {
  static SSLContext ctx(String ca) throws Exception { KeyStore ks = KeyStore.getInstance("PKCS12"); ks.load(null, null); try (InputStream in = Files.newInputStream(Path.of(ca))) { ks.setCertificateEntry("ca", CertificateFactory.getInstance("X.509").generateCertificate(in)); } TrustManagerFactory tmf = TrustManagerFactory.getInstance("PKIX"); tmf.init(ks); SSLContext c = SSLContext.getInstance("TLS"); c.init(null, tmf.getTrustManagers(), null); return c; }
  static String msg(Throwable t) { Throwable c = t; while (c.getCause() != null && !(c instanceof java.security.cert.CertificateException)) c = c.getCause(); String m = String.valueOf(c.getMessage()).replaceAll("\\s+", " "); return c.getClass().getSimpleName() + ":" + (m.length() > 85 ? m.substring(0, 85) : m); }
  public static void main(String[] a) throws Exception {
    System.setProperty("http.keepAlive", "false");
    if (a[0].equals("override")) { String host = a[1]; int port = Integer.parseInt(a[2]); SSLContext c = ctx(a[3]); String[] r = new String[4];
      try { HttpsURLConnection u = (HttpsURLConnection) new URL("https://" + host + ":" + port + "/").openConnection(); u.setSSLSocketFactory(c.getSocketFactory()); u.setHostnameVerifier((h, s) -> true); u.setConnectTimeout(5000); u.setReadTimeout(5000); int code = u.getResponseCode(); u.getInputStream().readAllBytes(); u.disconnect(); r[0] = "HTTP " + code; } catch (Exception e) { r[0] = "失败 " + msg(e); }
      try { HttpsURLConnection u = (HttpsURLConnection) new URL("https://" + host + ":" + port + "/").openConnection(); u.setSSLSocketFactory(c.getSocketFactory()); u.setHostnameVerifier((h, s) -> { System.out.println("RES   (自定义 HostnameVerifier 被调用:" + h + ")"); return false; }); u.setConnectTimeout(5000); u.setReadTimeout(5000); int code = u.getResponseCode(); u.disconnect(); r[1] = "HTTP " + code; } catch (Exception e) { r[1] = "失败 " + msg(e); }
      try { SSLParameters p0 = c.getDefaultSSLParameters(); r[2] = "SSLContext 的默认 SSLParameters.endpointIdentificationAlgorithm = " + p0.getEndpointIdentificationAlgorithm(); } catch (Exception e) { r[2] = e.toString(); }
      try { HttpClient hc = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).sslContext(c).connectTimeout(java.time.Duration.ofSeconds(5)).build(); HttpResponse<String> resp = hc.send(HttpRequest.newBuilder(URI.create("https://" + host + ":" + port + "/")).build(), HttpResponse.BodyHandlers.ofString()); r[3] = "HTTP " + resp.statusCode(); } catch (Exception e) { r[3] = "失败 " + msg(e); }
      System.out.println("RES " + String.join(" ¦ ", r)); return; }
    String host = a[0]; int port = Integer.parseInt(a[1]); SSLContext c = ctx(a[2]); String[] r = new String[4];
    try (SSLSocket s = (SSLSocket) c.getSocketFactory().createSocket(host, port)) { s.startHandshake(); r[0] = "握手成功"; } catch (Exception e) { r[0] = "失败 " + msg(e); }
    try (SSLSocket s = (SSLSocket) c.getSocketFactory().createSocket(host, port)) { SSLParameters p = s.getSSLParameters(); p.setEndpointIdentificationAlgorithm("HTTPS"); s.setSSLParameters(p); s.startHandshake(); r[1] = "握手成功"; } catch (Exception e) { r[1] = "失败 " + msg(e); }
    try { HttpsURLConnection u = (HttpsURLConnection) new URL("https://" + (host.contains(":") ? "[" + host + "]" : host) + ":" + port + "/").openConnection(); u.setSSLSocketFactory(c.getSocketFactory()); u.setConnectTimeout(5000); u.setReadTimeout(5000); int code = u.getResponseCode(); u.getInputStream().readAllBytes(); u.disconnect(); r[2] = "HTTP " + code; } catch (Exception e) { r[2] = "失败 " + msg(e); }
    try { HttpClient hc = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).sslContext(c).connectTimeout(java.time.Duration.ofSeconds(5)).build(); HttpResponse<String> resp = hc.send(HttpRequest.newBuilder(URI.create("https://" + host + ":" + port + "/")).build(), HttpResponse.BodyHandlers.ofString()); r[3] = "HTTP " + resp.statusCode(); } catch (Exception e) { r[3] = "失败 " + msg(e); }
    System.out.println("RES " + String.join(" ¦ ", r));
  }
}
'''
d = jdir('j273a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
print('== 一:同一张由本地 CA 签发的证书,换不同的主机名去连接(本地 CA 在信任库里;主机名通过 -Djdk.net.hosts.file 解析到 127.0.0.1)')
print('  四种客户端:①SSLSocket 默认设置;②SSLSocket + setEndpointIdentificationAlgorithm(\"HTTPS\");③HttpsURLConnection;④java.net.http.HttpClient')
tally = {'raw': 0, 'idalg': 0, 'url': 0, 'client': 0}; total = 0; results = []
for i, (lab, cn, san, hs) in enumerate(CASES):
    port = 9740 + i
    srv = subprocess.Popen([OSSL, 's_server', '-accept', str(port), '-cert', str(data / f'c{i}.pem'), '-key', str(data / f'c{i}.key'), '-www', '-quiet'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(0.8)
    try:
        print(f'  [{lab}]')
        for h in hs:
            r = subprocess.run(['java', f'-Djdk.net.hosts.file={data / "hosts"}', '-cp', 'out', 'Main', h, str(port), str(data / 'ca.pem')], cwd=d, env=E, capture_output=True, text=True, timeout=90)
            line = next((l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ')), (r.stdout + r.stderr).strip()[:300]); parts = line.split(' ¦ ')
            print(f'      连接 {h}:①{parts[0]};②{parts[1] if len(parts) > 1 else "?"}');
            if len(parts) > 3: print(f'          ③{parts[2]};④{parts[3]}')
            results.append((lab, h, parts))
    finally: srv.kill()
ok = lambda s: s.startswith('握手成功') or s.startswith('HTTP')
n_raw_ok_bad = sum(1 for lab, h, p in results if len(p) > 3 and ok(p[0]) and not ok(p[1]))
print(f'  汇总:共 {len(results)} 种(证书, 主机名)组合;①默认 SSLSocket 成功但②加上端点标识后失败的有 {n_raw_ok_bad} 种;①成功的共 {sum(1 for _, _, p in results if len(p) > 3 and ok(p[0]))} 种,②成功的共 {sum(1 for _, _, p in results if len(p) > 3 and ok(p[1]))} 种,③成功的共 {sum(1 for _, _, p in results if len(p) > 3 and ok(p[2]))} 种,④成功的共 {sum(1 for _, _, p in results if len(p) > 3 and ok(p[3]))} 种')
def res(lab_prefix, host):
    for lab, h, p in results:
        if lab.startswith(lab_prefix) and h == host: return p
    return ['?'] * 4
def short(x): return '成功' if ok(x) else '失败(' + x.replace('失败 ', '')[:60] + ')'
print('== 二:匹配规则(由上面的结果归纳,按②加 HTTPS 标识的 SSLSocket)')
print(f'  大小写:SAN=localhost,连接 LOCALHOST → {short(res("A", "LOCALHOST")[1])}')
print(f'  没有 SAN 时回退到 CN:证书只有 CN=cn.test,连接 cn.test → {short(res("C", "cn.test")[1])}')
print(f'  有 SAN 时 CN 被忽略:SAN=dot.test、CN=wrong.test,连接 dot.test → {short(res("I", "dot.test")[1])};连接 wrong.test → {short(res("I", "wrong.test")[1])}')
print(f'  通配符 *.wild.test:连接 a.wild.test → {short(res("D", "a.wild.test")[1])};连接 wild.test → {short(res("D", "wild.test")[1])};连接 a.b.wild.test → {short(res("D", "a.b.wild.test")[1])}')
print(f'  部分通配 w*.part.test:连接 w1.part.test → {short(res("G", "w1.part.test")[1])}')
print(f'  IP 地址:SAN=IP:127.0.0.1,连接 127.0.0.1 → {short(res("E", "127.0.0.1")[1])};连接 localhost → {short(res("E", "localhost")[1])};SAN=DNS:127.0.0.1,连接 127.0.0.1 → {short(res("F", "127.0.0.1")[1])}')
pt = res("A", "localhost."); print(f'  主机名带结尾的点(localhost.):①{short(pt[0])};②{short(pt[1])};③{short(pt[2])};④{short(pt[3])}')
print('== 三:想“绕过”主机名检查:对证书是给 other.test 的服务端(案例 B),用 right.test 去连')
i = 1; port = 9760
srv = subprocess.Popen([OSSL, 's_server', '-accept', str(port), '-cert', str(data / f'c{i}.pem'), '-key', str(data / f'c{i}.key'), '-www', '-quiet'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(0.8)
try:
    for lab, fl in (('默认', []), ('-Djdk.internal.httpclient.disableHostnameVerification=true', ['-Djdk.internal.httpclient.disableHostnameVerification=true']), ('-Dcom.sun.net.ssl.checkRevocation=false(与主机名无关,对照)', ['-Dcom.sun.net.ssl.checkRevocation=false'])):
        r = subprocess.run(['java', f'-Djdk.net.hosts.file={data / "hosts"}', *fl, '-cp', 'out', 'Main', 'override', 'right.test', str(port), str(data / 'ca.pem')], cwd=d, env=E, capture_output=True, text=True, timeout=90)
        out = [l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ')]; main = next((l for l in out if ' ¦ ' in l), ''); extra = [l.strip() for l in out if ' ¦ ' not in l]; p = main.split(' ¦ ')
        print(f'  [{lab}] HttpsURLConnection + setHostnameVerifier((h, s) -> true):{p[0]};HttpsURLConnection + 返回 false 的验证器:{p[1]}' + (';' + ' '.join(extra) if extra else '') + f';HttpClient:{p[3]}')
        if lab == '默认': print('      ' + p[2])
finally: srv.kill()
shutil.rmtree(data, ignore_errors=True)
