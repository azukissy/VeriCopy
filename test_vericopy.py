import pytest
import os
import hashlib
import tempfile
import shutil
from pathlib import Path
import sys

# vericopy.py をインポート
from vericopy import (
    calchash,
    _calc_file_hash,
    _compute_hashes_for_directory,
    verify,
)


class TestCalchash:
    """calchash() 関数のテスト"""
    
    def test_md5_hash(self):
        """MD5ハッシュが正しく計算されることを確認"""
        data = b"test data"
        result = calchash(data, "md5")
        expected = hashlib.md5(data).hexdigest()
        assert result == expected
    
    def test_sha256_hash(self):
        """SHA256ハッシュが正しく計算されることを確認"""
        data = b"test data"
        result = calchash(data, "sha256")
        expected = hashlib.sha256(data).hexdigest()
        assert result == expected
    
    def test_sha512_hash(self):
        """SHA512ハッシュが正しく計算されることを確認"""
        data = b"test data for sha512"
        result = calchash(data, "sha512")
        expected = hashlib.sha512(data).hexdigest()
        assert result == expected
    
    def test_sha3_256_hash(self):
        """SHA3-256ハッシュが正しく計算されることを確認"""
        data = b"sha3 test"
        result = calchash(data, "sha3_256")
        expected = hashlib.sha3_256(data).hexdigest()
        assert result == expected
    
    def test_unknown_algorithm_returns_none(self):
        """未知のアルゴリズムに対してNoneが返される"""
        data = b"test"
        result = calchash(data, "unknown_algo")
        assert result is None


