"""JPA 实验辅助:Hibernate ORM 6.6.4 + 本机真实 PostgreSQL(PGI,端口 9501)。
jpa(name, files, classes, ...) 写入源码与 persistence.xml、编译并运行,返回 (退出码, 输出)。"""
from jl import *
JPA_CP = mcp('org.hibernate.orm:hibernate-core:6.6.4.Final', 'org.postgresql:postgresql:42.7.4')
def persistence_xml(classes, props, pu='demo', port=9501):
    base = {'jakarta.persistence.jdbc.url': f'jdbc:postgresql://127.0.0.1:{port}/lab', 'jakarta.persistence.jdbc.user': 'lab', 'jakarta.persistence.jdbc.password': '',
            'jakarta.persistence.jdbc.driver': 'org.postgresql.Driver', 'hibernate.hbm2ddl.auto': 'create-drop', 'hibernate.show_sql': 'false', 'hibernate.generate_statistics': 'true'}
    base.update(props or {})
    cl = ''.join(f'<class>{c}</class>' for c in classes); pr = ''.join(f'<property name="{k}" value="{v}"/>' for k, v in base.items())
    return f'<?xml version="1.0" encoding="UTF-8"?><persistence xmlns="https://jakarta.ee/xml/ns/persistence" version="3.0"><persistence-unit name="{pu}" transaction-type="RESOURCE_LOCAL"><provider>org.hibernate.jpa.HibernatePersistenceProvider</provider>{cl}<exclude-unlisted-classes>true</exclude-unlisted-classes><properties>{pr}</properties></persistence-unit></persistence>'
def jpa(name, files, classes, main='Main', args=(), props=None, jopts=(), timeout=300, jdk='21', extra_cp=''):
    d = jdir(name); write(d, files); out = d / 'out'; (out / 'META-INF').mkdir(parents=True, exist_ok=True); (out / 'META-INF' / 'persistence.xml').write_text(persistence_xml(classes, props))
    cp = JPA_CP + (':' + extra_cp if extra_cp else ''); e = jenv(jdk); fs = [str(p) for p in d.rglob('*.java')]
    cr = subprocess.run(['javac', '-parameters', '-d', str(out), '-cp', cp, *fs], cwd=d, env=e, capture_output=True, text=True, timeout=timeout)
    if cr.returncode != 0: return cr.returncode, tidy(cr.stdout + cr.stderr)
    r = subprocess.run(['java', '-Dorg.jboss.logging.provider=jdk', '-Djava.util.logging.config.file=' + str(d / 'logging.properties'), *jopts, '-cp', str(out) + ':' + cp, main, *args], cwd=d, env=e, capture_output=True, text=True, timeout=timeout)
    return r.returncode, tidy(r.stdout + r.stderr)
JPA_LOGGING = 'handlers=java.util.logging.ConsoleHandler\n.level=WARNING\njava.util.logging.ConsoleHandler.level=WARNING\n'
