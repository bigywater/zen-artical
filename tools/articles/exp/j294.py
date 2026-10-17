import sys, os, re, time, zipfile, hashlib, statistics; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jl import *
tee('j294'); R = {}
d = jdir('j294a'); os.chdir(d); J = JDKS['21'] + '/bin/'; E = jenv('21')
def sh(args, cwd=d, tmo=300): r = subprocess.run(args, cwd=cwd, env=E, capture_output=True, text=True, timeout=tmo); return r.returncode, tidy(r.stdout + r.stderr)
write(d, {'src/p/Hello.java': 'package p; public class Hello { public static String msg() { return "hello-original"; } }', 'src/Main.java': 'public class Main { public static void main(String[] a) { System.out.println(p.Hello.msg()); } }'})
(d / 'cls').mkdir(); assert sh([J + 'javac', '-d', 'cls', 'src/p/Hello.java', 'src/Main.java'])[0] == 0
assert sh([J + 'jar', 'cfe', 'app.jar', 'Main', '-C', 'cls', '.'])[0] == 0
def keygen(ks, alias, cn): return sh([J + 'keytool', '-genkeypair', '-alias', alias, '-keyalg', 'RSA', '-keysize', '2048', '-dname', f'CN={cn}, O=Demo', '-validity', '365', '-keystore', ks, '-storepass', 'changeit', '-storetype', 'PKCS12', '-keypass', 'changeit'])
assert keygen('good.p12', 'mykey', 'Release Signer')[0] == 0 and keygen('evil.p12', 'evilkey', 'Attacker')[0] == 0
def sign(src, dst, ks='good.p12', alias='mykey', *extra): return sh([J + 'jarsigner', '-keystore', ks, '-storepass', 'changeit', '-signedjar', dst, *extra, src, alias])
def verify(jar, *extra): return sh([J + 'jarsigner', '-verify', *extra, jar])
def key(t): return ' / '.join(l.strip() for l in t.splitlines() if l.strip() and not l.startswith(('Warning', 'The signer', 'Re-run', 'This jar contains entries whose signer', '  ', '- ')))[:260]
def jarun(jar): rc, t = sh([J + 'java', '-cp', jar, 'Main']); return t.splitlines()[0][:160] if t else '(无输出)'
def tamper(src, dst, rep=None, add=None, drop=()):
    zi = zipfile.ZipFile(src); zo = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
    for i in zi.infolist():
        if any(i.filename.startswith(p) for p in drop): continue
        b = zi.read(i.filename)
        if rep and i.filename == rep[0]: b = b.replace(rep[1], rep[2])
        zo.writestr(i.filename, b)
    if add: zo.writestr(add[0], add[1])
    zo.close()
