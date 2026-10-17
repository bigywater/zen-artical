"""
静态资源的内容哈希(cache busting)。

public/assets/ 下手工维护的资源(css、图标)会各生成一份带内容哈希的副本:

    /assets/css/md3-shell.css  ->  /assets/css/md3-shell.4f2a91c3.css

发布出去的页面引用带哈希的路径,nginx 对它设一年的 immutable 缓存;文件内容一变哈希就变,
页面引用跟着变,浏览器自然重新下载,不会出现"改了 css 但访客还在用旧的"。不带哈希的原文件
保留,给动态回落页面和外部引用兜底。
"""
import hashlib
import re

from django.conf import settings

from .files import GZIP_SUFFIXES, atomic_write, write_public

HASHED_NAME = re.compile(r'^(?P<stem>.+)\.(?P<digest>[0-9a-f]{8})(?P<ext>\.[A-Za-z0-9]+)$')
ASSET_URL = re.compile(r'/assets/[A-Za-z0-9_./-]+')


def _assets_dir():
    return settings.PUBLIC_DIR / 'assets'


def _is_generated(path):
    m = HASHED_NAME.match(path.name)
    return bool(m) and path.with_name(m['stem'] + m['ext']).exists()


def _sources():
    root = _assets_dir()
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.rglob('*')
        if p.is_file() and not p.name.startswith('.') and p.suffix != '.gz' and not _is_generated(p)
    )


def fingerprint():
    """确保每个资源的哈希副本都存在,返回 {原路径: 带哈希路径}。幂等、很便宜(几十 KB)。"""
    public = settings.PUBLIC_DIR
    mapping = {}
    for src in _sources():
        data = src.read_bytes()
        digest = hashlib.sha256(data).hexdigest()[:8]
        hashed = src.with_name(f'{src.stem}.{digest}{src.suffix}')
        if not hashed.exists():
            if src.suffix in GZIP_SUFFIXES:
                write_public(hashed, data)
            else:
                atomic_write(hashed, data)
        mapping['/' + src.relative_to(public).as_posix()] = '/' + hashed.relative_to(public).as_posix()
    return mapping


def rewrite(html, mapping):
    """把页面里的资源路径换成带哈希的;不在映射里的(比如正文里随口提到的路径)原样保留。"""
    return ASSET_URL.sub(lambda m: mapping.get(m.group(0), m.group(0)), html)


def prune(mapping):
    """删掉不再被引用的旧哈希副本。只能在所有页面都用新映射重新发布之后调用,
    否则还没重建的旧页面会引用到已被删除的文件。"""
    keep = {settings.PUBLIC_DIR / url.lstrip('/') for url in mapping.values()}
    removed = 0
    root = _assets_dir()
    if not root.is_dir():
        return removed
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        plain = path.with_name(path.name[:-3]) if path.suffix == '.gz' else path
        if _is_generated(plain) and plain not in keep:
            path.unlink()
            removed += 1
    return removed
