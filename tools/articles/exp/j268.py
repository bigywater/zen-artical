import sys, os, re, time, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j268'); R = {}
MAIN = r'''
import javax.crypto.*; import java.math.BigInteger; import java.nio.file.*; import java.security.*; import java.security.interfaces.*; import java.security.spec.*; import java.util.*;
public class Main {
  static String hex(byte[] b) { StringBuilder s = new StringBuilder(); for (byte x : b) s.append(String.format("%02x", x)); return s.toString(); }
  static byte[] unhex(String h) { byte[] b = new byte[h.length() / 2]; for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16); return b; }
  static void say(String s) { System.out.println("RES " + s); }
  static byte[] rev(byte[] b) { byte[] r = new byte[b.length]; for (int i = 0; i < b.length; i++) r[i] = b[b.length - 1 - i]; return r; }
  static double med(double[] r) { Arrays.sort(r); return r[r.length / 2]; }
  static KeyFactory kf() throws Exception { return KeyFactory.getInstance("X25519"); }
  static byte[] agree(byte[] priv, PublicKey pub) throws Exception { KeyAgreement ka = KeyAgreement.getInstance("X25519"); ka.init(kf().generatePrivate(new XECPrivateKeySpec(NamedParameterSpec.X25519, priv))); ka.doPhase(pub, true); return ka.generateSecret(); }
  static PublicKey pubFromU(BigInteger u) throws Exception { return kf().generatePublic(new XECPublicKeySpec(NamedParameterSpec.X25519, u)); }
  static PublicKey pubFromRaw(byte[] raw) throws Exception { byte[] be = rev(raw); be[0] &= 0x7f; return pubFromU(new BigInteger(1, be)); }
  static byte[] derivePublic(byte[] priv) throws Exception { return agree(priv, pubFromU(BigInteger.valueOf(9))); }
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    if (mode.equals("rfc")) {
      byte[] ap = unhex("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"), bp = unhex("5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb");
      byte[] aPub = derivePublic(ap), bPub = derivePublic(bp);
      say("RFC 7748 §6.1:Alice 的公钥(私钥 × 基点 u=9)与 RFC 相同 = " + hex(aPub).equals("8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a") + ",Bob 的公钥与 RFC 相同 = " + hex(bPub).equals("de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f"));
      byte[] s1 = agree(ap, pubFromRaw(bPub)), s2 = agree(bp, pubFromRaw(aPub)); say("Alice 与 Bob 算出的共享密钥相同 = " + Arrays.equals(s1, s2) + ",与 RFC 的 4a5d9d5b… 相同 = " + hex(s1).equals("4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742") + ",长度 " + s1.length + " 字节");
      KeyPairGenerator g = KeyPairGenerator.getInstance("X25519"); KeyPair k1 = g.generateKeyPair(), k2 = g.generateKeyPair(), k3 = g.generateKeyPair(); KeyAgreement a1 = KeyAgreement.getInstance("X25519"); a1.init(k1.getPrivate()); a1.doPhase(k2.getPublic(), true); byte[] x = a1.generateSecret();
      KeyAgreement a2 = KeyAgreement.getInstance("X25519"); a2.init(k2.getPrivate()); a2.doPhase(k1.getPublic(), true); byte[] y = a2.generateSecret(); KeyAgreement a3 = KeyAgreement.getInstance("X25519"); a3.init(k1.getPrivate()); a3.doPhase(k3.getPublic(), true); byte[] z = a3.generateSecret();
      say("随机生成的三把密钥:k1×k2 与 k2×k1 相同 = " + Arrays.equals(x, y) + ";k1×k3 与 k1×k2 不同 = " + !Arrays.equals(x, z));
      try { a1.generateSecret(); say("同一个 KeyAgreement 对象再次 generateSecret():返回了结果"); } catch (Throwable t) { say("generateSecret() 之后没有重新 init 就再次调用:" + t.getClass().getSimpleName()); }
      KeyAgreement a4 = KeyAgreement.getInstance("X25519"); a4.init(k1.getPrivate()); try { a4.doPhase(k2.getPublic(), false); say("doPhase(lastPhase=false) 成功"); } catch (Throwable t) { say("doPhase(…, false):" + t.getClass().getSimpleName() + ":" + t.getMessage()); }
    } else if (mode.equals("enc")) {
      KeyPair k = KeyPairGenerator.getInstance("X25519").generateKeyPair(); XECPublicKey pk = (XECPublicKey) k.getPublic(); byte[] der = pk.getEncoded(); byte[] raw = Arrays.copyOfRange(der, der.length - 32, der.length);
      say("X25519 公钥的 X.509 编码 " + der.length + " 字节,前 12 字节(算法标识)" + hex(Arrays.copyOf(der, 12)) + ";最后 32 字节是裸的 u 坐标(小端)");
      say("XECPublicKey.getU() = " + pk.getU().toString(16).substring(0, 16) + "…(BigInteger,大端);把 getU() 转成 32 字节小端后与编码里的最后 32 字节相同 = " + Arrays.equals(rev(padded(pk.getU().toByteArray(), 32)), raw));
      XECPrivateKey sk = (XECPrivateKey) k.getPrivate(); say("私钥 PKCS#8 编码 " + sk.getEncoded().length + " 字节,XECPrivateKey.getScalar() 是 " + sk.getScalar().get().length + " 字节;公钥由私钥推出的 u(k × 9)与 getU() 相同 = " + Arrays.equals(derivePublic(sk.getScalar().get()), raw));
      KeyPair k448 = KeyPairGenerator.getInstance("X448").generateKeyPair(); say("X448:公钥编码 " + k448.getPublic().getEncoded().length + " 字节,私钥编码 " + k448.getPrivate().getEncoded().length + " 字节,共享密钥 " + sharedLen("X448") + " 字节");
      KeyPairGenerator eg = KeyPairGenerator.getInstance("EC"); eg.initialize(new ECGenParameterSpec("secp256r1")); KeyPair ek = eg.generateKeyPair(); say("对照 ECDH P-256:公钥编码 " + ek.getPublic().getEncoded().length + " 字节,共享密钥 " + sharedEc(ek) + " 字节");
      try { KeyPairGenerator.getInstance("XDH").initialize(NamedParameterSpec.X25519); say("KeyPairGenerator(\"XDH\") + NamedParameterSpec.X25519 可用"); } catch (Throwable t) { say("XDH:" + t); }
    } else if (mode.equals("clamp")) {
      byte[] base = unhex("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"); String p0 = hex(derivePublic(base));
      byte[] v1 = base.clone(); v1[0] ^= 0x07; say("私钥第 0 字节的低 3 位(会被 clamp 清零)翻转后,公钥是否不变 = " + hex(derivePublic(v1)).equals(p0));
      byte[] v2 = base.clone(); v2[31] ^= 0x80; say("私钥第 31 字节的最高位(会被 clamp 清零)翻转后,公钥是否不变 = " + hex(derivePublic(v2)).equals(p0));
      byte[] v3 = base.clone(); v3[31] ^= 0x40; say("私钥第 31 字节的次高位(会被 clamp 置 1)翻转后,公钥是否不变 = " + hex(derivePublic(v3)).equals(p0));
      byte[] v4 = base.clone(); v4[0] ^= 0x08; say("私钥第 0 字节的第 4 位(不被 clamp 影响)翻转后,公钥是否不变 = " + hex(derivePublic(v4)).equals(p0));
      Set<String> pubs = new HashSet<>(); Random r = new Random(1); int same = 0; for (int i = 0; i < 1000; i++) { byte[] s = new byte[32]; r.nextBytes(s); byte[] t = s.clone(); t[0] ^= (byte) (r.nextInt(8)); if (hex(derivePublic(s)).equals(hex(derivePublic(t)))) same++; pubs.add(hex(derivePublic(s))); }
      say("1000 对随机私钥(每对只在低 3 位上不同):公钥相同的有 " + same + " 对;1000 把随机私钥的公钥互不相同 = " + (pubs.size() == 1000));
    } else if (mode.equals("lowork")) {
      byte[] priv = unhex("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"); String[][] pts = {{"u = 0(阶 1 的点)", "0"}, {"u = 1(阶 4 的点)", "1"}, {"u = 325606250916557431795983626356110631294008115727848805560023387167927233504(阶 8 的点)", "325606250916557431795983626356110631294008115727848805560023387167927233504"}, {"u = 39382357235489614581723060781553021112529911719440698176882885853963445705823(阶 8 的点)", "39382357235489614581723060781553021112529911719440698176882885853963445705823"}, {"u = p - 1(2^255 - 20,阶 2 的点)", new BigInteger("2").pow(255).subtract(BigInteger.valueOf(20)).toString()}, {"u = 9(基点)", "9"}};
      for (String[] c : pts) { try { byte[] s = agree(priv, pubFromU(new BigInteger(c[1]))); say(c[0].replaceAll("u = (\\d{12})\\d+", "u = $1…") + " → 共享密钥 " + hex(s).substring(0, 16) + "…" + (isZero(s) ? "(全零)" : "")); } catch (Throwable t) { say(c[0].replaceAll("u = (\\d{12})\\d+", "u = $1…") + " → " + t.getClass().getSimpleName() + ":" + t.getMessage()); } }
      BigInteger p = BigInteger.TWO.pow(255).subtract(BigInteger.valueOf(19)); try { byte[] s = agree(priv, pubFromU(p.add(BigInteger.valueOf(9)))); say("u = p + 9(与基点 9 同余,超出域):共享密钥与 u = 9 相同 = " + Arrays.equals(s, agree(priv, pubFromU(BigInteger.valueOf(9))))); } catch (Throwable t) { say("u = p + 9:" + t.getClass().getSimpleName() + ":" + t.getMessage()); }
      try { pubFromU(BigInteger.valueOf(-1)); say("u = -1:成功"); } catch (Throwable t) { say("u = -1:" + t.getClass().getSimpleName()); }
      try { pubFromU(BigInteger.TWO.pow(256)); say("u = 2^256:成功构造公钥"); } catch (Throwable t) { say("u = 2^256:" + t.getClass().getSimpleName() + ":" + t.getMessage()); }
      try { KeyAgreement ka = KeyAgreement.getInstance("X25519"); ka.init(KeyPairGenerator.getInstance("X25519").generateKeyPair().getPrivate()); ka.doPhase(KeyPairGenerator.getInstance("X448").generateKeyPair().getPublic(), true); say("X25519 私钥 + X448 公钥:成功"); } catch (Throwable t) { say("X25519 私钥 + X448 公钥:" + t.getClass().getSimpleName() + ":" + t.getMessage()); }
    } else if (mode.equals("write")) {
      Path dir = Path.of(a[1]); KeyPair k = KeyPairGenerator.getInstance("X25519").generateKeyPair(); KeyPair o = KeyPairGenerator.getInstance("X25519").generateKeyPair(); Files.write(dir.resolve("a.priv.der"), k.getPrivate().getEncoded()); Files.write(dir.resolve("b.pub.der"), o.getPublic().getEncoded()); Files.write(dir.resolve("b.priv.der"), o.getPrivate().getEncoded()); Files.write(dir.resolve("a.pub.der"), k.getPublic().getEncoded());
      KeyAgreement ka = KeyAgreement.getInstance("X25519"); ka.init(k.getPrivate()); ka.doPhase(o.getPublic(), true); Files.write(dir.resolve("java.secret"), ka.generateSecret()); say("已写出 A 私钥、B 公钥与 Java 算出的共享密钥");
    } else if (mode.equals("perf")) {
      String[] names = {"X25519", "X448", "ECDH P-256", "DH 2048(FFDHE)"}; KeyPairGenerator[] gens = new KeyPairGenerator[4]; gens[0] = KeyPairGenerator.getInstance("X25519"); gens[1] = KeyPairGenerator.getInstance("X448"); gens[2] = KeyPairGenerator.getInstance("EC"); ((KeyPairGenerator) gens[2]).initialize(new ECGenParameterSpec("secp256r1")); gens[3] = KeyPairGenerator.getInstance("DH"); gens[3].initialize(new DHGenParameterSpec(new BigInteger("FFFFFFFFFFFFFFFFADF85458A2BB4A9AAFDC5620273D3CF1D8B9C583CE2D3695A9E13641146433FBCC939DCE249B3EF97D2FE363630C75D8F681B202AEC4617AD3DF1ED5D5FD65612433F51F5F066ED0856365553DED1AF3B557135E7F57C935984F0C70E0E68B77E2A689DAF3EFE8721DF158A136ADE73530ACCA4F483A797ABC0AB182B324FB61D108A94BB2C8E3FBB96ADAB760D7F4681D4F42A3DE394DF4AE56EDE76372BB190B07A7C8EE0A6D709E02FCE1CDF7E2ECC03404CD28342F619172FE9CE98583FF8E4F1232EEF28183C3FE3B1B4C6FAD733BB5FCBC2EC22005C58EF1837D1683B2C6F34A26C1B2EFFA886B423861285C97FFFFFFFFFFFFFFFF", 16), BigInteger.TWO).getG() == null ? null : null) == null ? null : null;
      for (int k = 0; k < 3; k++) { KeyPair mine = gens[k].generateKeyPair(), peer = gens[k].generateKeyPair(); String alg = k == 0 ? "X25519" : k == 1 ? "X448" : "ECDH"; double[] tg = new double[5], ta = new double[5]; int N = 2000;
        for (int w = 0; w < 2; w++) for (int i = 0; i < N; i++) { KeyAgreement ka = KeyAgreement.getInstance(alg); ka.init(mine.getPrivate()); ka.doPhase(peer.getPublic(), true); ka.generateSecret(); }
        for (int r = 0; r < 5; r++) { long t0 = System.nanoTime(); for (int i = 0; i < N; i++) gens[k].generateKeyPair(); tg[r] = (System.nanoTime() - t0) / 1e3 / N; t0 = System.nanoTime(); for (int i = 0; i < N; i++) { KeyAgreement ka = KeyAgreement.getInstance(alg); ka.init(mine.getPrivate()); ka.doPhase(peer.getPublic(), true); ka.generateSecret(); } ta[r] = (System.nanoTime() - t0) / 1e3 / N; }
        say(String.format("%-14s 生成密钥对 %.0f µs/次,密钥协商(init + doPhase + generateSecret)%.0f µs/次(约 %.0f 次/秒)", names[k], med(tg), med(ta), 1e6 / med(ta))); }
    }
  }
  static boolean isZero(byte[] b) { for (byte x : b) if (x != 0) return false; return true; }
  static byte[] padded(byte[] be, int n) { byte[] r = new byte[n]; int len = Math.min(be.length, n); System.arraycopy(be, be.length - len, r, n - len, len); return r; }
  static int sharedLen(String alg) throws Exception { KeyPairGenerator g = KeyPairGenerator.getInstance(alg); KeyPair a = g.generateKeyPair(), b = g.generateKeyPair(); KeyAgreement ka = KeyAgreement.getInstance(alg); ka.init(a.getPrivate()); ka.doPhase(b.getPublic(), true); return ka.generateSecret().length; }
  static int sharedEc(KeyPair a) throws Exception { KeyPairGenerator g = KeyPairGenerator.getInstance("EC"); g.initialize(new ECGenParameterSpec("secp256r1")); KeyPair b = g.generateKeyPair(); KeyAgreement ka = KeyAgreement.getInstance("ECDH"); ka.init(a.getPrivate()); ka.doPhase(b.getPublic(), true); return ka.generateSecret().length; }
}
'''
# 去掉 DH 性能那行里写错的占位表达式,只测 X25519 / X448 / ECDH
import re as _re
MAIN = _re.sub(r'gens\[3\] = KeyPairGenerator\.getInstance\("DH"\);.*?== null \? null : null;', 'gens[3] = null;', MAIN, flags=_re.S)
d = jdir('j268a'); (d / 'Main.java').write_text(MAIN); E = jenv('21'); data = JT / 'j268data'; shutil.rmtree(data, ignore_errors=True); data.mkdir(parents=True)
rc = subprocess.run(['javac', '-d', 'out', 'Main.java'], cwd=d, env=E, capture_output=True, text=True)
if rc.returncode: print(rc.stderr[:2500]); sys.exit()
def jv(mode, timeout=300):
    r = subprocess.run(['java', '-cp', 'out', 'Main', mode, str(data)], cwd=d, env=E, capture_output=True, text=True, timeout=timeout); return [l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ')] or [(r.stdout + r.stderr).strip()[:500]]
print('== 一:RFC 7748 §6.1 的测试向量与基本协商')
for l in jv('rfc'): print('  ' + l)
print('== 二:编码、字节序与大小')
for l in jv('enc'): print('  ' + l)
print('== 三:私钥的 clamp:哪些位不影响公钥')
for l in jv('clamp'): print('  ' + l)
print('== 四:小阶点与非法输入')
for l in jv('lowork'): print('  ' + l)
print('== 五:与 OpenSSL 互通,以及性能')
jv('write'); OSSL = shutil.which('openssl')
r = subprocess.run([OSSL, 'pkeyutl', '-derive', '-inkey', str(data / 'b.priv.der'), '-keyform', 'DER', '-peerkey', str(data / 'a.pub.der'), '-peerform', 'DER', '-out', str(data / 'ossl.secret')], capture_output=True, text=True)
print(f'  openssl pkeyutl -derive(B 的私钥 × A 的公钥):退出码 {r.returncode},输出 {os.path.getsize(data / "ossl.secret")} 字节;与 Java(A 的私钥 × B 的公钥)算出的共享密钥相同 = {(data / "ossl.secret").read_bytes() == (data / "java.secret").read_bytes()}')
for l in jv('perf'): print('  ' + l)
shutil.rmtree(data, ignore_errors=True)
