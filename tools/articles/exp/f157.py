import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fl import *
from fl import app as mkapp
tee('f157'); R = {}
FILES = {
 'myapp.py': '''
import os, uuid
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
def create_app(upload_dir):
    app = Flask(__name__); app.config.update(TESTING=True, UPLOAD_DIR=str(upload_dir), MAX_CONTENT_LENGTH=100 * 1024)
    @app.post("/upload")
    def upload():
        f = request.files.get("file")
        if f is None or not f.filename: return jsonify(error="no file"), 400
        data = f.read()
        name = f"{uuid.uuid4().hex}{os.path.splitext(secure_filename(f.filename))[1]}"
        with open(os.path.join(app.config["UPLOAD_DIR"], name), "wb") as out: out.write(data)
        return jsonify(saved=name, size=len(data), original=f.filename, ctype=f.mimetype, field=request.form.get("title")), 201
    @app.post("/multi")
    def multi(): fs = request.files.getlist("files"); return jsonify(names=[f.filename for f in fs], sizes=[len(f.read()) for f in fs])
    return app
''',
 'conftest.py': '''
import pytest
from myapp import create_app
@pytest.fixture
def app(tmp_path): return create_app(tmp_path)
@pytest.fixture
def client(app): return app.test_client()
''',
 'test_upload.py': '''
import io
from pathlib import Path
def test_single_file(client, tmp_path):
    r = client.post("/upload", data={"file": (io.BytesIO(b"hello"), "a.txt"), "title": "t1"}, content_type="multipart/form-data")
    j = r.get_json(); print("RESULT single", r.status_code, j)
    assert r.status_code == 201 and j["size"] == 5 and j["field"] == "t1"
    assert (Path(tmp_path) / j["saved"]).read_bytes() == b"hello"
def test_content_type_is_multipart_by_default(client):
    r = client.post("/upload", data={"file": (io.BytesIO(b"x"), "b.png")})
    print("RESULT auto-multipart", r.status_code, r.get_json()); assert r.status_code == 201
def test_declared_mimetype(client):
    r = client.post("/upload", data={"file": (io.BytesIO(b"x"), "c.png", "image/png")}); print("RESULT mimetype", r.get_json()["ctype"]); assert r.get_json()["ctype"] == "image/png"
def test_no_file(client):
    r = client.post("/upload", data={}); print("RESULT nofile", r.status_code, r.get_json()); assert r.status_code == 400
def test_empty_filename(client):
    r = client.post("/upload", data={"file": (io.BytesIO(b"x"), "")}); print("RESULT emptyname", r.status_code, r.get_json()); assert r.status_code == 400
def test_multi(client):
    r = client.post("/multi", data={"files": [(io.BytesIO(b"1"), "1.txt"), (io.BytesIO(b"22"), "2.txt")]}); print("RESULT multi", r.get_json()); assert r.get_json()["sizes"] == [1, 2]
def test_too_large(client):
    r = client.post("/upload", data={"file": (io.BytesIO(b"x" * (200 * 1024)), "big.bin")}); print("RESULT toolarge", r.status_code); assert r.status_code == 413
def test_real_file_from_disk(client, tmp_path):
    p = tmp_path / "src.bin"; p.write_bytes(b"abc" * 10)
    with open(p, "rb") as fh: r = client.post("/upload", data={"file": (fh, "src.bin")})
    print("RESULT disk", r.status_code, r.get_json()["size"]); assert r.get_json()["size"] == 30
def test_stream_position_matters(client):
    buf = io.BytesIO(b"abcdef"); buf.read(3)     # 指针不在开头
    r = client.post("/upload", data={"file": (buf, "p.txt")}); print("RESULT position", r.get_json()["size"])
def test_original_name_sanitized_on_disk(client, tmp_path):
    r = client.post("/upload", data={"file": (io.BytesIO(b"x"), "../../evil name.txt")}); j = r.get_json(); print("RESULT name", repr(j["original"]), j["saved"][-4:], sorted(p.name[-4:] for p in tmp_path.iterdir() if p.name.endswith(".txt")))
    assert all((tmp_path / n).parent == tmp_path for n in [j["saved"]])
''',
}
d = mkapp('f157', FILES)
r = subprocess.run([str(BIN / 'python'), '-m', 'pytest', '-p', 'no:cacheprovider', '-v', '-s', '--no-header'], cwd=d, capture_output=True, text=True, env=env(d)); out = tidy(r.stdout + r.stderr)
print('== 一:一组上传测试(pytest -v -s,真实运行):')
for l in out.splitlines():
    if 'RESULT' in l or 'PASSED' in l or 'FAILED' in l or ' passed' in l or ' failed' in l: print('  ' + l.replace('test_upload.py::', '')[:200])
R['out'] = [l for l in out.splitlines() if 'RESULT' in l or ' passed' in l or ' failed' in l]
save('f157', R)