print('== 一:用 keytool 与 jarsigner 签名一个 jar,验证,以及签名给 jar 增加了什么(JDK 21,RSA 2048 自签名证书)')
rc, t = sign('app.jar', 'signed.jar'); print(f'  jarsigner 签名:rc={rc};输出:{key(t)}')
names = zipfile.ZipFile('signed.jar').namelist(); orig = zipfile.ZipFile('app.jar').namelist(); man = zipfile.ZipFile('signed.jar').read('META-INF/MANIFEST.MF').decode()
print(f'  签名后条目 {len(orig)} → {len(names)} 个,新增:' + ','.join(n for n in names if n not in orig) + f';jar 大小 {os.path.getsize("app.jar")} → {os.path.getsize("signed.jar")} 字节;MANIFEST.MF 里每个类文件一行摘要(JDK 21 默认 SHA-384):' + str(len(re.findall(r'-Digest: ', man))) + ' 条,其中 SHA-384-Digest ' + str(man.count('SHA-384-Digest: ')) + ' 条')
sf = zipfile.ZipFile('signed.jar').read('META-INF/MYKEY.SF').decode(); print('  MYKEY.SF 头部:' + ' | '.join(l for l in sf.splitlines()[:3]) + f';MYKEY.RSA(PKCS#7 签名块)大小 {zipfile.ZipFile("signed.jar").getinfo("META-INF/MYKEY.RSA").file_size} 字节')
rc, t = verify('signed.jar'); print(f'  jarsigner -verify signed.jar:rc={rc};{key(t)}')
rc, t = verify('signed.jar', '-strict'); print(f'  加 -strict:rc={rc}(自签名证书与没有时间戳都会让 -strict 返回非零)')
rc, t = verify('app.jar'); print(f'  未签名的 app.jar:rc={rc};{key(t)}')
print('== 二:对签名过的 jar 动手脚:验证与运行时分别会怎样(原始输出 hello-original)')
tamper('signed.jar', 'bad1.jar', rep=('p/Hello.class', b'hello-original', b'hello-tampered')); rc, t = verify('bad1.jar'); print(f'  (a) 改了已签名类里的字符串(同长度,hello-original → hello-tampered):jarsigner -verify rc={rc};{key(t)};java -cp 运行:{jarun("bad1.jar")}')
tamper('app.jar', 'bad0.jar', rep=('p/Hello.class', b'hello-original', b'hello-tampered')); print(f'  (a\') 同样的改动,但 jar 没有签名:java -cp 运行:{jarun("bad0.jar")}(没有任何报错,输出被改了)')
tamper('signed.jar', 'bad2.jar', add=('Evil.class', b'\xca\xfe\xba\xbe')); rc, t = verify('bad2.jar'); rc2, t2 = verify('bad2.jar', '-strict'); print(f'  (b) 往已签名的 jar 里加一个没有签名的文件:jarsigner -verify rc={rc};{key(t)};加 -strict rc={rc2}')
tamper('signed.jar', 'bad3.jar', drop=('META-INF/MYKEY.',)); rc, t = verify('bad3.jar'); print(f'  (c) 删掉 META-INF/MYKEY.SF 与 .RSA:rc={rc};{key(t)};java -cp 运行:{jarun("bad3.jar")}')
tamper('bad0.jar', 'bad4a.jar', drop=('META-INF/MYKEY.',)); rc, t = sign('bad4a.jar', 'bad4.jar', 'evil.p12', 'evilkey'); rc, t = verify('bad4.jar', '-certs', '-verbose:summary'); print(f'  (d) 攻击者改了类、用自己的证书重新签名:jarsigner -verify rc={rc};{key(t)};签名者:' + ','.join(sorted(set(re.findall(r'CN=[A-Za-z ]+', t)))) + f';java -cp 运行:{jarun("bad4.jar")}')
rc, t = sign('app.jar', 'sha1.jar', 'good.p12', 'mykey', '-digestalg', 'SHA1', '-sigalg', 'SHA1withRSA'); rc2, t2 = verify('sha1.jar'); print(f'  (e) 用 SHA1 摘要与 SHA1withRSA 签名:签名 rc={rc}{"(" + key(t)[:140] + ")" if key(t) else ""};验证 rc={rc2};{key(t2)}')
rc, t = verify('sha1.jar', '-verbose:summary', '-certs'); print('      -certs 输出里与算法有关的行:' + ' / '.join(l.strip() for l in t.splitlines() if 'SHA1' in l or 'sha1' in l.lower() or 'disabled' in l.lower() or 'weak' in l.lower() or 'risk' in l.lower())[:300])
print('== 三:校验和 vs 分离的 PGP 签名(Maven Central 的 .sha256 / .asc 方式),用 BouncyCastle bcpg 1.78.1 在 JDK 21 里真实签名与验证')
BC = mcp('org.bouncycastle:bcpg-jdk18on:1.78.1', 'org.bouncycastle:bcprov-jdk18on:1.78.1')
write(d, {'pgp/Pgp.java': r'''
import org.bouncycastle.bcpg.*; import org.bouncycastle.jce.provider.BouncyCastleProvider; import org.bouncycastle.openpgp.*; import org.bouncycastle.openpgp.jcajce.JcaPGPObjectFactory; import org.bouncycastle.openpgp.operator.jcajce.*; import org.bouncycastle.util.encoders.Hex;
import java.io.*; import java.nio.file.*; import java.security.*; import java.util.*;
public class Pgp {
  static void say(String s) { System.out.println("RES " + s); }
  static PGPKeyPair gen() throws Exception { KeyPairGenerator g = KeyPairGenerator.getInstance("RSA"); g.initialize(2048); return new JcaPGPKeyPair(PublicKeyAlgorithmTags.RSA_GENERAL, g.generateKeyPair(), new Date()); }
  static byte[] sign(PGPKeyPair k, byte[] data) throws Exception {
    PGPSignatureGenerator sg = new PGPSignatureGenerator(new JcaPGPContentSignerBuilder(PublicKeyAlgorithmTags.RSA_GENERAL, HashAlgorithmTags.SHA256).setProvider("BC")); sg.init(PGPSignature.BINARY_DOCUMENT, k.getPrivateKey()); sg.update(data);
    ByteArrayOutputStream b = new ByteArrayOutputStream(); ArmoredOutputStream a = new ArmoredOutputStream(b); sg.generate().encode(a); a.close(); return b.toByteArray(); }
  static boolean verify(PGPPublicKey pub, byte[] asc, byte[] data) throws Exception {
    PGPObjectFactory f = new JcaPGPObjectFactory(PGPUtil.getDecoderStream(new ByteArrayInputStream(asc))); PGPSignature s = ((PGPSignatureList) f.nextObject()).get(0);
    s.init(new JcaPGPContentVerifierBuilderProvider().setProvider("BC"), pub); s.update(data); return s.verify(); }
  static String sha(byte[] b) throws Exception { return Hex.toHexString(MessageDigest.getInstance("SHA-256").digest(b)); }
  public static void main(String[] a) throws Exception {
    Security.addProvider(new BouncyCastleProvider());
    byte[] good = Files.readAllBytes(Paths.get(a[0])), bad = Files.readAllBytes(Paths.get(a[1]));
    PGPKeyPair pub = gen(), other = gen(); byte[] asc = sign(pub, good); String[] lines = new String(asc).split("\n");
    say("发布者密钥:RSA 2048,指纹 " + Hex.toHexString(pub.getPublicKey().getFingerprint()) + ",key id " + Long.toHexString(pub.getKeyID()) + ";另一个无关密钥 key id " + Long.toHexString(other.getKeyID()));
    say("app.jar 的分离签名 app.jar.asc:" + asc.length + " 字节,首行 " + lines[0] + ",末行 " + lines[lines.length - 1] + ";app.jar " + good.length + " 字节(签名大小与 jar 大小无关)");
    say("用发布者的公钥验证原始 jar:" + verify(pub.getPublicKey(), asc, good) + ";验证被篡改的 jar:" + verify(pub.getPublicKey(), asc, bad) + ";用无关的公钥验证原始 jar:" + verify(other.getPublicKey(), asc, good));
    String shaGood = sha(good), shaBad = sha(bad);
    say("攻击者同时替换 jar 与 .sha256 文件:下载到的 jar 的 SHA-256 " + shaBad.substring(0, 16) + "… 与替换后的 .sha256 文件内容 " + shaBad.substring(0, 16) + "… 相等:" + sha(bad).equals(shaBad) + "(校验和检查通过);而 .asc 还是发布者的签名:" + verify(pub.getPublicKey(), asc, bad) + "(签名检查失败)");
    PGPKeyPair evil = gen(); byte[] ascEvil = sign(evil, bad);
    say("攻击者也替换 .asc(用自己的密钥 " + Long.toHexString(evil.getKeyID()) + " 签名):用攻击者的公钥验证 " + verify(evil.getPublicKey(), ascEvil, bad) + ",用发布者的公钥验证 " + verify(pub.getPublicKey(), ascEvil, bad) + "(签名通过与否取决于你信任哪把公钥)");
    byte[] flip = good.clone(); flip[flip.length / 2] ^= 1; say("原始 jar 只翻转 1 个比特:SHA-256 前 16 位 " + shaGood.substring(0, 16) + " → " + sha(flip).substring(0, 16) + ",签名验证 " + verify(pub.getPublicKey(), asc, flip));
  } }'''})
