# 🔊 Audio Visualizer（Voicemeeter必須版）

本プロジェクトは、リアルタイムでPC上の音声を解析・視覚化する
**Windows専用オーディオビジュアライザー**です。

⚠ **本アプリは Voicemeeter の常時起動を前提とします。**

---

# 🚨 必須ソフト

## 🎛 Voicemeeter を必ずインストールしてください

公式サイト：
[https://vb-audio.com/Voicemeeter/](https://vb-audio.com/Voicemeeter/)

### 推奨版

* **Voicemeeter（通常版）でOK**
* Banana / Potato でも可

---

# 📦 初回セットアップ（必須）

## ① Voicemeeterをインストール

1. 公式サイトからダウンロード
2. ZIPを解凍
3. `VoicemeeterSetup.exe` を **右クリック → 管理者として実行**
4. 再起動

---

## ② Voicemeeterの基本設定

### 🎧 A1（実際に音を出すデバイス）

Voicemeeter右上の

```
A1
```

をクリックして、
自分が実際に音を聞いているデバイスを選択：

* 有線イヤホン
* Bluetoothヘッドホン
* スピーカー
* USB DAC など

👉 ここは自由です（既定デバイス変更不要）

---

### 🎵 Windowsの出力先を変更

Windowsの「サウンド設定」→ 出力デバイスを

```
Voicemeeter Input (VB-Audio Voicemeeter VAIO)
```

に変更

これで

Spotify / YouTube / ゲーム / すべての音

が Voicemeeter を通るようになります。

---

## ③ Visualizer 側の入力設定

アプリ起動後、

入力デバイスを：

```
Voicemeeter Output (VB-Audio Voicemeeter VAIO)
```

に設定してください。

これで音を安全に取得できます。

---

# ⚠ 重要

Voicemeeterは **常に起動しておく必要があります。**

* × 終了してはいけません
* ○ 最小化（－ボタン）はOK
* ○ タスクトレイ常駐OK

Voicemeeterが終了すると、音の取得ができません。

---

# 🚀 EXE版の使い方

1. `Visualizer.exe` をダブルクリック
2. 入力デバイスに「Voicemeeter Output」を選択
3. 音楽を再生
4. リアルタイムでビジュアライザーが動作

Python不要で動作します。

---

# 🛠 Python版（開発者向け）

## 仮想環境作成

```powershell
python -m venv muvenv
.\muvenv\Scripts\activate
```

## 依存インストール

```powershell
uv sync --active
```

## 実行

```powershell
python auto_mv.py
```

---

# 🏗 EXEビルド方法（PowerShell）

```powershell
pyinstaller --onefile --windowed --name AudioVisualizer ^
--collect-all numpy ^
--collect-all sounddevice ^
--collect-all matplotlib ^
auto_mv.py
```

生成場所：

```
dist\AudioVisualizer.exe
```

---

# 🎯 この方式のメリット

| 項目         | メリット  |
| ---------- | ----- |
| 有線         | 問題なし  |
| Bluetooth  | 問題なし  |
| 既定デバイス変更   | 不要    |
| ステレオミキサー   | 不要    |
| VB-CABLE単体 | 不要    |
| 安定性        | 非常に高い |
| 音質劣化       | なし    |

---

# 🛠 トラブルシューティング

### 音が反応しない

✔ Voicemeeterが起動しているか確認
✔ Windows出力がVoicemeeter Inputになっているか確認
✔ Visualizer入力がVoicemeeter Outputになっているか確認

---

### 音が聞こえない

✔ VoicemeeterのA1が正しいデバイスか確認
✔ A1がWDMで選択されているか確認

---

# 🎉 Enjoy!

PC上のすべての音を
安全かつ安定してリアルタイム可視化できます。

---
