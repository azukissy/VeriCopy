import os
import hashlib
import time
from multiprocessing import Pool, cpu_count, Queue, Manager, Process
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from tqdm import tqdm
from datetime import datetime

# ----- Config Begin -----
inputDir = r"input"
outputDir = r"output"
logDir = r"logs"
chunkSize = 16 * 1024 * 1024  # ユーザー設定可能: チャンク読み込みサイズ(デフォルト: 16MB)
enableParallelDrives = True  # inputとoutputが異なるドライブにある場合、並行ハッシュ計算を有効にする
enableMultiThreadHashing = True  # I/Oスレッド + マルチプロセスハッシュ計算を有効にする
# 使えるアルゴリズム確認用
# print(hashlib.algorithms_available)
# ----- Config End -----

# ディレクトリの有無確認し、なければ作成する
if not os.path.isdir(inputDir):  os.makedirs(inputDir)
if not os.path.isdir(outputDir): os.makedirs(outputDir)
if not os.path.isdir(logDir):    os.makedirs(logDir)


def calchash(data, algorithm):
    if algorithm == "md5": return hashlib.md5(data).hexdigest()
    if algorithm == "sha1": return hashlib.sha1(data).hexdigest()
    if algorithm == "sha224": return hashlib.sha224(data).hexdigest()
    if algorithm == "sha256": return hashlib.sha256(data).hexdigest()
    if algorithm == "sha384": return hashlib.sha384(data).hexdigest()
    if algorithm == "sha512": return hashlib.sha512(data).hexdigest()
    if algorithm == "sha3_224": return hashlib.sha3_224(data).hexdigest()
    if algorithm == "sha3_256": return hashlib.sha3_256(data).hexdigest()
    if algorithm == "sha3_384": return hashlib.sha3_384(data).hexdigest()
    if algorithm == "sha3_512": return hashlib.sha3_512(data).hexdigest()


def _calc_file_hash(args):
    """ワーカー関数: ファイルのハッシュ値をチャンク単位で計算する
    
    Args:
        args (tuple): (file_path, algorithm, chunk_size)を含むタプル
    
    Returns:
        dict: {"file": filename, "hash": hash_value, "error": error_message or None}
    """
    file_path, algorithm, chunk_size = args
    filename = os.path.basename(file_path)
    
    try:
        # アルゴリズムの選択
        if algorithm == "md5": hasher = hashlib.md5()
        elif algorithm == "sha1": hasher = hashlib.sha1()
        elif algorithm == "sha224": hasher = hashlib.sha224()
        elif algorithm == "sha256": hasher = hashlib.sha256()
        elif algorithm == "sha384": hasher = hashlib.sha384()
        elif algorithm == "sha512": hasher = hashlib.sha512()
        elif algorithm == "sha3_224": hasher = hashlib.sha3_224()
        elif algorithm == "sha3_256": hasher = hashlib.sha3_256()
        elif algorithm == "sha3_384": hasher = hashlib.sha3_384()
        elif algorithm == "sha3_512": hasher = hashlib.sha3_512()
        else:
            return {"file": filename, "hash": None, "error": f"Unknown algorithm: {algorithm}"}
        
        # ファイルをチャンク単位で読み込んでハッシュ計算
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        
        return {"file": filename, "hash": hasher.hexdigest(), "error": None}
    
    except Exception as e:
        return {"file": filename, "hash": None, "error": str(e)}


def _file_reader_thread(directory, file_list, chunk_queue, pbar):
    """ファイルを順次読み込んで、チャンクキューに入れる（シングルスレッド I/O）
    
    Args:
        directory (str): ディレクトリパス
        file_list (list): ファイル一覧
        chunk_queue: マルチプロセス队列
        pbar: tqdm進捗バー
    """
    for file in file_list:
        file_path = os.path.join(directory, file)
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunkSize)
                    if not chunk:
                        chunk_queue.put((os.path.basename(file), -1, None))  # EOF marker
                        break
                    chunk_queue.put((os.path.basename(file), 0, chunk))  # (filename, flags, data)
        except Exception as e:
            chunk_queue.put((os.path.basename(file), -2, str(e)))  # Error marker