(d / 'pgp/out').mkdir(); _rc, _t = sh([J + 'javac', '-cp', BC, '-d', 'pgp/out', 'pgp/Pgp.java']); assert _rc == 0, _t
r = subprocess.run([J + 'java', '-cp', 'pgp/out:' + BC, 'Pgp', 'app.jar', 'bad0.jar'], cwd=d, env=E, capture_output=True, text=True, timeout=120)
for l in (r.stdout + r.stderr).splitlines(): print('  ' + (l[4:] if l.startswith('RES ') else l))
print('== 四:运行时验证签名的开销:从签名与未签名的 jar 里加载 1000 个类')
src = {f'big/C{i}.java': f'public class C{i} {{ public static int v() {{ return {i}; }} }}' for i in range(1000)}; write(d, src)
write(d, {'big/Load.java': 'public class Load { public static void main(String[] a) throws Exception { long t = System.nanoTime(); long s = 0; for (int i = 0; i < 1000; i++) s += (Integer) Class.forName("C" + i).getMethod("v").invoke(null); System.out.println("RES " + (System.nanoTime() - t) / 1000000.0 + " " + s); } }'})
(d / 'big/out').mkdir(); assert sh([J + 'javac', '-d', 'big/out', *[str(p) for p in (d / 'big').glob('*.java')]])[0] == 0
assert sh([J + 'jar', 'cf', 'big.jar', '-C', 'big/out', '.'])[0] == 0; rc, t = sign('big.jar', 'bigs.jar'); assert rc == 0, t
def load(jar, n=9):
    xs = []
    for _ in range(n):
        r = subprocess.run([J + 'java', '-cp', jar, 'Load'], cwd=d, env=E, capture_output=True, text=True, timeout=120); xs.append(float(next(l for l in r.stdout.splitlines() if l.startswith('RES ')).split()[1]))
    return xs
u = load('big.jar'); s_ = load('bigs.jar')
print(f'  1000 个类,每个新 JVM 里 Class.forName + 调用一次(9 次取中位数):未签名 {statistics.median(u):.0f} ms(最小 {min(u):.0f}、最大 {max(u):.0f}),签名后 {statistics.median(s_):.0f} ms(最小 {min(s_):.0f}、最大 {max(s_):.0f}),比值 {statistics.median(s_) / statistics.median(u):.2f}')
print(f'  jar 大小:未签名 {os.path.getsize(d / "big.jar")} 字节,签名后 {os.path.getsize(d / "bigs.jar")} 字节;MANIFEST.MF 里的摘要条目 {zipfile.ZipFile(d / "bigs.jar").read("META-INF/MANIFEST.MF").decode().count("-Digest: ")} 条')
os.chdir(HERE); shutil.rmtree(d, ignore_errors=True)