class TestCalcFileHash:
    """_calc_file_hash() 関数のテスト"""
    
    @pytest.fixture
    def temp_file(self):
        """一時ファイルを作成するフィクスチャ"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test file content")
            temp_path = f.name
        yield temp_path
        os.remove(temp_path)
    
    def test_file_hash_calculation(self, temp_file):
        """ファイルのハッシュが正しく計算されることを確認"""
        result = _calc_file_hash((temp_file, "sha256", 16 * 1024 * 1024))
        
        assert result["file"] == os.path.basename(temp_file)
        assert result["error"] is None
        assert result["hash"] is not None
        
        # 検証：ハッシュ値が正しいか確認
        with open(temp_file, 'rb') as f:
            expected_hash = hashlib.sha256(f.read()).hexdigest()
        assert result["hash"] == expected_hash
    
    def test_file_not_found(self):
        """存在しないファイルを指定した場合のエラー処理"""
        result = _calc_file_hash(("/nonexistent/file.txt", "sha256", 16 * 1024 * 1024))
        
        assert result["hash"] is None
        assert result["error"] is not None
    
    def test_different_algorithms(self, temp_file):
        """異なるアルゴリズムでハッシュが異なることを確認"""
        result_md5 = _calc_file_hash((temp_file, "md5", 16 * 1024 * 1024))
        result_sha256 = _calc_file_hash((temp_file, "sha256", 16 * 1024 * 1024))
        
        assert result_md5["hash"] != result_sha256["hash"]
        assert result_md5["error"] is None
        assert result_sha256["error"] is None


class TestComputeHashesForDirectory:
    """_compute_hashes_for_directory() 関数のテスト"""
    
    @pytest.fixture
    def temp_dir_with_files(self):
        """複数のテストファイルを含む一時ディレクトリを作成"""
        temp_dir = tempfile.mkdtemp()
        try:
            # テストファイルを3つ作成
            file_contents = {
                "file1.txt": b"content 1",
                "file2.txt": b"content 2",
                "file3.txt": b"content 3",
            }
            
            for filename, content in file_contents.items():
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(content)
            
            yield temp_dir, file_contents
        finally:
            shutil.rmtree(temp_dir)
    
    def test_multiple_files_hashing(self, temp_dir_with_files):
        """複数ファイルのハッシュが正しく計算されることを確認"""
        temp_dir, file_contents = temp_dir_with_files
        file_list = list(file_contents.keys())
        
        hashes = _compute_hashes_for_directory(temp_dir, file_list, "sha256", num_processes=1)
        
        assert len(hashes) == 3
        for filename, content in file_contents.items():
            expected_hash = hashlib.sha256(content).hexdigest()
            assert hashes[filename] == expected_hash
    
    def test_empty_directory(self):
        """空のディレクトリを処理した場合"""
        temp_dir = tempfile.mkdtemp()
        try:
            hashes = _compute_hashes_for_directory(temp_dir, [], "sha256", num_processes=1)
            assert hashes == {}
        finally:
            shutil.rmtree(temp_dir)


class TestVerifyFunction:
    """verify() 関数のテスト"""
    
    @pytest.fixture
    def verify_test_dirs(self):
        """verify関数用のテストディレクトリを作成"""
        input_dir = tempfile.mkdtemp()
        output_dir = tempfile.mkdtemp()
        log_dir = tempfile.mkdtemp()
        
        try:
            # テストファイルを作成
            test_files = {
                "file1.txt": b"test content 1",
                "file2.txt": b"test content 2",
            }
            
            # inputディレクトリにファイルを配置
            for filename, content in test_files.items():
                with open(os.path.join(input_dir, filename), 'wb') as f:
                    f.write(content)
            
            # outputディレクトリに同じファイルを配置（file1のみ一致、file2は異なる）
            with open(os.path.join(output_dir, "file1.txt"), 'wb') as f:
                f.write(test_files["file1.txt"])
            with open(os.path.join(output_dir, "file2.txt"), 'wb') as f:
                f.write(b"different content for file2")  # 異なる内容
            
            yield input_dir, output_dir, log_dir
        finally:
            shutil.rmtree(input_dir)
            shutil.rmtree(output_dir)
            shutil.rmtree(log_dir)
    
    def test_verify_matching_files(self, verify_test_dirs, monkeypatch):
        """verify() 関数が正常に実行されることを確認"""
        input_dir, output_dir, log_dir = verify_test_dirs
        
        # ログディレクトリをモンキーパッチで指定
        monkeypatch.setattr('vericopy.logDir', log_dir)
        
        # verify関数を実行（エラーが発生しないことを確認）
        try:
            verify(input_dir, output_dir, "sha256")
            # ログファイルが作成されたことを確認
            log_files = os.listdir(log_dir)
            assert len(log_files) > 0
        except Exception as e:
            pytest.fail(f"verify() raised an exception: {e}")


class TestDirectoryCreation:
    """VeriCopyの初期化とディレクトリ作成のテスト"""
    
    def test_required_directories_exist(self):
        """必要なディレクトリが存在することを確認"""
        import vericopy
        
        assert os.path.isdir(vericopy.inputDir), f"{vericopy.inputDir} directory not found"
        assert os.path.isdir(vericopy.outputDir), f"{vericopy.outputDir} directory not found"
        assert os.path.isdir(vericopy.logDir), f"{vericopy.logDir} directory not found"


class TestEdgeCases:
    """エッジケースのテスト"""
    
    def test_large_file_hash(self):
        """大きなファイル（1MB以上）のハッシュ計算を確認"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # 1MBのファイルを作成
            f.write(b"x" * (1024 * 1024))
            temp_path = f.name
        
        try:
            result = _calc_file_hash((temp_path, "sha256", 16 * 1024))  # 16KBチャンク
            assert result["error"] is None
            assert result["hash"] is not None
        finally:
            os.remove(temp_path)
    
    def test_empty_file_hash(self):
        """空のファイルのハッシュ計算を確認"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
        
        try:
            result = _calc_file_hash((temp_path, "sha256", 16 * 1024 * 1024))
            assert result["error"] is None
            assert result["hash"] is not None
            
            # 空のファイルのSHA256ハッシュは既知の値
            expected_hash = hashlib.sha256(b"").hexdigest()
            assert result["hash"] == expected_hash
        finally:
            os.remove(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
