"""Versioned source + built UI + retained data. No credentials or runtime DBs."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '交付物'
SKIP = {'.vendor', 'node_modules', '__pycache__', '.pytest_cache', '.playwright-cli',
        'output', 'exports', '交付物', '.git', '.agents', '.codex'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT / '贸势有据-0.5.4-源码与运行包.zip')
    target = parser.parse_args().output.resolve()
    if not target.is_relative_to(ROOT.resolve()):
        raise ValueError('输出必须位于本项目目录内')
    if target.exists():
        raise FileExistsError('保留已有交付包；请选择新的输出文件名')
    target.parent.mkdir(parents=True, exist_ok=True)
    config = ROOT / 'config.local.json'
    private = json.loads(config.read_text(encoding='utf-8')) if config.exists() else {}
    secrets = [str(v).encode() for k, v in private.items() if any(s in k.lower() for s in ['key', 'token', 'secret', 'password']) and v and len(str(v)) >= 8]
    files = []
    for path in sorted(ROOT.rglob('*')):
        rel = path.relative_to(ROOT)
        if not path.is_file() or any(p in SKIP for p in rel.parts):
            continue
        if path.name.startswith(('config.local', '.env')) or path.suffix in {'.sqlite', '.sqlite3', '.db', '.pyc', '.tsbuildinfo', '.log'} or '.sqlite-' in path.name:
            continue
        raw = path.read_bytes()
        if any(secret in raw for secret in secrets):
            raise ValueError('待打包文件包含本地凭据，已停止：' + rel.as_posix())
        files.append((rel.as_posix(), raw))
    hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in files}
    with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files:
            archive.writestr(name, raw)
        archive.writestr('PACKAGE_CHECKSUMS.json', json.dumps(hashes, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert all(hashlib.sha256(archive.read(n)).hexdigest() == h for n, h in hashes.items())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.sha256.txt').write_text(digest + '  ' + target.name + '\n', encoding='utf-8')
    print(json.dumps({'path': str(target), 'files': len(files), 'bytes': target.stat().st_size,
                      'sha256': digest, 'secret_scan': 'passed'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
