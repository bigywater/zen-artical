import sys, os, re, time, shutil; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j271'); R = {}
MAIN = r'''
import java.math.BigInteger; import java.nio.file.*; import java.security.*; import java.security.interfaces.*; import java.security.spec.*; import java.util.*; import javax.crypto.spec.*;
public class Main {
  static void say(String s) { System.out.println("RES " + s); }
  static String err(Throwable t) { return t.getClass().getSimpleName() + ":" + String.valueOf(t.getMessage()).replaceAll("\\s+", " "); }
  static double med(double[] r) { Arrays.sort(r); return r[r.length / 2]; }
  static String hex(byte[] b) { StringBuilder s = new StringBuilder(); for (byte x : b) s.append(String.format("%02x", x)); return s.toString(); }
  public static void main(String[] a) throws Exception {
    String mode = a[0];
    if (mode.equals("defaults")) {
      for (String alg : new String[]{"RSA", "DSA", "EC", "DH", "Ed25519", "Ed448", "X25519", "X448", "RSASSA-PSS", "EdDSA", "XDH"}) { try { KeyPair kp = KeyPairGenerator.getInstance(alg).generateKeyPair(); String sz = kp.getPublic() instanceof RSAPublicKey r ? r.getModulus().bitLength() + " 位模数" : kp.getPublic() instanceof ECPublicKey e ? "曲线阶 " + e.getParams().getOrder().bitLength() + " 位" : kp.getPublic() instanceof DSAPublicKey d ? d.getParams().getP().bitLength() + " 位素数 p" : kp.getPublic() instanceof javax.crypto.interfaces.DHPublicKey dh ? dh.getParams().getP().bitLength() + " 位素数 p" : kp.getPublic().getAlgorithm();
          say(String.format("%-11s 不 initialize 直接 generateKeyPair():%s;公钥编码 %d 字节、私钥编码 %d 字节;提供者 %s", alg, sz, kp.getPublic().getEncoded().length, kp.getPrivate().getEncoded().length, KeyPairGenerator.getInstance(alg).getProvider().getName())); } catch (Throwable t) { say(String.format("%-11s %s", alg, err(t))); } }
    } else if (mode.equals("rsa")) {
      for (int bits : new int[]{511, 512, 1023, 1024, 2048, 4097, 16384, 16385}) { try { KeyPairGenerator g = KeyPairGenerator.getInstance("RSA"); g.initialize(bits); long t0 = System.nanoTime(); KeyPair kp = bits >= 8192 ? null : g.generateKeyPair(); say("RSA initialize(" + bits + "):成功" + (kp == null ? "(未实际生成,只检查参数)" : ",模数 " + ((RSAPublicKey) kp.getPublic()).getModulus().bitLength() + " 位") ); } catch (Throwable t) { say("RSA initialize(" + bits + "):" + err(t)); } }
      KeyPairGenerator g = KeyPairGenerator.getInstance("RSA"); g.initialize(2048); RSAPublicKey pk = (RSAPublicKey) g.generateKeyPair().getPublic(); say("默认公钥指数 e = " + pk.getPublicExponent());
      for (BigInteger e : new BigInteger[]{BigInteger.valueOf(3), BigInteger.valueOf(17), RSAKeyGenParameterSpec.F4, BigInteger.valueOf(65539), BigInteger.TWO, BigInteger.valueOf(4), BigInteger.ONE}) { try { KeyPairGenerator g2 = KeyPairGenerator.getInstance("RSA"); g2.initialize(new RSAKeyGenParameterSpec(2048, e)); say("RSAKeyGenParameterSpec(2048, e = " + e + "):成功,公钥指数 " + ((RSAPublicKey) g2.generateKeyPair().getPublic()).getPublicExponent()); } catch (Throwable t) { say("RSAKeyGenParameterSpec(2048, e = " + e + "):" + err(t)); } }
      RSAPrivateCrtKey sk = (RSAPrivateCrtKey) g.generateKeyPair().getPrivate(); say("私钥是 RSAPrivateCrtKey:p " + sk.getPrimeP().bitLength() + " 位,q " + sk.getPrimeQ().bitLength() + " 位,p×q = n " + sk.getPrimeP().multiply(sk.getPrimeQ()).equals(sk.getModulus()) + ",d " + sk.getPrivateExponent().bitLength() + " 位,保存了 CRT 参数 dP、dQ、qInv");
      int exact = 0, N = 200; for (int i = 0; i < N; i++) { KeyPair kp = g.generateKeyPair(); if (((RSAPublicKey) kp.getPublic()).getModulus().bitLength() == 2048) exact++; } say("生成 " + N + " 把 initialize(2048) 的 RSA 密钥:模数恰好 2048 位的有 " + exact + " 把");
    } else if (mode.equals("ec")) {
      for (int bits : new int[]{192, 224, 255, 256, 384, 521, 522}) { try { KeyPairGenerator g = KeyPairGenerator.getInstance("EC"); g.initialize(bits); ECPublicKey k = (ECPublicKey) g.generateKeyPair().getPublic(); say("EC initialize(" + bits + "):成功,曲线 " + k.getParams().toString().replaceAll(",.*", "") + ",阶 " + k.getParams().getOrder().bitLength() + " 位"); } catch (Throwable t) { say("EC initialize(" + bits + "):" + err(t)); } }
      for (String c : new String[]{"secp256r1", "secp384r1", "secp521r1", "secp256k1", "secp224r1", "brainpoolP256r1", "prime256v1", "NIST P-256", "X9.62 prime256v1", "1.2.840.10045.3.1.7"}) { try { KeyPairGenerator g = KeyPairGenerator.getInstance("EC"); g.initialize(new ECGenParameterSpec(c)); ECPublicKey k = (ECPublicKey) g.generateKeyPair().getPublic(); say("ECGenParameterSpec(\"" + c + "\"):成功,阶 " + k.getParams().getOrder().bitLength() + " 位"); } catch (Throwable t) { say("ECGenParameterSpec(\"" + c + "\"):" + err(t)); } }
      Set<String> prov = new TreeSet<>(); for (Provider p : Security.getProviders()) for (Provider.Service s : p.getServices()) if (s.getType().equals("KeyPairGenerator")) prov.add(s.getAlgorithm()); say("所有提供者里注册的 KeyPairGenerator 算法:" + prov);
    } else if (mode.equals("time")) {
      String[][] cfg = {{"RSA", "2048"}, {"RSA", "3072"}, {"RSA", "4096"}, {"EC", "256"}, {"EC", "384"}, {"EC", "521"}, {"Ed25519", ""}, {"X25519", ""}, {"DH", "2048"}, {"DSA", "2048"}};
      for (String[] c : cfg) { int N = c[0].equals("RSA") ? (c[1].equals("4096") ? 12 : 30) : c[0].equals("DH") || c[0].equals("DSA") ? 6 : 200; KeyPairGenerator g = KeyPairGenerator.getInstance(c[0]); if (!c[1].isEmpty()) g.initialize(Integer.parseInt(c[1])); for (int w = 0; w < 2; w++) g.generateKeyPair(); double[] t = new double[N]; for (int i = 0; i < N; i++) { long t0 = System.nanoTime(); g.generateKeyPair(); t[i] = (System.nanoTime() - t0) / 1e6; } Arrays.sort(t); say(String.format("%-8s %-5s %d 次:最快 %.2f ms,中位数 %.2f ms,最慢 %.2f ms(最慢 / 中位数 = %.1f)", c[0], c[1], N, t[0], t[N / 2], t[N - 1], t[N - 1] / t[N / 2])); }
    } else if (mode.equals("seed")) {
      for (String alg : new String[]{"SHA1PRNG", "DRBG", "NativePRNG"}) { try { List<String> mods = new ArrayList<>(); for (int i = 0; i < 2; i++) { SecureRandom sr = SecureRandom.getInstance(alg); sr.setSeed(12345L); KeyPairGenerator g = KeyPairGenerator.getInstance("RSA"); g.initialize(1024, sr); mods.add(((RSAPublicKey) g.generateKeyPair().getPublic()).getModulus().toString(16).substring(0, 24)); }
          say(alg + ":用 setSeed(12345) 的 SecureRandom 各生成一把 RSA 1024 密钥,两次的模数" + (mods.get(0).equals(mods.get(1)) ? "完全相同(密钥可重现)" : "不同") + ":" + mods); } catch (Throwable t) { say(alg + ":" + err(t)); } }
      try { SecureRandom sr1 = SecureRandom.getInstance("SHA1PRNG"); sr1.setSeed(1L); SecureRandom sr2 = SecureRandom.getInstance("SHA1PRNG"); sr2.setSeed(1L); KeyPairGenerator g1 = KeyPairGenerator.getInstance("EC"); g1.initialize(256, sr1); KeyPairGenerator g2 = KeyPairGenerator.getInstance("EC"); g2.initialize(256, sr2); say("SHA1PRNG + setSeed(1):EC P-256 私钥相同 = " + Arrays.equals(g1.generateKeyPair().getPrivate().getEncoded(), g2.generateKeyPair().getPrivate().getEncoded())); } catch (Throwable t) { say("EC:" + err(t)); }
      SecureRandom sr = new SecureRandom(); say("默认 new SecureRandom() 的算法 " + sr.getAlgorithm() + ",提供者 " + sr.getProvider().getName() + ";KeyPairGenerator 不传 SecureRandom 时使用 " + "JDK 内部的默认实例(与它相同类型)");
      SecureRandom s1 = SecureRandom.getInstance("SHA1PRNG"); s1.setSeed(42L); byte[] b1 = new byte[8]; s1.nextBytes(b1); SecureRandom s2 = SecureRandom.getInstance("SHA1PRNG"); byte[] x = new byte[8]; s2.nextBytes(x); s2.setSeed(42L); byte[] b2 = new byte[8]; s2.nextBytes(b2); say("SHA1PRNG:先 setSeed(42) 再取字节 " + hex(b1) + ";先取字节再 setSeed(42)(补充种子而不是替换)得到 " + hex(b2) + "(两者不同:setSeed 在第一次取字节之后只是追加熵)");
    } else if (mode.equals("write")) {
      Path dir = Path.of(a[1]); for (String[] c : new String[][]{{"RSA", "2048"}, {"EC", "256"}, {"Ed25519", ""}}) { KeyPairGenerator g = KeyPairGenerator.getInstance(c[0]); if (!c[1].isEmpty()) g.initialize(Integer.parseInt(c[1])); KeyPair kp = g.generateKeyPair(); Files.write(dir.resolve(c[0] + ".priv.der"), kp.getPrivate().getEncoded()); Files.write(dir.resolve(c[0] + ".pub.der"), kp.getPublic().getEncoded()); say(c[0] + ":私钥 getFormat() = " + kp.getPrivate().getFormat() + ",公钥 getFormat() = " + kp.getPublic().getFormat() + ",私钥 " + kp.getPrivate().getEncoded().length + " 字节"); }
    }
  }
}
'''
d = jdir('j271a'); (d / 'Main.java').write_text(MAIN)
for jdk in ('17', '21', '27'):
    rc = subprocess.run([JDKS[jdk] + '/bin/javac', '-d', f'out{jdk}', 'Main.java'], cwd=d, env=jenv(jdk), capture_output=True, text=True)
    if rc.returncode: print(jdk, rc.stderr[:1500]); sys.exit()
