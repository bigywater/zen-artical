"""对外发布文件的写入工具:原子写入 + 同名 .gz(供 nginx 的 gzip_static 直接返回)。"""
import gzip
import os
import tempfile

# 只有文本类文件值得预压缩;png/ico 本身已经是压缩格式
GZIP_SUFFIXES = {'.html', '.css', '.js', '.json', '.svg', '.xml', '.txt', '.webmanifest'}


def atomic_write(path, data):
    # nginx 直接读这些文件:先写同目录临时文件再 rename,读的人要么看到旧版本
    # 要么看到新版本,不会看到写了一半的页面。
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.tmp-')
    try:
        if isinstance(data, str):
            f = os.fdopen(fd, 'w', encoding='utf-8')
        else:
            f = os.fdopen(fd, 'wb')
        with f:
            f.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def gz_path(path):
    return path.with_name(path.name + '.gz')


def write_public(path, data):
    """写对外文件;文本类文件同时写好 .gz。

    nginx 的 gzip_static 只看 .gz 文件在不在、不校验它是否过期,所以两者必须成对更新:
    先写 .gz 再写原文件,任何一步抛异常都直接向上传,不留"新页面 + 旧 .gz"的状态。
    """
    raw = data.encode('utf-8') if isinstance(data, str) else data
    if path.suffix in GZIP_SUFFIXES:
        # mtime=0:相同内容压出相同字节,重复构建不会产生无意义的文件变动
        atomic_write(gz_path(path), gzip.compress(raw, compresslevel=9, mtime=0))
    atomic_write(path, raw)


def remove_public(path):
    for p in (path, gz_path(path)):
        if p.exists():
            p.unlink()
