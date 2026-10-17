import os, sys, zipfile, tomllib, hashlib, base64, json


def _log(hook, **kw):
    with open(os.environ['BUILD_LOG'], 'a') as f:
        f.write(json.dumps({'hook': hook, 'pid': os.getpid(), 'ppid': os.getppid(), 'python': sys.executable,
                            'cwd': os.getcwd(), 'args': kw}, ensure_ascii=False) + '\n')


def _meta():
    return tomllib.load(open('pyproject.toml', 'rb'))['project']


def _dist_info(m):
    return m['name'].replace('-', '_') + '-' + m['version'] + '.dist-info'


def _metadata_text(m):
    return 'Metadata-Version: 2.1\nName: ' + m['name'] + '\nVersion: ' + m['version'] + '\nSummary: ' + m.get('description', '') + '\n'


def get_requires_for_build_wheel(config_settings=None):
    _log('get_requires_for_build_wheel', config_settings=config_settings)
    return []


def get_requires_for_build_sdist(config_settings=None):
    _log('get_requires_for_build_sdist')
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    _log('prepare_metadata_for_build_wheel', metadata_directory=os.path.basename(metadata_directory))
    m = _meta()
    d = os.path.join(metadata_directory, _dist_info(m))
    os.makedirs(d)
    open(os.path.join(d, 'METADATA'), 'w').write(_metadata_text(m))
    return os.path.basename(d)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    _log('build_wheel', wheel_directory=os.path.basename(wheel_directory), has_metadata_directory=metadata_directory is not None)
    if os.environ.get('BACKEND_CRASH'):
        raise RuntimeError('后端里出错了')
    m = _meta()
    di = _dist_info(m)
    name = m['name'].replace('-', '_') + '-' + m['version'] + '-py3-none-any.whl'
    files = {}
    for root, _, fs in os.walk('src'):
        for f in fs:
            p = os.path.join(root, f)
            files[os.path.relpath(p, 'src')] = open(p, 'rb').read()
    files[di + '/METADATA'] = _metadata_text(m).encode()
    files[di + '/WHEEL'] = b'Wheel-Version: 1.0\nGenerator: mybackend\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
    rec = ''.join(k + ',sha256=' + base64.urlsafe_b64encode(hashlib.sha256(v).digest()).rstrip(b'=').decode() + ',' + str(len(v)) + '\n' for k, v in files.items()) + di + '/RECORD,,\n'
    files[di + '/RECORD'] = rec.encode()
    with zipfile.ZipFile(os.path.join(wheel_directory, name), 'w') as z:
        for k, v in files.items():
            z.writestr(k, v)
    return name