data = JT / 'j271data'; shutil.rmtree(data, ignore_errors=True); data.mkdir(parents=True)
def jv(mode, jdk='21', timeout=600):
    r = subprocess.run([JDKS[jdk] + '/bin/java', '-cp', f'out{jdk}', 'Main', mode, str(data)], cwd=d, env=jenv(jdk), capture_output=True, text=True, timeout=timeout); return [l[4:] for l in (r.stdout + r.stderr).splitlines() if l.startswith('RES ')] or [(r.stdout + r.stderr).strip()[:500]]
print('== 一:不调用 initialize 时的默认参数(JDK 17、21、27 各一次)')
for jdk in ('17', '21', '27'):
    print(f'  [JDK {jdk}]'); [print('      ' + l[:210]) for l in jv('defaults', jdk) if l.startswith(('RSA ', 'DSA', 'EC ', 'DH ', 'Ed25519', 'X25519', 'RSASSA'))]
print('== 二:RSA:密钥长度的边界与公钥指数(JDK 21)')
for l in jv('rsa'): print('  ' + l)
print('== 三:EC:按位数与按曲线名初始化(JDK 21)')
for l in jv('ec'): print('  ' + l[:300])
print('== 四:生成耗时的分布(JDK 21)')
for l in jv('time'): print('  ' + l)
print('== 五:用固定种子的 SecureRandom 生成密钥')
for l in jv('seed'): print('  ' + l)
print('== 六:编码格式与 OpenSSL 解析')
for l in jv('write'): print('  ' + l)
OSSL = shutil.which('openssl')
for c in ('RSA', 'EC', 'Ed25519'):
    r = subprocess.run([OSSL, 'pkey', '-inform', 'DER', '-in', str(data / f'{c}.priv.der'), '-noout', '-text'], capture_output=True, text=True); first = r.stdout.splitlines()[0] if r.stdout else r.stderr[:100]
    r2 = subprocess.run([OSSL, 'pkey', '-inform', 'DER', '-pubin', '-in', str(data / f'{c}.pub.der'), '-noout', '-text'], capture_output=True, text=True); first2 = r2.stdout.splitlines()[0] if r2.stdout else r2.stderr[:100]
    print(f'  openssl pkey 读取 {c}.priv.der:{first};读取 {c}.pub.der:{first2}')
shutil.rmtree(data, ignore_errors=True)
