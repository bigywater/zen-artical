import sys, os, re, time, shutil, json; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j272'); R = {}
CP = mcp('org.bouncycastle:bcprov-jdk18on:1.78.1', 'org.bouncycastle:bcpkix-jdk18on:1.78.1', 'com.fasterxml.jackson.core:jackson-databind:2.17.2')
data = JT / 'j272data'; shutil.rmtree(data, ignore_errors=True); data.mkdir(parents=True)
OSSL = shutil.which('openssl'); PROXY = '127.0.0.1:1087'
def fetch_chain(host):
    r = subprocess.run([OSSL, 's_client', '-proxy', PROXY, '-connect', f'{host}:443', '-servername', host, '-showcerts'], input='', capture_output=True, text=True, timeout=60)
    certs = re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', r.stdout, re.S); (data / f'{host}.pem').write_text('\n'.join(certs[:2]) + '\n'); return len(certs)
subprocess.run(['curl', '-s', '-x', f'http://{PROXY}', '-m', '60', '-o', str(data / 'loglist.json'), 'https://www.gstatic.com/ct/log_list/v3/log_list.json'])
hosts = ['github.com', 'www.wikipedia.org', 'example.com']
nchain = {h: fetch_chain(h) for h in hosts}
MAIN = r'''
import com.fasterxml.jackson.databind.*; import org.bouncycastle.asn1.*; import org.bouncycastle.asn1.x509.*; import java.io.*; import java.net.*; import java.net.http.*; import java.nio.ByteBuffer; import java.nio.file.*; import java.security.*; import java.security.cert.*; import java.time.*; import java.util.*;
public class Main {
  static final String SCT_OID = "1.3.6.1.4.1.11129.2.4.2";
  static void say(String s) { System.out.println("RES " + s); }
  static String hex(byte[] b, int n) { StringBuilder s = new StringBuilder(); for (int i = 0; i < Math.min(n, b.length); i++) s.append(String.format("%02x", b[i])); return s.toString(); }
  record Sct(int version, byte[] logId, long ts, byte[] ext, int hashAlg, int sigAlg, byte[] sig) {}
  static List<X509Certificate> chain(Path p) throws Exception { CertificateFactory cf = CertificateFactory.getInstance("X.509"); List<X509Certificate> l = new ArrayList<>(); try (InputStream in = Files.newInputStream(p)) { for (java.security.cert.Certificate c : cf.generateCertificates(in)) l.add((X509Certificate) c); } return l; }
  static List<Sct> scts(X509Certificate c) throws Exception {
    byte[] ev = c.getExtensionValue(SCT_OID); if (ev == null) return List.of(); byte[] inner = ((ASN1OctetString) ASN1Primitive.fromByteArray(((ASN1OctetString) ASN1Primitive.fromByteArray(ev)).getOctets())).getOctets();
    ByteBuffer b = ByteBuffer.wrap(inner); int total = b.getShort() & 0xffff; List<Sct> out = new ArrayList<>(); int end = b.position() + total;
    while (b.position() < end) { int len = b.getShort() & 0xffff; byte[] e = new byte[len]; b.get(e); ByteBuffer s = ByteBuffer.wrap(e); int ver = s.get() & 0xff; byte[] id = new byte[32]; s.get(id); long ts = s.getLong(); byte[] ext = new byte[s.getShort() & 0xffff]; s.get(ext); int ha = s.get() & 0xff, sa = s.get() & 0xff; byte[] sig = new byte[s.getShort() & 0xffff]; s.get(sig); out.add(new Sct(ver, id, ts, ext, ha, sa, sig)); }
    return out; }
  static byte[] precertTbs(X509Certificate c) throws Exception {
    ASN1Sequence tbs = ASN1Sequence.getInstance(org.bouncycastle.asn1.x509.Certificate.getInstance(c.getEncoded()).getTBSCertificate().toASN1Primitive()); ASN1EncodableVector v = new ASN1EncodableVector();
    for (ASN1Encodable e : tbs) { if (e instanceof ASN1TaggedObject t && t.getTagNo() == 3 && t.hasContextTag()) { ASN1Sequence exts = ASN1Sequence.getInstance(t.getExplicitBaseObject()); ASN1EncodableVector ev = new ASN1EncodableVector(); for (ASN1Encodable x : exts) if (!org.bouncycastle.asn1.x509.Extension.getInstance(x).getExtnId().getId().equals(SCT_OID)) ev.add(x); v.add(new DERTaggedObject(true, 3, new DERSequence(ev))); } else v.add(e); }
    return new DERSequence(v).getEncoded(ASN1Encoding.DER); }
  static byte[] u24(int n) { return new byte[]{(byte) (n >> 16), (byte) (n >> 8), (byte) n}; }
  static byte[] cat(byte[]... p) { int n = 0; for (byte[] x : p) n += x.length; byte[] r = new byte[n]; int o = 0; for (byte[] x : p) { System.arraycopy(x, 0, r, o, x.length); o += x.length; } return r; }
  static byte[] be(long v, int n) { byte[] r = new byte[n]; for (int i = n - 1; i >= 0; i--) { r[i] = (byte) v; v >>= 8; } return r; }
  static byte[] entry(Sct s, byte[] issuerHash, byte[] tbs) { return cat(be(s.ts(), 8), be(1, 2), issuerHash, u24(tbs.length), tbs, be(s.ext().length, 2), s.ext()); }
  static boolean verify(Sct s, byte[] issuerHash, byte[] tbs, PublicKey key) throws Exception { byte[] data = cat(new byte[]{0, 0}, entry(s, issuerHash, tbs)); Signature sg = Signature.getInstance(s.sigAlg() == 3 ? "SHA256withECDSA" : "SHA256withRSA"); sg.initVerify(key); sg.update(data); return sg.verify(s.sig()); }
  static byte[] sha256(byte[]... p) throws Exception { MessageDigest md = MessageDigest.getInstance("SHA-256"); for (byte[] x : p) md.update(x); return md.digest(); }
  static Map<String, JsonNode> logs(Path p) throws Exception { JsonNode root = new ObjectMapper().readTree(p.toFile()); Map<String, JsonNode> m = new HashMap<>(); for (JsonNode op : root.get("operators")) for (JsonNode l : op.get("logs")) { ((com.fasterxml.jackson.databind.node.ObjectNode) l).put("operator", op.get("name").asText()); m.put(l.get("log_id").asText(), l); } return m; }
  static String state(JsonNode l) { Iterator<String> it = l.get("state").fieldNames(); return it.hasNext() ? it.next() : "?"; }
  public static void main(String[] a) throws Exception {
    Path dir = Path.of(a[1]); String mode = a[0];
    if (mode.equals("tls")) { javax.net.ssl.SSLContext ctx; if (a[3].equals("default")) ctx = javax.net.ssl.SSLContext.getDefault(); else { java.security.KeyStore ks = java.security.KeyStore.getInstance("PKCS12"); ks.load(null, null); ks.setCertificateEntry("ca", chain(Path.of(a[3])).get(0)); javax.net.ssl.TrustManagerFactory tmf = javax.net.ssl.TrustManagerFactory.getInstance("PKIX"); tmf.init(ks); ctx = javax.net.ssl.SSLContext.getInstance("TLS"); ctx.init(null, tmf.getTrustManagers(), null); }
      try (javax.net.ssl.SSLSocket sk = (javax.net.ssl.SSLSocket) ctx.getSocketFactory().createSocket("localhost", Integer.parseInt(a[2]))) { sk.startHandshake(); X509Certificate pc = (X509Certificate) sk.getSession().getPeerCertificates()[0]; say("握手成功:协议 " + sk.getSession().getProtocol() + ",对端证书 " + pc.getSubjectX500Principal().getName() + ",内嵌 SCT 扩展 = " + (pc.getExtensionValue(SCT_OID) != null) + ",TLS 握手里收到的 SCT(SSLSession 没有相关 API)"); } catch (Exception e) { say("握手失败:" + e.getClass().getSimpleName() + ":" + String.valueOf(e.getMessage()).replaceAll("\\s+", " ").substring(0, Math.min(120, String.valueOf(e.getMessage()).length()))); } return; }
    Map<String, JsonNode> logs = logs(dir.resolve("loglist.json"));
    if (mode.equals("parse")) {
      for (String host : a[2].split(",")) { List<X509Certificate> ch = chain(dir.resolve(host + ".pem")); X509Certificate leaf = ch.get(0); List<Sct> ss = scts(leaf);
        say(host + ":叶子证书主题 " + leaf.getSubjectX500Principal().getName().replaceAll(",.*", "") + ",颁发者 " + leaf.getIssuerX500Principal().getName().replaceAll(".*CN=([^,]*).*", "$1") + ",有效期 " + leaf.getNotBefore().toInstant().toString().substring(0, 10) + " 至 " + leaf.getNotAfter().toInstant().toString().substring(0, 10) + ",扩展 OID " + SCT_OID + " 存在 = " + (leaf.getNonCriticalExtensionOIDs() != null && leaf.getNonCriticalExtensionOIDs().contains(SCT_OID)) + ",内嵌 SCT 个数 " + ss.size());
        for (Sct s : ss) { String id = Base64.getEncoder().encodeToString(s.logId()); JsonNode l = logs.get(id); say("    SCT:version " + s.version() + ",日志 ID " + hex(s.logId(), 6) + "…," + (l == null ? "不在当前日志列表里" : l.get("description").asText() + "(运营者 " + l.get("operator").asText() + ",状态 " + state(l) + ")") + ",时间戳 " + Instant.ofEpochMilli(s.ts()) + ",签名算法 hash=" + s.hashAlg() + " sig=" + s.sigAlg() + ",签名 " + s.sig().length + " 字节"); } }
    } else if (mode.equals("verify")) {
      for (String host : a[2].split(",")) { List<X509Certificate> ch = chain(dir.resolve(host + ".pem")); X509Certificate leaf = ch.get(0), issuer = ch.get(1); byte[] ih = sha256(issuer.getPublicKey().getEncoded()); byte[] tbs = precertTbs(leaf);
        say(host + ":重建的预证书 TBS " + tbs.length + " 字节(去掉 SCT 扩展之后;原始叶子 TBS " + org.bouncycastle.asn1.x509.Certificate.getInstance(leaf.getEncoded()).getTBSCertificate().getEncoded(ASN1Encoding.DER).length + " 字节)");
        for (Sct s : scts(leaf)) { JsonNode l = logs.get(Base64.getEncoder().encodeToString(s.logId())); if (l == null) { say("    SCT 的日志不在列表里,跳过"); continue; } PublicKey key = KeyFactory.getInstance(l.get("key").asText().length() < 150 ? "EC" : "EC").generatePublic(new java.security.spec.X509EncodedKeySpec(Base64.getDecoder().decode(l.get("key").asText())));
          boolean ok = verify(s, ih, tbs, key); X509Certificate fake = leaf; byte[] tbs2 = precertTbs(leaf); tbs2[tbs2.length - 1] ^= 1; boolean tamper = false; try { tamper = verify(s, ih, tbs2, key); } catch (Exception e) { }
          byte[] ih2 = ih.clone(); ih2[0] ^= 1; boolean wrongIssuer = verify(s, ih2, tbs, key); Sct late = new Sct(s.version(), s.logId(), s.ts() + 1, s.ext(), s.hashAlg(), s.sigAlg(), s.sig()); boolean wrongTs = verify(late, ih, tbs, key);
          say("    " + l.get("description").asText() + ":SCT 签名用日志公钥验证 = " + ok + ";改 TBS 的 1 位 = " + tamper + ";错误的颁发者哈希 = " + wrongIssuer + ";时间戳加 1 ms = " + wrongTs); } }
    } else if (mode.equals("proof")) {
      String host = a[2]; List<X509Certificate> ch = chain(dir.resolve(host + ".pem")); X509Certificate leaf = ch.get(0), issuer = ch.get(1); byte[] ih = sha256(issuer.getPublicKey().getEncoded()); byte[] tbs = precertTbs(leaf);
      HttpClient hc = HttpClient.newBuilder().proxy(ProxySelector.of(new InetSocketAddress("127.0.0.1", 1087))).connectTimeout(Duration.ofSeconds(20)).build(); ObjectMapper om = new ObjectMapper();
      for (Sct s : scts(leaf)) { JsonNode l = logs.get(Base64.getEncoder().encodeToString(s.logId())); if (l == null) continue; String url = l.get("url").asText(); if (!url.endsWith("/")) url += "/";
        try { byte[] leafBytes = cat(new byte[]{0, 0}, entry(s, ih, tbs)); byte[] leafHash = sha256(new byte[]{0}, leafBytes); String sthBody = hc.send(HttpRequest.newBuilder(URI.create(url + "ct/v1/get-sth")).timeout(Duration.ofSeconds(30)).build(), HttpResponse.BodyHandlers.ofString()).body(); JsonNode sth = om.readTree(sthBody); long size = sth.get("tree_size").asLong(); byte[] root = Base64.getDecoder().decode(sth.get("sha256_root_hash").asText());
          say(l.get("description").asText() + ":get-sth → tree_size " + size + ",时间戳 " + Instant.ofEpochMilli(sth.get("timestamp").asLong()) + ",根哈希 " + hex(root, 8) + "…");
          PublicKey key = KeyFactory.getInstance("EC").generatePublic(new java.security.spec.X509EncodedKeySpec(Base64.getDecoder().decode(l.get("key").asText()))); Signature sg = Signature.getInstance("SHA256withECDSA"); sg.initVerify(key); sg.update(cat(new byte[]{0, 1}, be(sth.get("timestamp").asLong(), 8), be(size, 8), root)); byte[] dsig = Base64.getDecoder().decode(sth.get("tree_head_signature").asText()); ByteBuffer db = ByteBuffer.wrap(dsig); db.get(); db.get(); byte[] sg2 = new byte[db.getShort() & 0xffff]; db.get(sg2);
          say("    STH 签名用日志公钥验证 = " + sg.verify(sg2));
          String q = url + "ct/v1/get-proof-by-hash?hash=" + URLEncoder.encode(Base64.getEncoder().encodeToString(leafHash), "UTF-8") + "&tree_size=" + size; HttpResponse<String> pr = hc.send(HttpRequest.newBuilder(URI.create(q)).timeout(Duration.ofSeconds(30)).build(), HttpResponse.BodyHandlers.ofString());
          if (pr.statusCode() != 200) { say("    get-proof-by-hash 返回 HTTP " + pr.statusCode() + ":" + pr.body().replaceAll("\\s+", " ").substring(0, Math.min(120, pr.body().length()))); continue; }
          JsonNode pj = om.readTree(pr.body()); long idx = pj.get("leaf_index").asLong(); List<byte[]> path = new ArrayList<>(); for (JsonNode n : pj.get("audit_path")) path.add(Base64.getDecoder().decode(n.asText()));
          // RFC 9162 §2.1.3.2 的验证算法
          long fn = idx, sn = size - 1; byte[] r = leafHash; boolean okp = true; for (byte[] p : path) { if (sn == 0) { okp = false; break; } if ((fn & 1) == 1 || fn == sn) { r = sha256(new byte[]{1}, p, r); if ((fn & 1) == 0) { while ((fn & 1) == 0 && fn != 0) { fn >>= 1; sn >>= 1; } } } else { r = sha256(new byte[]{1}, r, p); } fn >>= 1; sn >>= 1; }
          boolean inc = okp && sn == 0 && Arrays.equals(r, root);
          say("    叶子哈希 " + hex(leafHash, 8) + "…;get-proof-by-hash:leaf_index = " + idx + ",审计路径 " + path.size() + " 个哈希;按 RFC 9162 验证包含证明:算出的根与 STH 的根相同 = " + inc);
          byte[] badLeaf = leafHash.clone(); badLeaf[0] ^= 1; long fn2 = idx, sn2 = size - 1; byte[] r2 = badLeaf; for (byte[] p : path) { if (sn2 == 0) break; if ((fn2 & 1) == 1 || fn2 == sn2) { r2 = sha256(new byte[]{1}, p, r2); if ((fn2 & 1) == 0) { while ((fn2 & 1) == 0 && fn2 != 0) { fn2 >>= 1; sn2 >>= 1; } } } else { r2 = sha256(new byte[]{1}, r2, p); } fn2 >>= 1; sn2 >>= 1; } say("    把叶子哈希改 1 位后重新计算:根与 STH 的根相同 = " + Arrays.equals(r2, root));
          String entries = hc.send(HttpRequest.newBuilder(URI.create(url + "ct/v1/get-entries?start=" + idx + "&end=" + idx)).timeout(Duration.ofSeconds(30)).build(), HttpResponse.BodyHandlers.ofString()).body(); JsonNode ej = om.readTree(entries); byte[] lb = Base64.getDecoder().decode(ej.get("entries").get(0).get("leaf_input").asText()); say("    get-entries 取回该下标的条目:leaf_input " + lb.length + " 字节,与本地重建的 MerkleTreeLeaf 逐字节相同 = " + Arrays.equals(lb, leafBytes));
          break; } catch (Exception e) { say("    " + l.get("description").asText() + " 访问失败:" + e.getClass().getSimpleName() + ":" + String.valueOf(e.getMessage()).replaceAll("\\s+", " ")); } }
    }
  }
}
'''
d = jdir('j272a'); (d / 'Main.java').write_text(MAIN); E = jenv('21')
rc = subprocess.run(['javac', '-cp', CP, '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:3500]); sys.exit()
def jv(mode, hosts, timeout=300):
    r = subprocess.run(['java', '-cp', 'out:' + CP, 'Main', mode, str(data), hosts], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); return [l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ')] or [(r.stdout + r.stderr).strip()[:800]]
ll = json.load(open(data / 'loglist.json')); nlogs = sum(len(o['logs']) for o in ll['operators']); states = {}
for o in ll['operators']:
    for l in o['logs']: st = next(iter(l['state'])); states[st] = states.get(st, 0) + 1
print(f'== 一:证书里的 SCT:从真实站点取回证书链(通过 openssl s_client),解析叶子证书的 SCT 扩展(OID 1.3.6.1.4.1.11129.2.4.2)')
print(f'  Google 的公开日志列表 log_list.json:版本 {ll["version"]},时间戳 {ll["log_list_timestamp"]},{len(ll["operators"])} 个运营者、{nlogs} 个日志,按状态 {states}')
print('  取回的证书数(每个站点,含叶子与中间证书):' + str(nchain))
for l in jv('parse', ','.join(hosts)): print('  ' + l)
print('== 二:验证 SCT 的签名:重建预证书 TBS(去掉 SCT 扩展),与日志公钥一起验证')
for l in jv('verify', ','.join(hosts)): print('  ' + l)
print('== 三:包含证明:向日志取 STH 与审计路径,验证这张证书确实在日志的 Merkle 树里')
for h in hosts[:2]:
    for l in jv('proof', h): print('  ' + l)
print('== 四:JDK 自己检查证书透明度吗:用本地 CA 签发的、没有任何 SCT 的证书起一个 TLS 服务端(openssl s_server)')
import socket
sub = lambda *a, **k: subprocess.run(list(a), capture_output=True, text=True, **k)
sub(OSSL, 'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-keyout', str(data / 'ca.key'), '-out', str(data / 'ca.pem'), '-subj', '/CN=Local Test CA', '-days', '2', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign')
sub(OSSL, 'req', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-keyout', str(data / 'srv.key'), '-out', str(data / 'srv.csr'), '-subj', '/CN=localhost')
(data / 'ext.cnf').write_text('subjectAltName=DNS:localhost\nbasicConstraints=CA:FALSE\n')
sub(OSSL, 'x509', '-req', '-in', str(data / 'srv.csr'), '-CA', str(data / 'ca.pem'), '-CAkey', str(data / 'ca.key'), '-CAcreateserial', '-out', str(data / 'srv.pem'), '-days', '2', '-extfile', str(data / 'ext.cnf'))
srv = subprocess.Popen([OSSL, 's_server', '-accept', '9731', '-cert', str(data / 'srv.pem'), '-key', str(data / 'srv.key'), '-www', '-quiet'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1.0)
try:
    for lab, ca in (('把本地 CA 加入信任库', str(data / 'ca.pem')), ('只用 Java 默认的信任库(对照)', 'default')):
        r = subprocess.run(['java', '-cp', 'out:' + CP, 'Main', 'tls', str(data), '9731', ca], cwd=d, env=E, capture_output=True, text=True, timeout=60); print(f'  [{lab}] ' + ' '.join(l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ')))
finally: srv.kill()
cx = subprocess.run([OSSL, 'x509', '-in', str(data / 'srv.pem'), '-noout', '-text'], capture_output=True, text=True).stdout; print('  这张本地证书里 “CT Precertificate SCTs” 出现 = ' + str('CT Precertificate SCTs' in cx))
shutil.rmtree(data, ignore_errors=True)