def _hash_calculator_worker(chunk_queue, result_dict, algorithm, num_files):
    """キューからチャンクを取得してハッシュを計算（マルチプロセス）
    
    Args:
        chunk_queue: マルチプロセス队列
        result_dict: 結果を格納する共有辞書
        algorithm (str): ハッシュアルゴリズム
        num_files (int): ファイル総数
    """
    hashers = {}
    completed_files = set()
    
    while len(completed_files) < num_files:
        try:
            filename, flags, data = chunk_queue.get(timeout=5)
        except:
            break
        
        # エラーチェック
        if flags == -2:  # Error
            result_dict[filename] = {"hash": None, "error": data}
            completed_files.add(filename)
            continue
        
        # Hasher初期化
        if filename not in hashers:
            if algorithm == "md5": hashers[filename] = hashlib.md5()
            elif algorithm == "sha1": hashers[filename] = hashlib.sha1()
            elif algorithm == "sha224": hashers[filename] = hashlib.sha224()
            elif algorithm == "sha256": hashers[filename] = hashlib.sha256()
            elif algorithm == "sha384": hashers[filename] = hashlib.sha384()
            elif algorithm == "sha512": hashers[filename] = hashlib.sha512()
            elif algorithm == "sha3_224": hashers[filename] = hashlib.sha3_224()
            elif algorithm == "sha3_256": hashers[filename] = hashlib.sha3_256()
            elif algorithm == "sha3_384": hashers[filename] = hashlib.sha3_384()
            elif algorithm == "sha3_512": hashers[filename] = hashlib.sha3_512()
        
        # EOF処理
        if flags == -1:  # EOF marker
            result_dict[filename] = {"hash": hashers[filename].hexdigest(), "error": None}
            completed_files.add(filename)
            del hashers[filename]
        else:  # データ処理
            hashers[filename].update(data)


def _compute_hashes_for_directory_threaded(directory, file_list, algorithm, num_processes):
    """I/Oスレッド + マルチプロセスハッシュ計算でファイルハッシュを計算
    
    Args:
        directory (str): ディレクトリパス
        file_list (list): ファイル一覧
        algorithm (str): ハッシュアルゴリズム
        num_processes (int): プロセス数
    
    Returns:
        dict: ファイル名をキー、ハッシュ値を値とする辞書
    """
    with Manager() as manager:
        chunk_queue = manager.Queue(maxsize=num_processes * 2)
        result_dict = manager.dict()
        
        # I/O用スレッドを起動
        reader_thread = Thread(
            target=_file_reader_thread,
            args=(directory, file_list, chunk_queue, None),
            daemon=False
        )
        reader_thread.start()
        
        # ハッシュ計算用プロセスを起動
        processes = []
        for _ in range(num_processes):
            p = Process(
                target=_hash_calculator_worker,
                args=(chunk_queue, result_dict, algorithm, len(file_list))
            )
            p.start()
            processes.append(p)
        
        # スレッド・プロセスの終了を待つ
        reader_thread.join()
        for p in processes:
            p.join()
        
        # 結果を取得
        hashes = {}
        for filename, result in result_dict.items():
            if result["error"]:
                print(f"Error hashing file '{filename}': {result['error']}")
            else:
                hashes[filename] = result["hash"]
        
        return hashes


def _compute_hashes_for_directory(directory, file_list, algorithm, num_processes):
    """ディレクトリ内のファイルハッシュを計算し、結果の辞書を返す
    enableMultiThreadHashingがTrueの場合、I/Oスレッド+マルチプロセス方式を使用
    
    Args:
        directory (str): ディレクトリパス
        file_list (list): ファイル一覧
        algorithm (str): ハッシュアルゴリズム
        num_processes (int): プロセス数
    
    Returns:
        dict: ファイル名をキー、ハッシュ値を値とする辞書
    """
    if enableMultiThreadHashing:
        return _compute_hashes_for_directory_threaded(directory, file_list, algorithm, num_processes)
    else:
        # 既存のマルチプロセス方式
        current_dir_os = os.getcwd()
        args = [(os.path.join(current_dir_os, directory, f), algorithm, chunkSize) for f in file_list]
        
        hashes = {}
        with Pool(processes=num_processes) as pool:
            results = list(tqdm(pool.imap_unordered(_calc_file_hash, args), total=len(file_list)))
        
        for result in results:
            if result["error"]:
                print(f"Error hashing file '{result['file']}': {result['error']}")
            else:
                hashes[result["file"]] = result["hash"]
        
        return hashes


