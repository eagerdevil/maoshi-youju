"""Extract the actual distribution and verify it without developer configuration."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, default=ROOT / '交付物/贸势有据-0.5.4-源码与运行包-20261103.zip')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--materials-directory', default='参赛材料/0.5.4-提交版-20261103')
    args = parser.parse_args()
    target = args.archive.resolve()
    destination = ROOT / 'output/package-check-054'
    destination.mkdir(parents=True, exist_ok=True)
    extracted = Path(tempfile.mkdtemp(prefix='extracted-', dir=destination))
    checks = []
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            assert (extracted / name).resolve().is_relative_to(extracted.resolve())
            assert not any(part in {'.vendor', 'node_modules'} for part in Path(name).parts)
            assert not Path(name).name.startswith(('config.local', '.env'))
            assert Path(name).suffix not in {'.sqlite', '.sqlite3', '.db', '.log'}
        hashes = json.loads(archive.read('PACKAGE_CHECKSUMS.json'))
        assert set(archive.namelist()) == set(hashes) | {'PACKAGE_CHECKSUMS.json'}
        for name, digest in hashes.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
        archive.extractall(extracted)
    checks += ['archive_paths_safe', 'all_file_hashes_match', 'credentials_and_database_excluded']
    # Dependencies are copied from the verified development installation for this
    # isolated extraction test; this is not a clean-machine pip-install claim.
    shutil.copytree(ROOT / '.vendor', extracted / '.vendor')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f'http://127.0.0.1:{port}'

    def request(path, payload=None):
        req = urllib.request.Request(base + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={} if payload is None else {'Content-Type': 'application/json'})
        with opener.open(req, timeout=45) as response:
            return response.read(), response.headers

    def get_json(path, payload=None):
        return json.loads(request(path, payload)[0])

    log = (extracted / 'verification-server.log').open('w', encoding='utf-8')
    process = subprocess.Popen([sys.executable, '-X', 'utf8', 'run.py', '--port', str(port)],
        cwd=extracted, stdout=log, stderr=log,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        deadline = time.monotonic() + 35
        while True:
            try:
                health = get_json('/api/health')
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('解压服务未能启动；检查verification-server.log')
                time.sleep(.25)
        assert health['version'] == '0.5.4' and health['ai']['has_key'] is False
        assert get_json('/api/saved') == []
        checks += ['extracted_server_started_054', 'no_developer_key', 'no_original_saved_records']
        body, headers = request('/')
        assert b'/assets/index-' in body and 'no-store' in headers['Cache-Control']
        import re
        js_path = re.search(rb'src="(/assets/[^" ]+\.js)"', body).group(1).decode()
        assert len(request(js_path)[0]) > 10000
        checks.append('built_homepage_and_js_load')
        datasets = get_json('/api/datasets')
        assert sum(row['records'] for row in datasets) == 16496
        checks.append('both_retained_datasets_available')
        materials = get_json('/api/materials')
        assert len(materials) == 6
        for item in materials:
            pdf = request(item['url'])[0]
            assert pdf.startswith(b'%PDF-')
            expected = (extracted / args.materials_directory / item['name']).read_bytes()
            assert pdf == expected
        checks.append('all_six_current_pdfs_served_exactly')
        results = []
        for spec in [
            {'mode': 'competition', 'products': ['8703']},
            {'mode': 'bilateral', 'reporter': 'DEU', 'partner': 'CHN', 'products': ['0902']},
            {'mode': 'comparison', 'flow': 'X', 'products': ['0901']},
            {'dataset_id': 'wits-canada-cocoa', 'reporter': 'CAN', 'products': ['1806']},
        ]:
            result = get_json('/api/analyse', spec)
            assert result['analysis_id'] and result['evidence']
            results.append(result)
        checks += ['all_three_analysis_modes', 'canada_extension_analysis']
        main_result = results[0]
        spec = main_result['spec']
        assert main_result['analysis_id'] == '34f5d85bad4f7888dbd7'
        assert main_result['summary']['baseline'] == 179515290490
        assert main_result['summary']['current'] == 210288252660
        diagnostic = get_json('/api/diagnostics', {'spec': spec})
        assert len(diagnostic['windows']) == 4
        checks.append('main_case_numbers_and_four_windows_match')
        raw, headers = request('/api/document/report', {'spec': spec})
        assert b'<html' in raw.lower()
        bundle, headers = request('/api/diagnostics/bundle', {'spec': spec})
        reproduce_dir = extracted / 'verification-reproduction'
        reproduce_dir.mkdir()
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            assert archive.testzip() is None
            for name in archive.namelist():
                assert (reproduce_dir / name).resolve().is_relative_to(reproduce_dir.resolve())
            archive.extractall(reproduce_dir)
            for name, digest in json.loads(archive.read('checksums.json')).items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == digest
        code = "import sys,runpy;sys.path.insert(0," + repr(str(extracted / '.vendor')) + ");runpy.run_path('reproduce_diagnostic.py',run_name='__main__')"
        reproduced = subprocess.run([sys.executable, '-X', 'utf8', '-c', code],
            cwd=reproduce_dir, capture_output=True, text=True, encoding='utf-8', timeout=60,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        assert reproduced.returncode == 0, reproduced.stdout + reproduced.stderr
        checks += ['html_report_export', 'diagnostic_zip_hashes', 'independent_diagnostic_reproduction']
        assert get_json('/api/saved') == []
        report = {'created_at': datetime.now(timezone.utc).isoformat(),
            'archive': str(target.relative_to(ROOT)),
            'archive_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'files_checked': len(hashes), 'checks': checks, 'status': 'passed',
            'reproduction_output': reproduced.stdout.strip(),
            'dependencies': '测试时复制开发机已安装.vendor到解压目录；未声称在空白机器重新pip安装',
            'model_requests': 0, 'submitted_to_platform': False}
        out = args.report or target.with_suffix('.verification.json')
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log.close()


if __name__ == '__main__':
    main()
