import os
import hashlib
import time
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

# ----- Config Begin -----
inputDir = r"input"
outputDir = r"output"
logDir = r"logs"
chunkSize = 16 * 1024 * 1024  # ユーザー設定可能: チャンク読み込みサイズ(デフォルト: 16MB)
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
    マルチプロセス化により、inputファイルとoutputファイルのハッシュ計算を並列実行
    
    Args:
        inputDir  (str): 入力ディレクトリのパス
        outputDir (str): 出力ディレクトリのパス
        algorithm (str): ハッシュアルゴリズムの名前（例: "sha256"） 規定は"sha512"
    """
    print(f"Verifying files in '{inputDir}' against '{outputDir}' using {algorithm}...")
    print(f"Chunk size: {chunkSize / (1024*1024):.1f} MB")
    
    current_dir_os = os.getcwd()
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

    # ワーカー関数用の引数リストを作成
    input_args = [(os.path.join(current_dir_os, inputDir, f), algorithm, chunkSize) for f in inputFiles]
    output_args = [(os.path.join(current_dir_os, outputDir, f), algorithm, chunkSize) for f in outputFiles]

    # プロセス数を自動決定（CPU コア数に基づく）
    num_processes = cpu_count()
    print(f"Using {num_processes} processes for hashing...")

    # マルチプロセス実行: inputファイルのハッシュ計算
    print("\n[1/2] Computing hashes for input files...")
    input_hashes = {}
    with Pool(processes=num_processes) as pool:
        results = list(tqdm(pool.imap_unordered(_calc_file_hash, input_args), total=len(inputFiles)))
    
    for result in results:
        if result["error"]:
            print(f"Error hashing input file '{result['file']}': {result['error']}")
        else:
            input_hashes[result["file"]] = result["hash"]

    # マルチプロセス実行: outputファイルのハッシュ計算
    print("\n[2/2] Computing hashes for output files...")
    output_hashes = {}
    with Pool(processes=num_processes) as pool:
        results = list(tqdm(pool.imap_unordered(_calc_file_hash, output_args), total=len(outputFiles)))
    
    for result in results:
        if result["error"]:
            print(f"Error hashing output file '{result['file']}': {result['error']}")
        else:
            output_hashes[result["file"]] = result["hash"]

    # 結果比較・出力
    print("\n[3/3] Comparing results...")
    for file in sorted(inputFiles):
        if file not in input_hashes:
            print(f"Skipped       : {file} (hash calculation failed)")
            continue
        
        if file not in output_hashes:
            print(f"File not found: {file}")
            continue
        
        if input_hashes[file] == output_hashes[file]:
            print(f"Match         : {file}")
        else:
            print(f"Do not match  : {file}")
    
    # outputにのみ存在するファイルの報告
    for file in sorted(outputFiles):
        if file not in inputFiles:
            print(f"Extra in output: {file}")

    print("\nVerification complete.")


def main():
    """メイン処理"""
    verify(inputDir, outputDir, "sha512")
    # speedtest()


if __name__ == '__main__':
    main()