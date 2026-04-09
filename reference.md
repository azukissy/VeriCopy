ディスク I/O とCPU の能力を考慮して、最適な並列度を計算します。

## 前提条件の整理

**ディスク構成：**
- HDD 3台 RAID5 シーケンシャル読み出し速度：約 350-400 MB/s（実効値）

**CPU SHA-512 ハッシュ速度：**
- 1コアあたり約 1,000-1,200 MB/s
- 16コア：約 16 GB/s
- 32コア：約 32 GB/s

**USB転送速度と実効帯域幅：**

| USB世代 | 理論速度 | 理論帯域 | 実効帯域 | ボトルネック |
|---------|---------|--------|--------|-----------|
| USB 2.0 | 480 Mbps | 60 MB/s | **40-50 MB/s** | USB |
| USB 3.0 | 5 Gbps | 625 MB/s | **400-500 MB/s** | ディスク |
| USB 3.1 (10Gbps) | 10 Gbps | 1,250 MB/s | **900-1,000 MB/s** | CPU |
| USB 3.2 (20Gbps) | 20 Gbps | 2,500 MB/s | **1,800-2,000 MB/s** | CPU |

## 各パターンの最適並列度計算

**1ファイルあたりの処理時間：**
- ディスク読み出し時間：30 MB ÷ 帯域幅
- ハッシュ計算時間：30 MB ÷ 1,200 MB/s ≈ **25ms**

### パターン1: USB 2.0（40-50 MB/s）

```
ディスク読み出し時間：30 MB ÷ 45 MB/s ≈ 667ms
ハッシュ計算時間：25ms
比率：667ms / 25ms ≈ 27倍

最適並列度：
  16コア環境 → 2-3 並列
  32コア環境 → 3-4 並列
  
理由：ディスクがボトルネック。CPUを過度に並列化しても
      ディスク読み出し待機時間が大半になり無駄
```

**結論：USB 2.0 は極めて非効率（非推奨）**

---

### パターン2: USB 3.0（400-500 MB/s）

```
ディスク読み出し時間：30 MB ÷ 450 MB/s ≈ 67ms
ハッシュ計算時間：25ms
比率：67ms / 25ms ≈ 2.7倍

並列度 N の場合の総処理時間：
  T(N) = (N × 67ms) / N + 25ms（理論値）
  実効：T(N) ≈ 67ms + 25ms = 92ms per ファイル

最適並列度：
  16コア環境 → 5-6 並列
  32コア環境 → 8-10 並列
  
根拠：ディスクが軽度制約。4-6並列で
      CPU 4-6コアがディスク I/O 待機で有効利用
```

**推奨：USB 3.0 の場合、`num_processes = 6` 程度が無難**

---

### パターン3: USB 3.1 (10Gbps)（900-1,000 MB/s）

```
ディスク読み出し時間：30 MB ÷ 950 MB/s ≈ 32ms
ハッシュ計算時間：25ms
比率：32ms / 25ms ≈ 1.3倍

ほぼバランス状態

最適並列度：
  16コア環境 → 10-12 並列 ★ 推奨
  32コア環境 → 20-24 並列 ★ 推奨
  
根拠：ディスク帯域幅とCPU性能がほぼ対等
      並列度を上げるほど全体効率が向上
```

**ベストケース：CPU リソースをほぼ100%活用可能**

---

### パターン4: USB 3.2 (20Gbps)（1,800-2,000 MB/s）

```
ディスク読み出し時間：30 MB ÷ 1,900 MB/s ≈ 16ms
ハッシュ計算時間：25ms
比率：16ms / 25ms ≈ 0.64倍

CPU がボトルネック

最適並列度：
  16コア環境 → 14-16 並列（全コア活用）⭐
  32コア環境 → 28-32 並列（全コア+HT活用）⭐

理由：ディスク帯域幅に余裕。できるだけ並列度を上げて
      CPU を最大稼働させる
```

**最高効率：CPU を最大活用し、処理時間を最小化**

---

## 実装の推奨設定

