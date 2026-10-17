import sys, os, re, time, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j269'); R = {}
MAIN = r'''
import java.nio.file.*; import java.security.*; import java.security.interfaces.*; import java.security.spec.*; import java.util.*;
public class Main {
  static void say(String s) { System.out.println("RES " + s); }
  static String hex(byte[] b) { StringBuilder s = new StringBuilder(); for (byte x : b) s.append(String.format("%02x", x)); return s.toString(); }
  static double med(double[] r) { Arrays.sort(r); return r[r.length / 2]; }
  static PSSParameterSpec spec(String md, int salt) { MGF1ParameterSpec m = md.equals("SHA-1") ? MGF1ParameterSpec.SHA1 : md.equals("SHA-256") ? MGF1ParameterSpec.SHA256 : md.equals("SHA-384") ? MGF1ParameterSpec.SHA384 : MGF1ParameterSpec.SHA512; return new PSSParameterSpec(md, "MGF1", m, salt, 1); }
  static byte[] sign(PrivateKey k, PSSParameterSpec p, byte[] m) throws Exception { Signature s = Signature.getInstance("RSASSA-PSS"); s.setParameter(p); s.initSign(k); s.update(m); return s.sign(); }
  static String verify(PublicKey k, PSSParameterSpec p, byte[] m, byte[] sig) { try { Signature s = Signature.getInstance("RSASSA-PSS"); s.setParameter(p); s.initVerify(k); s.update(m); return String.valueOf(s.verify(sig)); } catch (Throwable t) { return "抛出 " + t.getClass().getSimpleName() + ":" + t.getMessage(); } }
  static String err(Throwable t) { return t.getClass().getSimpleName() + ":" + String.valueOf(t.getMessage()).replaceAll("\\s+", " "); }
  public static void main(String[] a) throws Exception {
    String mode = a[0]; byte[] msg = "hello pss".getBytes(); KeyPairGenerator g = KeyPairGenerator.getInstance("RSA"); g.initialize(2048); KeyPair kp = g.generateKeyPair();
    if (mode.equals("api")) {
      try { Signature s = Signature.getInstance("RSASSA-PSS"); s.initSign(kp.getPrivate()); s.update(msg); byte[] sig = s.sign(); say("RSASSA-PSS 不 setParameter 直接 initSign / sign:成功,签名 " + sig.length + " 字节"); } catch (Throwable t) { say("RSASSA-PSS 不 setParameter 直接 initSign / sign:" + err(t)); }
      for (String n : new String[]{"SHA256withRSA/PSS", "SHA256withRSAandMGF1", "RSASSA-PSS", "SHA1withRSA/PSS"}) { try { Signature s = Signature.getInstance(n); s.initSign(kp.getPrivate()); s.update(msg); say("Signature.getInstance(\"" + n + "\") 可用,sign 成功,签名 " + s.sign().length + " 字节;提供者 " + s.getProvider().getName()); } catch (Throwable t) { say("Signature.getInstance(\"" + n + "\"):" + err(t)); } }
      Signature s = Signature.getInstance("RSASSA-PSS"); s.setParameter(spec("SHA-256", 32)); say("签名参数:getParameters() = " + s.getParameters().getAlgorithm() + " " + s.getParameters().getParameterSpec(PSSParameterSpec.class).getDigestAlgorithm() + "/" + s.getParameters().getParameterSpec(PSSParameterSpec.class).getSaltLength());
      byte[] sig = sign(kp.getPrivate(), spec("SHA-256", 32), msg); say("RSA 2048 + SHA-256 + 盐 32:签名 " + sig.length + " 字节(与密钥的模长相同)");
    } else if (mode.equals("salt")) {
      for (int salt : new int[]{0, 20, 32}) { Set<String> sigs = new HashSet<>(); for (int i = 0; i < 20; i++) sigs.add(hex(sign(kp.getPrivate(), spec("SHA-256", salt), msg))); say("盐长度 " + salt + ":同一消息签 20 次,不同的签名个数 = " + sigs.size()); }
      for (String[] c : new String[][]{{"SHA-256", "222"}, {"SHA-256", "223"}, {"SHA-512", "190"}, {"SHA-512", "191"}, {"SHA-1", "234"}, {"SHA-1", "235"}}) { try { sign(kp.getPrivate(), spec(c[0], Integer.parseInt(c[1])), msg); say("RSA 2048 + " + c[0] + " + 盐 " + c[1] + ":签名成功"); } catch (Throwable t) { say("RSA 2048 + " + c[0] + " + 盐 " + c[1] + ":" + err(t)); } }
      say("上限的计算:emBits = 2048 - 1 = 2047,emLen = ceil(2047 / 8) = 256 字节,最大盐 = emLen - hLen - 2(SHA-256 为 256 - 32 - 2 = 222;SHA-512 为 256 - 64 - 2 = 190;SHA-1 为 256 - 20 - 2 = 234)");
    } else if (mode.equals("mismatch")) {
      byte[] sig = sign(kp.getPrivate(), spec("SHA-256", 32), msg);
      say("同样的参数验证:" + verify(kp.getPublic(), spec("SHA-256", 32), msg, sig)); say("验证时盐长度写 20(签名用 32):" + verify(kp.getPublic(), spec("SHA-256", 20), msg, sig)); say("验证时摘要写 SHA-384(签名用 SHA-256):" + verify(kp.getPublic(), spec("SHA-384", 32), msg, sig));
      say("验证时 MGF1 用 SHA-1、摘要用 SHA-256:" + verify(kp.getPublic(), new PSSParameterSpec("SHA-256", "MGF1", MGF1ParameterSpec.SHA1, 32, 1), msg, sig)); say("验证时用 PKCS#1 v1.5(SHA256withRSA):" + pkcs1verify(kp.getPublic(), msg, sig));
      byte[] bad = sig.clone(); bad[10] ^= 1; say("签名翻转 1 位:" + verify(kp.getPublic(), spec("SHA-256", 32), msg, bad)); say("消息改一个字节:" + verify(kp.getPublic(), spec("SHA-256", 32), "hello psS".getBytes(), sig));
      byte[] v15 = pkcs1sign(kp.getPrivate(), msg); say("PKCS#1 v1.5 的签名用 PSS 验证:" + verify(kp.getPublic(), spec("SHA-256", 32), msg, v15));
      byte[] sig0 = sign(kp.getPrivate(), spec("SHA-256", 0), msg); say("盐 0 签名,验证时写盐 32:" + verify(kp.getPublic(), spec("SHA-256", 32), msg, sig0) + ";写盐 0:" + verify(kp.getPublic(), spec("SHA-256", 0), msg, sig0));
    } else if (mode.equals("pss-key")) {
      KeyPairGenerator pg = KeyPairGenerator.getInstance("RSASSA-PSS"); pg.initialize(new RSAKeyGenParameterSpec(2048, RSAKeyGenParameterSpec.F4, spec("SHA-256", 32))); KeyPair pk = pg.generateKeyPair();
      say("RSASSA-PSS 类型的密钥:算法 " + pk.getPublic().getAlgorithm() + ",公钥编码 " + pk.getPublic().getEncoded().length + " 字节(普通 RSA 公钥是 294 字节,多了 PSS 参数),参数 " + ((RSAPublicKey) pk.getPublic()).getParams().getClass().getSimpleName() + " " + ((PSSParameterSpec) ((RSAPublicKey) pk.getPublic()).getParams()).getDigestAlgorithm() + "/盐 " + ((PSSParameterSpec) ((RSAPublicKey) pk.getPublic()).getParams()).getSaltLength());
      try { byte[] sig = sign(pk.getPrivate(), spec("SHA-256", 32), msg); say("用与密钥参数一致的 PSS 参数签名:成功;验证 " + verify(pk.getPublic(), spec("SHA-256", 32), msg, sig)); } catch (Throwable t) { say("用与密钥参数一致的参数签名:" + err(t)); }
      try { sign(pk.getPrivate(), spec("SHA-512", 32), msg); say("摘要 SHA-512(密钥限定 SHA-256)签名:成功"); } catch (Throwable t) { say("摘要 SHA-512(密钥限定 SHA-256)签名:" + err(t)); }
      try { sign(pk.getPrivate(), spec("SHA-256", 16), msg); say("盐 16(密钥限定最小盐 32)签名:成功"); } catch (Throwable t) { say("盐 16(密钥限定最小盐 32)签名:" + err(t)); }
      try { sign(pk.getPrivate(), spec("SHA-256", 40), msg); say("盐 40(密钥限定最小盐 32)签名:成功"); } catch (Throwable t) { say("盐 40(密钥限定最小盐 32)签名:" + err(t)); }
      try { Signature s = Signature.getInstance("RSASSA-PSS"); s.initSign(pk.getPrivate()); s.update(msg); say("PSS 密钥不 setParameter 签名:成功,签名 " + s.sign().length + " 字节(使用密钥里的参数)"); } catch (Throwable t) { say("PSS 密钥不 setParameter 签名:" + err(t)); }
      try { Signature s = Signature.getInstance("SHA256withRSA"); s.initSign(pk.getPrivate()); say("把 PSS 密钥用于 SHA256withRSA(PKCS#1 v1.5):成功"); } catch (Throwable t) { say("把 PSS 密钥用于 SHA256withRSA(PKCS#1 v1.5):" + err(t)); }
      try { Signature s = Signature.getInstance("RSASSA-PSS"); s.setParameter(spec("SHA-256", 32)); s.initSign(kp.getPrivate()); say("普通 RSA 私钥配 PSS 参数:成功"); } catch (Throwable t) { say("普通 RSA 私钥配 PSS 参数:" + err(t)); }
    } else if (mode.equals("write")) {
      Path dir = Path.of(a[1]); Files.write(dir.resolve("pub.der"), kp.getPublic().getEncoded()); Files.write(dir.resolve("priv.der"), kp.getPrivate().getEncoded()); Files.write(dir.resolve("msg.txt"), msg); Files.write(dir.resolve("java32.sig"), sign(kp.getPrivate(), spec("SHA-256", 32), msg)); Files.write(dir.resolve("java0.sig"), sign(kp.getPrivate(), spec("SHA-256", 0), msg)); say("已写出密钥、消息与 Java 的 PSS 签名(盐 32、盐 0)");
    } else if (mode.equals("verify-ossl")) {
      Path dir = Path.of(a[1]); PublicKey pub = KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(Files.readAllBytes(dir.resolve("pub.der")))); for (String f : new String[]{"ossl_salt32.sig", "ossl_default.sig", "ossl_max.sig"}) { byte[] sig = Files.readAllBytes(dir.resolve(f)); say("Java 验证 " + f + "(OpenSSL 生成)盐 32:" + verify(pub, spec("SHA-256", 32), msg, sig) + ";盐 222(验证时写成最大盐):" + verify(pub, spec("SHA-256", 222), msg, sig) + ";写盐 20:" + verify(pub, spec("SHA-256", 20), msg, sig)); }
    } else if (mode.equals("perf")) {
      String[] names = {"RSA 2048 PKCS#1 v1.5(SHA256withRSA)", "RSA 2048 PSS(SHA-256,盐 32)", "RSA 3072 PKCS#1 v1.5", "RSA 3072 PSS(SHA-256,盐 32)"}; KeyPair k3; g.initialize(3072); k3 = g.generateKeyPair(); KeyPair[] ks = {kp, kp, k3, k3};
      for (int m = 0; m < 4; m++) { boolean pss = m % 2 == 1; byte[] sig = pss ? sign(ks[m].getPrivate(), spec("SHA-256", 32), msg) : pkcs1sign(ks[m].getPrivate(), msg); double[] ts = new double[5], tv = new double[5]; int N = m < 2 ? 500 : 200;
        for (int w = 0; w < 2; w++) for (int i = 0; i < N; i++) { if (pss) sign(ks[m].getPrivate(), spec("SHA-256", 32), msg); else pkcs1sign(ks[m].getPrivate(), msg); }
        for (int r = 0; r < 5; r++) { long t0 = System.nanoTime(); for (int i = 0; i < N; i++) { if (pss) sign(ks[m].getPrivate(), spec("SHA-256", 32), msg); else pkcs1sign(ks[m].getPrivate(), msg); } ts[r] = (System.nanoTime() - t0) / 1e3 / N; t0 = System.nanoTime(); for (int i = 0; i < N * 5; i++) { if (pss) verify(ks[m].getPublic(), spec("SHA-256", 32), msg, sig); else pkcs1verify(ks[m].getPublic(), msg, sig); } tv[r] = (System.nanoTime() - t0) / 1e3 / (N * 5); }
        say(String.format("%-38s 签名 %.0f µs/次,验证 %.1f µs/次", names[m], med(ts), med(tv))); }
    }
  }
  static byte[] pkcs1sign(PrivateKey k, byte[] m) throws Exception { Signature s = Signature.getInstance("SHA256withRSA"); s.initSign(k); s.update(m); return s.sign(); }
  static String pkcs1verify(PublicKey k, byte[] m, byte[] sig) throws Exception { Signature s = Signature.getInstance("SHA256withRSA"); s.initVerify(k); s.update(m); return String.valueOf(s.verify(sig)); }
}
'''
d = jdir('j269a'); (d / 'Main.java').write_text(MAIN); E = jenv('21'); data = JT / 'j269data'; shutil.rmtree(data, ignore_errors=True); data.mkdir(parents=True)
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def jv(mode, timeout=300):
    r = subprocess.run(['java', '-cp', 'out', 'Main', mode, str(data)], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); return [l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ')] or [(r.stdout + r.stderr).strip()[:500]]
print('== 一:API:RSASSA-PSS 需要参数吗(JDK 21)')
for l in jv('api'): print('  ' + l)
print('== 二:盐:长度对签名个数的影响,以及最大盐长度')
for l in jv('salt'): print('  ' + l)
print('== 三:验证时参数不一致')
for l in jv('mismatch'): print('  ' + l)
print('== 四:RSASSA-PSS 类型的密钥(带参数限制)')
for l in jv('pss-key'): print('  ' + l)
print('== 五:与 OpenSSL 互通')
jv('write'); OSSL = shutil.which('openssl')
def ossl(*args): r = subprocess.run([OSSL, *args], capture_output=True, text=True); return (r.returncode, (r.stdout + r.stderr).strip())
base = ['-inkey', str(data / 'pub.der'), '-keyform', 'DER', '-pubin', '-rawin', '-in', str(data / 'msg.txt')]
for lab, sigf, salt in (('Java 盐 32', 'java32.sig', '32'), ('Java 盐 0', 'java0.sig', '0')):
    rc, o = ossl('pkeyutl', '-verify', *base, '-sigfile', str(data / sigf), '-pkeyopt', 'rsa_padding_mode:pss', '-digest', 'sha256', '-pkeyopt', f'rsa_pss_saltlen:{salt}'); print(f'  openssl 验证 {lab} 的签名(指定盐 {salt}):{o.splitlines()[0] if o else rc}')
rc, o = ossl('pkeyutl', '-verify', *base, '-sigfile', str(data / 'java32.sig'), '-pkeyopt', 'rsa_padding_mode:pss', '-digest', 'sha256', '-pkeyopt', 'rsa_pss_saltlen:0'); print(f'  openssl 验证 Java 盐 32 的签名(指定盐 0):{o.splitlines()[0] if o else rc}')
rc, o = ossl('pkeyutl', '-verify', *base, '-sigfile', str(data / 'java32.sig'), '-pkeyopt', 'rsa_padding_mode:pss', '-digest', 'sha256', '-pkeyopt', 'rsa_pss_saltlen:auto'); print(f'  openssl 验证 Java 盐 32 的签名(rsa_pss_saltlen:auto):{o.splitlines()[0] if o else rc}')
for name, opt in (('ossl_salt32.sig', '32'), ('ossl_default.sig', None), ('ossl_max.sig', 'max')):
    args = ['pkeyutl', '-sign', '-inkey', str(data / 'priv.der'), '-keyform', 'DER', '-rawin', '-in', str(data / 'msg.txt'), '-out', str(data / name), '-pkeyopt', 'rsa_padding_mode:pss', '-digest', 'sha256'] + (['-pkeyopt', f'rsa_pss_saltlen:{opt}'] if opt else [])
    rc, o = ossl(*args); print(f'  openssl 用 PSS 签名(盐 {opt or "默认(不指定)"}):退出码 {rc},{os.path.getsize(data / name) if rc == 0 else o} 字节')
for l in jv('verify-ossl'): print('  ' + l)
print('== 六:性能(JDK 21,单线程,5 轮中位数)')
for l in jv('perf'): print('  ' + l)
shutil.rmtree(data, ignore_errors=True)