def speedtest():
    """Hashアルゴリズムの速度テストを行う
    目的は、ユーザーがHashアルゴリズムの信頼性と速度から選択できる為の指標を示すこと"""
    # 各環境下でのHash計算速度を事前テスト
    # ユーザーがHashアルゴリズムの信頼性と速度から選択できる為の指標を示す
    result = [["Algorithm" ,"FileName", "CalcTime(ms)", "Result"]]
    for file in os.listdir(inputDir):
        if os.path.isfile(os.path.join(inputDir, file)):
            with open(os.path.join(inputDir, file), 'rb') as f:
                file_data = f.read()
            for algorithm in hashlib.algorithms_available:
                startTime = time.perf_counter()
                hash_value = calchash(file_data, algorithm)
                endTime = time.perf_counter()
                elapsedTime = round((endTime - startTime) * 1000, 3)
                if hash_value:
                    result.append([algorithm, f.name, elapsedTime, hash_value])
                    # print(f.name)
                    # print(hash_value)
    
    result2 = sorted(result)
    for row in result2:
        # print(row[0], row[1], row[2], row[3])
        print(f"{row[0]:>9} :: {row[2]:>12} :: {row[1]} :: {row[3]}")

    return 0

def verify(inputDir, outputDir, algorithm = "sha512"):
    """inputDirとoutputDirのファイルを比較して、同一のファイルかどうかを確認する
    enableParallelDrivesがTrueの場合、inputファイルとoutputファイルのハッシュ計算を並列実行する
    
    Args:
        inputDir  (str): 入力ディレクトリのパス
        outputDir (str): 出力ディレクトリのパス
        algorithm (str): ハッシュアルゴリズムの名前（例: "sha256"） 規定は"sha512"
    """
    print(f"Verifying files in '{inputDir}' against '{outputDir}' using {algorithm}...")
    print(f"Chunk size: {chunkSize / (1024*1024):.1f} MB")
    
    inputFiles  = []
    outputFiles = []

    # 最初にファイルの一覧を取得しておく
    for file in os.listdir(inputDir):
        if os.path.isfile(os.path.join(inputDir, file)):
            inputFiles.append(file)
    for file in os.listdir(outputDir):
        if os.path.isfile(os.path.join(outputDir, file)):
            outputFiles.append(file)

    if not inputFiles:
        print("Warning: No files found in input directory.")
        return
    if not outputFiles:
        print("Warning: No files found in output directory.")
        return

    # プロセス数を自動決定（CPU コア数に基づく）
    num_processes = int(cpu_count() / 2)
    print(f"Using {num_processes} processes for hashing...")

    # enableParallelDrivesに基づいて、並行実行または順次実行を選択
    if enableParallelDrives:
        print("\n[1/2] Computing hashes for input and output files in parallel...")
        input_hashes = {}
        output_hashes = {}
        
        # ThreadPoolExecutorを使って、input と output の計算を並列実行
        with ThreadPoolExecutor(max_workers=2) as executor:
            input_future = executor.submit(_compute_hashes_for_directory, inputDir, inputFiles, algorithm, num_processes)
            output_future = executor.submit(_compute_hashes_for_directory, outputDir, outputFiles, algorithm, num_processes)
            
            input_hashes = input_future.result()
            output_hashes = output_future.result()
    else:
        # 順次実行：input -> output
        print("\n[1/2] Computing hashes for input files...")
        input_hashes = _compute_hashes_for_directory(inputDir, inputFiles, algorithm, num_processes)
        
        print("\n[2/3] Computing hashes for output files...")
        output_hashes = _compute_hashes_for_directory(outputDir, outputFiles, algorithm, num_processes)

    # 結果比較・出力
    comparison_step = "[2/2]" if enableParallelDrives else "[3/3]"
    print(f"\n{comparison_step} Comparing results...")
    
    # 統計情報とNot Matchファイル情報を記録
    matched_count = 0
    not_matched_files = []  # Not Matchのファイル情報を格納
    
    for file in sorted(inputFiles):
        if file not in input_hashes:
            print(f"Skipped       : {file} (hash calculation failed)")
            continue
        
        if file not in output_hashes:
            print(f"File not found: {file}")
            continue
        
        if input_hashes[file] == output_hashes[file]:
            print(f"Match         : {file}")
            matched_count += 1
        else:
            print(f"Do not match  : {file}")
            # Not Matchファイルの詳細情報を取得
            input_path = os.path.join(inputDir, file)
            output_path = os.path.join(outputDir, file)
            
            input_stat = os.stat(input_path)
            output_stat = os.stat(output_path)
            
            input_mtime = datetime.fromtimestamp(input_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            output_mtime = datetime.fromtimestamp(output_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            not_matched_files.append({
                'file': file,
                'input_hash': input_hashes[file],
                'output_hash': output_hashes[file],
                'input_mtime': input_mtime,
                'output_mtime': output_mtime,
                'input_size': input_stat.st_size,
                'output_size': output_stat.st_size
            })
    
    # outputにのみ存在するファイルの報告
    for file in sorted(outputFiles):
        if file not in inputFiles:
            print(f"Extra in output: {file}")

    # ハッシュ値から逆引き辞書を作成し、異なるファイル名で同じハッシュを持つファイルを検出
    duplicate_step = "[3/3]" if enableParallelDrives else "[4/4]"
    print(f"\n{duplicate_step} Checking for duplicate files with different names...")
    hash_to_input_files = {}
    hash_to_output_files = {}
    
    for filename, hash_value in input_hashes.items():
        if hash_value not in hash_to_input_files:
            hash_to_input_files[hash_value] = []
        hash_to_input_files[hash_value].append(filename)
    
    for filename, hash_value in output_hashes.items():
        if hash_value not in hash_to_output_files:
            hash_to_output_files[hash_value] = []
        hash_to_output_files[hash_value].append(filename)
    
    # 異なるファイル名で同じハッシュを持つ場合を報告
    duplicates_found = False
    
    # inputディレクトリ内で同じハッシュを持つ異なるファイルを検出
    for hash_value, files in hash_to_input_files.items():
        if len(files) > 1:
            duplicates_found = True
            print(f"[Input] Duplicate files with same hash {hash_value[:16]}...:")
            for file in sorted(files):
                print(f"  - {file}")
    
    # outputディレクトリ内で同じハッシュを持つ異なるファイルを検出
    for hash_value, files in hash_to_output_files.items():
        if len(files) > 1:
            duplicates_found = True
            print(f"[Output] Duplicate files with same hash {hash_value[:16]}...:")
            for file in sorted(files):
                print(f"  - {file}")
    
    # inputとoutputの間で異なるファイル名で同じハッシュを持つ場合を検出
    for hash_value in hash_to_input_files.keys():
        if hash_value in hash_to_output_files:
            input_files = hash_to_input_files[hash_value]
            output_files = hash_to_output_files[hash_value]
            
            # ファイル名が異なる場合のみ報告
            if set(input_files) != set(output_files):
                duplicates_found = True
                print(f"[Cross-directory] Files with same hash {hash_value[:16]}... (different names):")
                print(f"  Input:  {', '.join(sorted(input_files))}")
                print(f"  Output: {', '.join(sorted(output_files))}")
    
    if not duplicates_found:
        print("No duplicate files found with different names.")

    # ========== 結果サマリー ==========
    not_matched_count = len(not_matched_files)
    print(f"\n{'='*100}")
    print(f"SUMMARY:")
    print(f"  - Matched files:     {matched_count}")
    print(f"  - Not matched files: {not_matched_count}")
    print(f"{'='*100}")
    
    # Not Matchファイルの詳細を表形式で出力
    if not_matched_files:
        print("\n[NOT MATCHED FILES DETAILS]")
        print(f"\n{'File Name':<30} | {'Size (Input / Output)':<22} | {'Modified Time (Input)':<19} | {'Modified Time (Output)':<19}")
        print(f"{'-'*30}-+-{'-'*22}-+-{'-'*19}-+-{'-'*19}")
        
        for file_info in not_matched_files:
            file_name = file_info['file']
            sizes = f"{file_info['input_size']} / {file_info['output_size']}"
            input_mtime = file_info['input_mtime']
            output_mtime = file_info['output_mtime']
            
            print(f"{file_name:<30} | {sizes:<22} | {input_mtime:<19} | {output_mtime:<19}")
        
        print("\n[HASH VALUES]")
        print(f"{'File Name':<30} | {'Input Hash':<65}")
        print(f"{'-'*30}-+-{'-'*65}")
        
        for file_info in not_matched_files:
            file_name = file_info['file']
            input_hash = file_info['input_hash']
            print(f"{file_name:<30} | {input_hash:<65}")
        
        print(f"\n{'File Name':<30} | {'Output Hash':<65}")
        print(f"{'-'*30}-+-{'-'*65}")
        
        for file_info in not_matched_files:
            file_name = file_info['file']
            output_hash = file_info['output_hash']
            print(f"{file_name:<30} | {output_hash:<65}")

    print("\nVerification complete.")


def main():
    """メイン処理"""
    verify(inputDir, outputDir, "sha512")
    # speedtest()


if __name__ == '__main__':
    main()