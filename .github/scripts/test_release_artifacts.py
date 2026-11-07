"""Adversarial fixtures for the exact release artifact validator."""
from io import BytesIO
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

from verify_release_artifacts import verify


class ReleaseArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dist = self.root / 'dist'
        self.dist.mkdir()
        self.project = 'rqm-example'
        self.version = '1.2.3'
        self.pyproject = '[project]\nname = "rqm-example"\nversion = "1.2.3"\n'
        (self.root / 'pyproject.toml').write_text(self.pyproject)
        (self.root / '.release-please-manifest.json').write_text(json.dumps({'.': self.version}))
        self.wheel = self.dist / 'rqm_example-1.2.3-py3-none-any.whl'
        self.sdist = self.dist / 'rqm_example-1.2.3.tar.gz'
        self.write_wheel()
        self.write_sdist()

    def metadata(self, name='rqm-example', version='1.2.3'):
        return f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n'.encode()

    def write_wheel(self, name='rqm-example', version='1.2.3', duplicate=False, path=None, extra=b''):
        with zipfile.ZipFile(self.wheel, 'w') as archive:
            archive.writestr(path or 'rqm_example-1.2.3.dist-info/METADATA', self.metadata(name, version) + extra)
            if duplicate:
                archive.writestr('other-1.2.3.dist-info/METADATA', self.metadata())

    def write_sdist(self, name='rqm-example', version='1.2.3', pyproject=None, missing=None, link=False):
        with tarfile.open(self.sdist, 'w:gz') as archive:
            for suffix, data in [('PKG-INFO', self.metadata(name, version)),
                                 ('pyproject.toml', (pyproject or self.pyproject).encode())]:
                if suffix == missing:
                    continue
                info = tarfile.TarInfo(f'rqm_example-1.2.3/{suffix}')
                info.size = len(data)
                if link:
                    info.type = tarfile.SYMTYPE
                    info.linkname = '../outside'
                archive.addfile(info, BytesIO(data))

    def check(self):
        verify(self.root, self.project, 'v1.2.3', self.dist)

    def test_valid_source_and_distributions(self):
        self.check()
        verify(self.root, self.project, 'v1.2.3')

    def test_normalized_metadata_name(self):
        self.write_wheel(name='RQM_Example')
        self.check()

    def test_source_mismatch(self):
        for replacement in [self.pyproject.replace('rqm-example', 'wrong'),
                            self.pyproject.replace('1.2.3', '1.2.4')]:
            with self.subTest(replacement=replacement):
                (self.root / 'pyproject.toml').write_text(replacement)
                with self.assertRaises(ValueError):
                    self.check()

    def test_manifest_mismatch(self):
        (self.root / '.release-please-manifest.json').write_text('{".": "1.2.4"}')
        with self.assertRaises(ValueError):
            self.check()

    def test_bad_tags(self):
        for tag in ['1.2.3', 'v1.2.3rc1', 'v01.2.3', 'v1.2.3\n', 'v1.2.3; echo unsafe']:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                verify(self.root, self.project, tag, self.dist)

    def test_wheel_metadata_mismatch(self):
        for kwargs in [{'name': 'wrong'}, {'version': '1.2.4'}, {'duplicate': True},
                       {'path': 'other-1.2.3.dist-info/METADATA'}, {'extra': b'Name: other\n'},
                       {'extra': b'Version: 1.2.4\n'}]:
            with self.subTest(kwargs=kwargs):
                self.write_wheel(**kwargs)
                with self.assertRaises(ValueError):
                    self.check()

    def test_sdist_metadata_mismatch(self):
        for kwargs in [{'name': 'wrong'}, {'version': '1.2.4'}, {'missing': 'PKG-INFO'},
                       {'missing': 'pyproject.toml'}, {'link': True},
                       {'pyproject': self.pyproject.replace('1.2.3', '1.2.4')}]:
            with self.subTest(kwargs=kwargs):
                self.write_sdist(**kwargs)
                with self.assertRaises(ValueError):
                    self.check()

    def test_wheel_filename_mismatch(self):
        self.wheel.rename(self.dist / 'rqm_example-1.2.4-py3-none-any.whl')
        with self.assertRaises(ValueError):
            self.check()

    def test_sdist_filename_mismatch(self):
        self.sdist.rename(self.dist / 'rqm_example-1.2.4.tar.gz')
        with self.assertRaises(ValueError):
            self.check()

    def test_unexpected_file(self):
        (self.dist / 'extra.whl').write_bytes(b'not a release')
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_sdist(self):
        self.sdist.unlink()
        with self.assertRaises(ValueError):
            self.check()

    def test_second_wheel_instead_of_sdist(self):
        self.sdist.rename(self.dist / 'extra.whl')
        with self.assertRaises(ValueError):
            self.check()

    def test_symlink(self):
        self.wheel.rename(self.root / self.wheel.name)
        self.wheel.symlink_to(self.root / self.wheel.name)
        with self.assertRaises(ValueError):
            self.check()


if __name__ == '__main__':
    unittest.main()
