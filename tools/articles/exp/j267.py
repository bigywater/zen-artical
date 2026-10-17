import sys, os, re, time, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j267'); R = {}
MAIN = r'''
import java.security.*; import java.security.interfaces.*; import java.security.spec.*; import java.util.*; import java.nio.file.*;
public class Main {
  static String hex(byte[] b) { StringBuilder s = new StringBuilder(); for (byte x : b) s.append(String.format("%02x", x)); return s.toString(); }
  static byte[] unhex(String h) { byte[] b = new byte[h.length() / 2]; for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16); return b; }
  static void say(String s) { System.out.println("RES " + s); }
  static double med(double[] r) { Arrays.sort(r); return r[r.length / 2]; }
  public static void main(String[] a) throws Exception {
    String mode = a[0]; byte[] msg = "hello eddsa".getBytes();
    if (mode.equals("sizes")) {
      KeyPairGenerator g = KeyPairGenerator.getInstance("Ed25519"); KeyPair kp = g.generateKeyPair(); Signature s = Signature.getInstance("Ed25519"); s.initSign(kp.getPrivate()); s.update(msg); byte[] sig = s.sign();
      say("Ed25519:算法 " + kp.getPublic().getAlgorithm() + ",公钥 " + kp.getPublic().getEncoded().length + " 字节(" + kp.getPublic().getFormat() + "),私钥 " + kp.getPrivate().getEncoded().length + " 字节(" + kp.getPrivate().getFormat() + "),签名 " + sig.length + " 字节,公钥类型 " + kp.getPublic().getClass().getInterfaces()[0].getSimpleName());
      KeyPair k448 = KeyPairGenerator.getInstance("Ed448").generateKeyPair(); Signature s4 = Signature.getInstance("Ed448"); s4.initSign(k448.getPrivate()); s4.update(msg); say("Ed448:公钥 " + k448.getPublic().getEncoded().length + " 字节,私钥 " + k448.getPrivate().getEncoded().length + " 字节,签名 " + s4.sign().length + " 字节");
      KeyPairGenerator e = KeyPairGenerator.getInstance("EC"); e.initialize(new ECGenParameterSpec("secp256r1")); KeyPair ek = e.generateKeyPair(); Signature es = Signature.getInstance("SHA256withECDSA"); es.initSign(ek.getPrivate()); es.update(msg); say("ECDSA P-256:公钥 " + ek.getPublic().getEncoded().length + " 字节,私钥 " + ek.getPrivate().getEncoded().length + " 字节,签名(DER)" + es.sign().length + " 字节(长度随 r、s 变化,常见 70–72)");
      KeyPairGenerator r = KeyPairGenerator.getInstance("RSA"); r.initialize(2048); KeyPair rk = r.generateKeyPair(); Signature rs = Signature.getInstance("SHA256withRSA"); rs.initSign(rk.getPrivate()); rs.update(msg); say("RSA 2048:公钥 " + rk.getPublic().getEncoded().length + " 字节,私钥 " + rk.getPrivate().getEncoded().length + " 字节,签名 " + rs.sign().length + " 字节");
      try { KeyPairGenerator.getInstance("Ed25519").initialize(256); say("Ed25519 initialize(256) 成功"); } catch (Throwable t) { say("Ed25519 initialize(256):" + t.getClass().getSimpleName() + ":" + t.getMessage()); }
      say("Signature.getInstance(\"EdDSA\") 的提供者 " + Signature.getInstance("EdDSA").getProvider().getName() + ",Ed25519 的提供者 " + Signature.getInstance("Ed25519").getProvider().getName());
    } else if (mode.equals("determ")) {
      KeyPair kp = KeyPairGenerator.getInstance("Ed25519").generateKeyPair(); Set<String> ed = new HashSet<>(); for (int i = 0; i < 20; i++) { Signature s = Signature.getInstance("Ed25519"); s.initSign(kp.getPrivate()); s.update(msg); ed.add(hex(s.sign())); }
      KeyPairGenerator e = KeyPairGenerator.getInstance("EC"); e.initialize(new ECGenParameterSpec("secp256r1")); KeyPair ek = e.generateKeyPair(); Set<String> ec = new HashSet<>(); for (int i = 0; i < 20; i++) { Signature s = Signature.getInstance("SHA256withECDSA"); s.initSign(ek.getPrivate()); s.update(msg); ec.add(hex(s.sign())); }
      KeyPair rk = KeyPairGenerator.getInstance("RSA").generateKeyPair(); Set<String> rs = new HashSet<>(); for (int i = 0; i < 20; i++) { Signature s = Signature.getInstance("SHA256withRSA"); s.initSign(rk.getPrivate()); s.update(msg); rs.add(hex(s.sign())); }
      Set<String> pss = new HashSet<>(); for (int i = 0; i < 20; i++) { Signature s = Signature.getInstance("RSASSA-PSS"); s.setParameter(new PSSParameterSpec("SHA-256", "MGF1", MGF1ParameterSpec.SHA256, 32, 1)); s.initSign(rk.getPrivate()); s.update(msg); pss.add(hex(s.sign())); }
      say("同一把私钥、同一条消息各签 20 次,不同的签名个数:Ed25519 " + ed.size() + ",ECDSA P-256 " + ec.size() + ",RSA PKCS#1 v1.5 " + rs.size() + ",RSASSA-PSS " + pss.size());
    } else if (mode.equals("rfc")) {
      byte[] seed = unhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"); KeyFactory kf = KeyFactory.getInstance("Ed25519"); PrivateKey priv = kf.generatePrivate(new EdECPrivateKeySpec(NamedParameterSpec.ED25519, seed));
      Signature s = Signature.getInstance("Ed25519"); s.initSign(priv); s.update(new byte[0]); byte[] sig = s.sign(); String expect = "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b";
      say("RFC 8032 测试向量 1(种子 9d61b19d…,空消息):Java 的签名与 RFC 给出的签名完全相同 = " + hex(sig).equals(expect) + "(" + hex(sig).substring(0, 32) + "…)");
      byte[] pubEnc = hex(sig).isEmpty() ? null : null; EdECPrivateKey epk = (EdECPrivateKey) priv; say("EdECPrivateKey.getBytes() 是 " + epk.getBytes().get().length + " 字节(就是 32 字节种子)= " + hex(epk.getBytes().get()).equals(hex(seed)));
      // 把 Java 生成的密钥对导出给 openssl
      KeyPair kp = KeyPairGenerator.getInstance("Ed25519").generateKeyPair(); Path dir = Path.of(a[1]); Files.write(dir.resolve("pub.der"), kp.getPublic().getEncoded()); Files.write(dir.resolve("priv.der"), kp.getPrivate().getEncoded()); Files.write(dir.resolve("msg.txt"), msg);
      Signature j = Signature.getInstance("Ed25519"); j.initSign(kp.getPrivate()); j.update(msg); Files.write(dir.resolve("java.sig"), j.sign()); say("已把 Java 生成的密钥和签名写到文件(公钥 X.509 DER、私钥 PKCS#8 DER、java.sig)");
    } else if (mode.equals("verify-openssl")) {
      Path dir = Path.of(a[1]); PublicKey pub = KeyFactory.getInstance("Ed25519").generatePublic(new X509EncodedKeySpec(Files.readAllBytes(dir.resolve("pub.der")))); byte[] m = Files.readAllBytes(dir.resolve("msg.txt")); byte[] sig = Files.readAllBytes(dir.resolve("ossl.sig"));
      Signature v = Signature.getInstance("Ed25519"); v.initVerify(pub); v.update(m); say("Java 验证 openssl 生成的签名:" + v.verify(sig));
    } else if (mode.equals("tamper")) {
      KeyPair kp = KeyPairGenerator.getInstance("Ed25519").generateKeyPair(); Signature s = Signature.getInstance("Ed25519"); s.initSign(kp.getPrivate()); s.update(msg); byte[] sig = s.sign();
      class V { boolean ok(PublicKey k, byte[] m, byte[] sg) { try { Signature v = Signature.getInstance("Ed25519"); v.initVerify(k); v.update(m); return v.verify(sg); } catch (Exception e) { say("    抛出 " + e.getClass().getSimpleName() + ":" + e.getMessage()); return false; } } }
      V v = new V(); say("原样验证:" + v.ok(kp.getPublic(), msg, sig)); byte[] bad = sig.clone(); bad[0] ^= 1; say("签名第 0 字节翻转 1 位:" + v.ok(kp.getPublic(), msg, bad)); byte[] bad2 = sig.clone(); bad2[40] ^= 0x80; say("签名第 40 字节(S 部分)翻转 1 位:" + v.ok(kp.getPublic(), msg, bad2));
      say("消息改了一个字节:" + v.ok(kp.getPublic(), "hello eddsb".getBytes(), sig)); say("用另一把公钥验证:" + v.ok(KeyPairGenerator.getInstance("Ed25519").generateKeyPair().getPublic(), msg, sig)); say("签名截断成 63 字节:"); say("  结果 " + v.ok(kp.getPublic(), msg, Arrays.copyOf(sig, 63))); say("签名加长到 65 字节:"); say("  结果 " + v.ok(kp.getPublic(), msg, Arrays.copyOf(sig, 65)));
      byte[] mall = sig.clone(); // S + L:Ed25519 的群阶 L = 2^252 + 27742317777372353535851937790883648493,把 S 加上 L 得到另一个数值上不同但模 L 相同的 S
      java.math.BigInteger L = BigInteger("7237005577332262213973186563042994240857116359379907606001950938285454250989"); byte[] sb = Arrays.copyOfRange(sig, 32, 64); byte[] be = new byte[32]; for (int i = 0; i < 32; i++) be[i] = sb[31 - i]; java.math.BigInteger S = new java.math.BigInteger(1, be); java.math.BigInteger S2 = S.add(L); byte[] s2be = S2.toByteArray(); byte[] s2 = new byte[32]; for (int i = 0; i < 32 && i < s2be.length; i++) s2[i] = s2be[s2be.length - 1 - i]; System.arraycopy(s2, 0, mall, 32, 32);
      say("可锻性测试:把 S 换成 S + L(模 L 同余但数值不同,S + L < 2^256):" + v.ok(kp.getPublic(), msg, mall) + "(RFC 8032 要求验证者拒绝 S ≥ L 的签名)");
      Signature wrong = Signature.getInstance("Ed25519"); try { wrong.initVerify(KeyPairGenerator.getInstance("Ed448").generateKeyPair().getPublic()); say("用 Ed448 公钥初始化 Ed25519 的验证:成功"); } catch (Throwable t) { say("用 Ed448 公钥初始化 Ed25519 的验证:" + t.getClass().getSimpleName() + ":" + t.getMessage()); }
    } else if (mode.equals("perf")) {
      KeyPair ed = KeyPairGenerator.getInstance("Ed25519").generateKeyPair(); KeyPairGenerator eg = KeyPairGenerator.getInstance("EC"); eg.initialize(new ECGenParameterSpec("secp256r1")); KeyPair ec = eg.generateKeyPair(); KeyPairGenerator rg = KeyPairGenerator.getInstance("RSA"); rg.initialize(2048); KeyPair rs = rg.generateKeyPair(); rg.initialize(3072); KeyPair rs3 = rg.generateKeyPair();
      String[] names = {"Ed25519", "ECDSA P-256 (SHA256withECDSA)", "RSA 2048 (SHA256withRSA)", "RSA 3072 (SHA256withRSA)"}; KeyPair[] kps = {ed, ec, rs, rs3}; String[] algs = {"Ed25519", "SHA256withECDSA", "SHA256withRSA", "SHA256withRSA"};
      for (int k = 0; k < 4; k++) { Signature s = Signature.getInstance(algs[k]); byte[] sig = null; double[] ts = new double[5], tv = new double[5]; int N = k < 2 ? 4000 : 1000; for (int w = 0; w < 3; w++) for (int i = 0; i < N; i++) { s.initSign(kps[k].getPrivate()); s.update(msg); sig = s.sign(); }
        for (int r = 0; r < 5; r++) { long t0 = System.nanoTime(); for (int i = 0; i < N; i++) { s.initSign(kps[k].getPrivate()); s.update(msg); sig = s.sign(); } ts[r] = (System.nanoTime() - t0) / 1e3 / N; Signature v = Signature.getInstance(algs[k]); t0 = System.nanoTime(); for (int i = 0; i < N * 3; i++) { v.initVerify(kps[k].getPublic()); v.update(msg); v.verify(sig); } tv[r] = (System.nanoTime() - t0) / 1e3 / (N * 3); }
        say(String.format("%-32s 签名 %.0f µs/次(约 %.0f 次/秒),验证 %.0f µs/次(约 %.0f 次/秒)", names[k], med(ts), 1e6 / med(ts), med(tv), 1e6 / med(tv))); }
      long t0 = System.nanoTime(); for (int i = 0; i < 20; i++) KeyPairGenerator.getInstance("Ed25519").generateKeyPair(); double edgen = (System.nanoTime() - t0) / 1e6 / 20; t0 = System.nanoTime(); for (int i = 0; i < 5; i++) { rg.initialize(2048); rg.generateKeyPair(); } double rsgen = (System.nanoTime() - t0) / 1e6 / 5; say(String.format("生成密钥对:Ed25519 约 %.2f ms,RSA 2048 约 %.0f ms", edgen, rsgen));
    }
  }
  static java.math.BigInteger BigInteger(String s) { return new java.math.BigInteger(s); }
}
'''
d = jdir('j267a'); (d / 'Main.java').write_text(MAIN); E = jenv('21'); data = JT / 'j267data'; shutil.rmtree(data, ignore_errors=True); data.mkdir(parents=True)
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def jv(mode, jdk='21', timeout=300):
    r = subprocess.run([JDKS[jdk] + '/bin/java', '-cp', 'out', 'Main', mode, str(data)], cwd=d, env=jenv(jdk), capture_output=True, text=True, timeout=timeout); return [l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ') or l.startswith('    抛出') or l.startswith('  结果')] or [(r.stdout + r.stderr).strip()[:400]]
print('== 一:密钥与签名的大小(JDK 21)')
for l in jv('sizes'): print('  ' + l)
print('== 二:确定性:同一把私钥对同一条消息签 20 次')
for l in jv('determ'): print('  ' + l)
print('== 三:RFC 8032 测试向量与 OpenSSL 互通')
for l in jv('rfc'): print('  ' + l)
OSSL = shutil.which('openssl'); print('  openssl 版本:' + subprocess.run([OSSL, 'version'], capture_output=True, text=True).stdout.strip())
r = subprocess.run([OSSL, 'pkeyutl', '-verify', '-pubin', '-inkey', str(data / 'pub.der'), '-keyform', 'DER', '-rawin', '-in', str(data / 'msg.txt'), '-sigfile', str(data / 'java.sig')], capture_output=True, text=True); print('  openssl 验证 Java 生成的签名:' + (r.stdout + r.stderr).strip())
r = subprocess.run([OSSL, 'pkeyutl', '-sign', '-inkey', str(data / 'priv.der'), '-keyform', 'DER', '-rawin', '-in', str(data / 'msg.txt'), '-out', str(data / 'ossl.sig')], capture_output=True, text=True); print(f'  openssl 用 Java 的私钥签名:退出码 {r.returncode},签名 {os.path.getsize(data / "ossl.sig")} 字节;与 Java 的签名逐字节相同 = {(data / "ossl.sig").read_bytes() == (data / "java.sig").read_bytes()}')
for l in jv('verify-openssl'): print('  ' + l)
print('== 四:篡改与非法输入')
for l in jv('tamper'): print('  ' + l)
print('== 五:性能(JDK 21,单线程,5 轮中位数)')
for l in jv('perf'): print('  ' + l)
shutil.rmtree(data, ignore_errors=True)
