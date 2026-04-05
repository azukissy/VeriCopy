import os
import hashlib
import time
from tqdm import tqdm

# ----- Config Begin -----
inputDir = r"input"
outputDir = r"output"
logDir = r"logs"
hashFunc = ""
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

def speedtest():
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

def verify(inputDir, outputDir, algorithm):
    inputFiles  = []
    outputFiles = []

    # 最初にファイルの一覧を取得しておく
    for file in os.listdir(inputDir):
        if os.path.isfile(os.path.join(inputDir, file)):
            inputFiles.append([os.path.join(inputDir, file)])
    for file in os.listdir(outputDir):
        if os.path.isfile(os.path.join(outputDir, file)):
            outputFiles.append([os.path.join(outputDir, file)])
    
    for file in inputFiles:
        print(file)
        with open(file, 'rb') as f:
            file_data_in  = f.read()
        with open(file, 'rb') as f:
            file_data_out = f.read()
        if calchash(file_data_in, algorithm) == calchash(file_data_out, algorithm):
            # 2つのファイルが同一の時
            print("OK")
        else:
            print("NG")



verify(inputDir, outputDir, "sha512")
# speedtest()