```python
# 構成に応じた最適並列度の自動決定
import subprocess

def get_usb_info():
    """USB接続情報を取得（Windowsの場合）"""
    # 実装简化版：ユーザーが手動で指定
    pass

def determine_optimal_processes(cpu_cores, usb_generation):
    """最適なプロセス数を決定"""
    base_ratio = {
        2: 2,      # USB 2.0
        3: cpu_cores // 2 + 2,  # USB 3.0
        3.1: cpu_cores - 4,     # USB 3.1
        3.2: cpu_cores,         # USB 3.2（フルコア）
    }
    return min(base_ratio.get(usb_generation, 4), cpu_cores)

# 使用例
cpu_cores = cpu_count()
usb_gen = 3.1  # ユーザーが指定
num_processes = determine_optimal_processes(cpu_cores, usb_gen)
```

---

## まとめ表

| 環境 | USB 2.0 | USB 3.0 | USB 3.1 | USB 3.2 |
|------|---------|---------|---------|---------|
| **16コア** | 2-3 | 5-6 | **10-12** | **14-16** |
| **32コア** | 3-4 | 8-10 | **20-24** | **28-32** |
| **ボトルネック** | USB | ディスク | バランス | **CPU** |
| **効率** | 低 ⚠️ | 中 | 高 | **最高** ⭐ |

**結論：USB 3.0 以上であれば、現在の `cpu_count()` 使用でおおむね最適。USB 3.1 以上なら、さらに 1.5-2 倍の並列度向上が可能です。**





`verify` 関数の比較処理のマルチプロセス化について、実装前に効果を分析します。

## 1. マルチプロセス化の効果について

**結論：比較処理のマルチプロセス化は効果がほぼありません。むしろ避けるべきです。**

理由：

| 処理の特性 | ハッシュ計算 | 比較処理 |
|----------|----------|--------|
| 計算の種類 | CPU集約的 | I/Oバウンド＋軽量計算 |
| 処理時間 | 長い（30MBのファイル）| 極めて短い（辞書検索＋比較） |
| ボトルネック | CPU性能 | 出力（print）処理 |
| マルチプロセス効果 | ◎ 高い | ✗ なし |
| オーバーヘッド | 相対的に小さい | **相対的に大きい** |

**具体的な計算時間の目安：**
- ハッシュ計算：30MB × 数千ファイル ≈ 数十分（CPU依存）
- 比較処理：数千回のハッシュ値比較 ≈ **マイクロ秒単位**

マルチプロセス化のオーバーヘッド（プロセス生成、IPC、メモリ管理）が比較処理の実行時間を上回るため、総処理時間は **むしろ遅くなります**。

## 実装が有効な場合の代替案

もし比較処理を本当に高速化したいなら：

```python
# 案1: マルチスレッド使用（print出力があるため）
from concurrent.futures import ThreadPoolExecutor

def _compare_file(file_info):
    """ファイル比較用のワーカー関数"""
    file, input_hashes, output_hashes = file_info
    
    if file not in input_hashes:
        return f"Skipped       : {file} (hash calculation failed)"
    if file not in output_hashes:
        return f"File not found: {file}"
    if input_hashes[file] == output_hashes[file]:
        return f"Match         : {file}"
    else:
        return f"Do not match  : {file}"

# 比較処理部分の置き換え
print("\n[3/3] Comparing results...")
compare_args = [(file, input_hashes, output_hashes) for file in sorted(inputFiles)]

with ThreadPoolExecutor(max_workers=4) as executor:
    for result in executor.map(lambda args: _compare_file(args), compare_args):
        print(result)

# 出力に存在するファイルの報告
for file in sorted(outputFiles):
    if file not in inputFiles:
        print(f"Extra in output: {file}")
```

**ただし、このアプローチも現実的には：**
- print出力の競合により、シングルプロセスとほぼ同等か遅い
- メモリオーバーヘッドが増加
- 処理時間全体への改善は1%未満

## 実装のお勧め

**現在のシングルプロセス実装を維持し、以下を検討してください：**

1. **計算時間が気になるなら、ハッシュ計算の並列度を上げる**
   ```python
   num_processes = cpu_count() * 2  # または調整
   ```

2. **出力を後から集約する方式にする**
   ```python
   # 比較結果をメモリに集約してから一括出力
   results = []
   for file in sorted(inputFiles):
       # ... 比較ロジック ...
       results.append(message)
   
   for msg in results:
       print(msg)
   ```

3. **ログをファイルに書き込む**
   - 出力がボトルネックなら、ファイル I/O は print より高速

**結論：現在の実装で十分最適化されています。比較処理の改善より、ハッシュ計算の最適化（チャンクサイズやプロセス数調整）がコスト対効果的です。**