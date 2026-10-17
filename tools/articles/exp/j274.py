import sys, os, re, time, shutil, json, signal; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j274'); R = {}
data = JT / 'j274data'; shutil.rmtree(data, ignore_errors=True); data.mkdir(parents=True)
OSSL = shutil.which('openssl')
def sh(*a, **k): return subprocess.run(list(a), capture_output=True, text=True, **k)
sh(OSSL, 'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-keyout', str(data / 'ca.key'), '-out', str(data / 'ca.pem'), '-subj', '/CN=Local Test CA', '-days', '2', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign')
sh(OSSL, 'req', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-keyout', str(data / 'srv.key'), '-out', str(data / 'srv.csr'), '-subj', '/CN=x')
(data / 'srv.ext').write_text('basicConstraints=CA:FALSE\nsubjectAltName=DNS:localhost\n')
sh(OSSL, 'x509', '-req', '-in', str(data / 'srv.csr'), '-CA', str(data / 'ca.pem'), '-CAkey', str(data / 'ca.key'), '-CAcreateserial', '-out', str(data / 'srv.pem'), '-days', '2', '-extfile', str(data / 'srv.ext'))
MAIN = r'''
import javax.crypto.*; import javax.crypto.spec.*; import javax.net.ssl.*; import java.io.*; import java.net.*; import java.net.http.*; import java.nio.charset.*; import java.nio.file.*; import java.security.*; import java.security.cert.*; import java.util.*;
public class Main {
  static void say(String s) { System.out.println("RES " + s); }
  static SSLContext ctx(String ca) throws Exception { KeyStore ks = KeyStore.getInstance("PKCS12"); ks.load(null, null); try (InputStream in = Files.newInputStream(Path.of(ca))) { ks.setCertificateEntry("ca", CertificateFactory.getInstance("X.509").generateCertificate(in)); } TrustManagerFactory tmf = TrustManagerFactory.getInstance("PKIX"); tmf.init(ks); SSLContext c = SSLContext.getInstance("TLS"); c.init(null, tmf.getTrustManagers(), null); return c; }
  static String hex(byte[] b) { StringBuilder s = new StringBuilder(); for (byte x : b) s.append(String.format("%02x", x)); return s.toString(); }
  static String sha(String s) throws Exception { return hex(MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8))); }
  static String hmac(byte[] key, String s) throws Exception { Mac m = Mac.getInstance("HmacSHA256"); m.init(new SecretKeySpec(key, "HmacSHA256")); return hex(m.doFinal(s.getBytes(StandardCharsets.UTF_8))); }
  interface Hasher { String h(String prev, String body) throws Exception; }
  static List<String> build(int n, Hasher h) throws Exception { List<String> lines = new ArrayList<>(); String prev = "0".repeat(64); for (int i = 1; i <= n; i++) { String body = "{\"seq\":" + i + ",\"actor\":\"user" + (i % 7) + "\",\"action\":\"" + (i % 3 == 0 ? "login" : i % 3 == 1 ? "read" : "delete") + "\",\"resource\":\"/orders/" + i + "\",\"outcome\":\"" + (i % 11 == 0 ? "denied" : "ok") + "\"}"; String hash = h.h(prev, body); lines.add(body + "|" + prev + "|" + hash); prev = hash; } return lines; }
  /** 返回第一个校验失败的 seq(从 1 起),全部通过返回 -1 */
  static int verify(List<String> lines, Hasher h, String anchor) throws Exception { String prev = "0".repeat(64); int seq = 0; for (String l : lines) { seq++; String[] p = l.split("\\|"); if (p.length != 3) return seq; if (!p[1].equals(prev)) return seq; if (!h.h(p[1], p[0]).equals(p[2])) return seq; prev = p[2]; } if (anchor != null && !anchor.equals(prev)) return lines.size() + 1; return -1; }
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    if (mode.equals("client")) {
      SSLContext c = ctx(a[1]); HttpsURLConnection u = (HttpsURLConnection) new URL("https://localhost:" + a[2] + "/?user=alice&password=hunter2").openConnection(); u.setSSLSocketFactory(c.getSocketFactory()); u.setRequestProperty("Authorization", "Bearer SECRET-TOKEN-123"); u.setConnectTimeout(5000); u.setReadTimeout(5000); try { say("响应码 " + u.getResponseCode()); } catch (Exception e) { say("请求异常 " + e.getClass().getSimpleName()); } u.disconnect();
    } else if (mode.equals("leaks")) {
      String pw = "S3cret!pw"; URL url = new URL("https://alice:" + pw + "@example.com/path?x=1"); URI uri = URI.create("https://alice:" + pw + "@example.com/path?x=1"); HttpRequest req = HttpRequest.newBuilder(uri).build();
      say("URL.toString():" + url); say("URI.toString():" + uri); say("HttpRequest.toString():" + req); say("URL.getAuthority() = " + url.getAuthority() + ",getUserInfo() = " + url.getUserInfo() + ",getHost() = " + url.getHost() + "(只有 getHost() 不含密码)");
      Properties p = new Properties(); p.setProperty("db.user", "alice"); p.setProperty("db.password", pw); say("Properties.toString():" + p); char[] pc = pw.toCharArray(); System.out.println("RES System.out.println(char[]) 打印:" + String.valueOf(pc)); say("println(Object) 打印 char[]:" + (Object) pc + "(只是类型与哈希);Arrays.toString(char[]):" + Arrays.toString(pc) + ";String.valueOf(char[]):" + String.valueOf(pc));
      say("sun.java.command 系统属性(包含启动参数):" + System.getProperty("sun.java.command")); say("ProcessHandle.current().info().commandLine():" + ProcessHandle.current().info().commandLine().orElse("?").replaceAll("^.*/bin/java ", "java "));
      String[][] exc = {{"Integer.parseInt(口令)", "Integer.parseInt"}, {"new BigDecimal(口令)", "BigDecimal"}, {"UUID.fromString(口令)", "UUID"}, {"URI.create(\"http://a b/\" + 口令)", "URI"}, {"Base64 解码含非法字符的口令", "B64"}, {"LocalDate.parse(口令)", "LocalDate"}, {"Enum.valueOf(口令)", "Enum"}};
      for (String[] e : exc) { try { switch (e[1]) { case "Integer.parseInt" -> Integer.parseInt(pw); case "BigDecimal" -> new java.math.BigDecimal(pw); case "UUID" -> UUID.fromString(pw); case "URI" -> URI.create("http://a b/" + pw); case "B64" -> Base64.getDecoder().decode(pw); case "LocalDate" -> java.time.LocalDate.parse(pw); default -> Thread.State.valueOf(pw); } } catch (Throwable t) { say(e[0] + " 抛出:" + t.getClass().getSimpleName() + ": " + t.getMessage() + "  → 包含口令 = " + String.valueOf(t.getMessage()).contains(pw)); } }
      try { Cipher.getInstance("AES/" + pw + "/NoPadding"); } catch (Throwable t) { say("Cipher.getInstance 传入口令:" + t.getClass().getSimpleName() + ": " + t.getMessage() + "  → 包含口令 = " + String.valueOf(t.getMessage()).contains(pw)); }
    } else if (mode.equals("chain")) {
      Hasher plain = (prev, body) -> sha(prev + body); byte[] key = "audit-hmac-key-0123456789".getBytes(); Hasher hm = (prev, body) -> hmac(key, prev + body); int N = 1000;
      List<String> L = build(N, plain); String anchor = L.get(L.size() - 1).split("\\|")[2];
      say("N = " + N + " 条审计记录,每条 = JSON 正文 | 上一条的哈希 | 本条哈希。示例第 1 条:" + L.get(0).substring(0, 100) + "…");
      say("原始日志校验:" + (verify(L, plain, null) == -1 ? "全部通过" : "第 " + verify(L, plain, null) + " 条失败"));
      List<String> m1 = new ArrayList<>(L); m1.set(499, m1.get(499).replace("\"outcome\":\"ok\"", "\"outcome\":\"denied\"").replace("\"delete\"", "\"read\"")); say("篡改第 500 条的正文(把 delete 改成 read,ok 改成 denied):校验失败的第一条 seq = " + verify(m1, plain, null));
      List<String> m2 = new ArrayList<>(L); m2.remove(499); say("删除第 500 条:校验失败的第一条 seq = " + verify(m2, plain, null) + "(原来第 501 条的上一条哈希对不上了)");
      List<String> m3 = new ArrayList<>(L); Collections.swap(m3, 99, 100); say("交换第 100 与第 101 条:校验失败的第一条 seq = " + verify(m3, plain, null));
      List<String> m4 = new ArrayList<>(L.subList(0, N - 10)); say("删除最后 10 条(截断尾部):无锚点时校验 " + (verify(m4, plain, null) == -1 ? "全部通过(没有发现)" : "失败") + ";用外部保存的最后一条哈希作锚点时校验失败的位置 = " + verify(m4, plain, anchor) + "(= 剩余条数 + 1)");
      List<String> m5 = new ArrayList<>(L.subList(0, 499)); String prev = m5.isEmpty() ? "0".repeat(64) : m5.get(498).split("\\|")[2]; for (int i = 499; i < N; i++) { String body = L.get(i).split("\\|")[0]; if (i == 499) body = body.replace("\"delete\"", "\"read\""); String h = plain.h(prev, body); m5.add(body + "|" + prev + "|" + h); prev = h; }
      say("攻击者从第 500 条起把后面的哈希全部重新计算(普通 SHA-256 链,不需要任何密钥):无锚点校验 " + (verify(m5, plain, null) == -1 ? "全部通过(篡改成功)" : "失败") + ";用外部锚点(原始的最后一条哈希)校验失败的位置 = " + verify(m5, plain, anchor));
      List<String> H = build(N, hm); String hAnchor = H.get(H.size() - 1).split("\\|")[2]; List<String> m6 = new ArrayList<>(H.subList(0, 499)); prev = m6.get(498).split("\\|")[2]; for (int i = 499; i < N; i++) { String body = H.get(i).split("\\|")[0]; if (i == 499) body = body.replace("\"delete\"", "\"read\""); String h = plain.h(prev, body); m6.add(body + "|" + prev + "|" + h); prev = h; }
      say("同样的攻击,但日志用 HMAC-SHA256 链(密钥不在攻击者手里):攻击者用普通 SHA-256 重算后,用 HMAC 校验失败的第一条 seq = " + verify(m6, hm, null) + ";原始 HMAC 日志校验 " + (verify(H, hm, null) == -1 ? "全部通过" : "失败"));
      long t0 = System.nanoTime(); for (int i = 0; i < 20; i++) build(N, hm); double bt = (System.nanoTime() - t0) / 1e6 / 20; t0 = System.nanoTime(); for (int i = 0; i < 20; i++) verify(H, hm, null); double vt = (System.nanoTime() - t0) / 1e6 / 20; say(String.format("HMAC 链:生成 %d 条约 %.1f ms(每条约 %.1f µs),校验 %d 条约 %.1f ms", N, bt, bt * 1000 / N, N, vt));
    }
  }
}
'''
d = jdir('j274a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def server(port):
    return subprocess.Popen([OSSL, 's_server', '-accept', str(port), '-cert', str(data / 'srv.pem'), '-key', str(data / 'srv.key'), '-www', '-quiet'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print('== 一:JDK 自带的调试日志会把明文写出来:同一个 HTTPS 请求(Authorization 头与查询字符串里的口令),只改 -Djavax.net.debug')
for lab, fl in (('默认(没有调试)', []), ('-Djavax.net.debug=ssl:handshake', ['-Djavax.net.debug=ssl:handshake']), ('-Djavax.net.debug=ssl:record', ['-Djavax.net.debug=ssl:record']), ('-Djavax.net.debug=ssl:record:plaintext', ['-Djavax.net.debug=ssl:record:plaintext']), ('-Djavax.net.debug=all', ['-Djavax.net.debug=all'])):
    srv = server(9770); time.sleep(0.8)
    try:
        r = subprocess.run(['java', *fl, '-cp', 'out', 'Main', 'client', str(data / 'ca.pem'), '9770'], cwd=d, env=E, capture_output=True, text=True, timeout=90)
    finally: srv.kill()
    out = r.stdout + r.stderr; lines = out.count('\n')
    hexbytes = bytearray()
    for l in out.splitlines():
        m = re.match(r'^\s*[0-9A-Fa-f]{4}: ((?:[0-9A-Fa-f]{2} +)+)', l)
        if m: hexbytes += bytes.fromhex(m.group(1).replace(' ', ''))
    text = hexbytes.decode('latin1')
    print(f'  [{lab}] 输出 {lines} 行,其中十六进制转储的字节 {len(hexbytes)} 个;直接搜索文本:“SECRET-TOKEN-123” 出现 {out.count("SECRET-TOKEN-123")} 次;把所有十六进制转储拼起来再搜索:“SECRET-TOKEN-123” {text.count("SECRET-TOKEN-123")} 次,“hunter2” {text.count("hunter2")} 次,“Authorization” {text.count("Authorization")} 次')
print('== 二:没有开任何调试,字符串也会把秘密带进日志')
r = subprocess.run(['java', '-cp', 'out', 'Main', 'leaks', '--password=cli-secret-42'], cwd=d, env=E, capture_output=True, text=True, timeout=60)
for l in (r.stdout + r.stderr).splitlines():
    if l.startswith('RES '): print('  ' + l[4:][:240])
p = subprocess.Popen(['sh', '-c', 'sleep 20; echo "$1"', 'sh', '--token=ARGV-SECRET-777'], env=dict(os.environ, API_KEY='ENV-SECRET-888')); time.sleep(0.5)
ps_args = subprocess.run(['ps', '-o', 'args=', '-p', str(p.pid)], capture_output=True, text=True).stdout.strip(); ps_env = subprocess.run(['ps', 'eww', '-p', str(p.pid)], capture_output=True, text=True).stdout
p.kill()
print(f'  另一个进程(同一用户)用 ps -o args= 看到的命令行:{ps_args};“ARGV-SECRET-777” 出现 = {"ARGV-SECRET-777" in ps_args};在 ps eww 的输出里 “ENV-SECRET-888”(环境变量)出现 = {"ENV-SECRET-888" in ps_env}')
print('== 三:防篡改的审计日志:每条记录带上一条的哈希(哈希链),1000 条,校验的行为')
r = subprocess.run(['java', '-cp', 'out', 'Main', 'chain'], cwd=d, env=E, capture_output=True, text=True, timeout=120)
for l in (r.stdout + r.stderr).splitlines():
    if l.startswith('RES '): print('  ' + l[4:])
print('== 四:JFR 里的安全事件(记录的是“发生了什么”,不含秘密):一次 TLS 请求')
srv = server(9771); time.sleep(0.8)
jfr = str(data / 'sec.jfr')
try:
    r = subprocess.run(['java', f'-XX:StartFlightRecording:filename={jfr},jdk.TLSHandshake#enabled=true,jdk.X509Validation#enabled=true,jdk.X509Certificate#enabled=true,jdk.SecurityPropertyModification#enabled=true', '-cp', 'out', 'Main', 'client', str(data / 'ca.pem'), '9771'], cwd=d, env=E, capture_output=True, text=True, timeout=90)
finally: srv.kill()
ev = subprocess.run(['jfr', 'summary', jfr], capture_output=True, text=True, env=E).stdout
for name in ('jdk.TLSHandshake', 'jdk.X509Validation', 'jdk.X509Certificate', 'jdk.SecurityPropertyModification'):
    m = re.search(rf'{re.escape(name)}\s+(\d+)\s+\d+', ev)
    print(f'  事件 {name}:{m.group(1) if m else "未出现"} 个')
pr = subprocess.run(['jfr', 'print', '--events', 'jdk.TLSHandshake', jfr], capture_output=True, text=True, env=E).stdout
print('  jdk.TLSHandshake 的内容:' + ' | '.join(l.strip() for l in pr.splitlines() if re.search(r'peerHost|peerPort|protocolVersion|cipherSuite|certificateId', l)))
pv = subprocess.run(['jfr', 'print', '--events', 'jdk.X509Validation', jfr], capture_output=True, text=True, env=E).stdout
print('  jdk.X509Validation 的内容:' + ' | '.join(l.strip() for l in pv.splitlines() if re.search(r'certificateId|certificatePosition|validationCounter|startTime', l))[:260])
px = subprocess.run(['jfr', 'print', '--events', 'jdk.X509Certificate', jfr], capture_output=True, text=True, env=E).stdout
print('  jdk.X509Certificate 的内容(第一个事件):' + ' | '.join(l.strip() for l in px.split('jdk.X509Certificate')[1].splitlines() if re.search(r'algorithm|subject|issuer|keyType|keyLength|validFrom|validUntil', l))[:420] if 'jdk.X509Certificate' in px else '  无 jdk.X509Certificate')
full = pr + pv + subprocess.run(['jfr', 'print', jfr], capture_output=True, text=True, env=E).stdout
print(f'  整个 JFR 文件打印出的文本里 “SECRET-TOKEN-123” 出现 {full.count("SECRET-TOKEN-123")} 次,“hunter2” 出现 {full.count("hunter2")} 次')
shutil.rmtree(data, ignore_errors=True)
