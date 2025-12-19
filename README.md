# Macro Toggle Tool (Windows 11)

ホットキーで **マクロをトグル(開始/停止)** できる常駐型ツールです。  
マクロは `macros.json` に「キー入力」「待機」「マウス操作」などの手順を定義します。

- 開始/停止トリガを押すと開始、もう一度押すと停止
- 実行中に **終了トリガ以外のキーを押しても止まらない**
- 停止時は **押しっぱなし中のキー／マウスボタンを必ず離す（release処理）**


## ファイル構成

````

Macro_Windows/
  macro_toggle.py
  macros.json
  README.md

````

## セットアップ

### venv 作成とインストール

PowerShell:

```Powershell
cd C:\path\to\Macro_Windows
py -m venv .venv
.\.venv\Scripts\activate
py -m pip install -U pip
py -m pip install pynput pydirectinput
````

## 実行

```powershell
.\.venv\Scripts\activate
py .\macro_toggle.py
```

起動するとホットキー待機状態になります。

> ゲームが「管理者として実行」されている場合、スクリプトも同様に
> **管理者として PowerShell を起動**して実行してください。

## macros.json の書き方

### JSONの注意（重要）

* コメント不可（`//` や `#` はNG）
* 末尾カンマ不可
* 文字列は必ず `"` で囲む

検証：

```powershell
py -m json.tool .\macros.json
```

---

### 必須項目

* `trigger_hotkey`
* `macro`

推奨:
* `quit_hotkey`
* `loop`

---

### トリガ（開始/停止・終了）

例：`Ctrl+Shift+E` でトグル、`Ctrl+Shift+Q` で終了

```json
{
  "trigger_hotkey": "<ctrl>+<shift>+e",
  "quit_hotkey": "<ctrl>+<shift>+q",
  "loop": true,
  "macro": []
}
```

---

### loop

* `true`：停止するまで繰り返す
* `false`：1回実行して終了（省略時は false）

## macro ステップ仕様


`macro` は上から順に実行されます。

### wait（待機）

```json
{ "type": "wait", "seconds": 0.2 }
```

---

### text（文字列入力）

```json
{ "type": "text", "text": "hello" }
```

※ ゲームは文字入力を受けないことがあります。

---

### key（キー操作）

* `action`: `"tap"` / `"press"` / `"release"`
* `key`: `"a"` のような1文字、または `"Key.enter"` 等

例：a を 10 秒押しっぱなし

```json
{ "type": "key", "key": "a", "action": "press" },
{ "type": "wait", "seconds": 10 },
{ "type": "key", "key": "a", "action": "release" }
```

---

### combo（同時押し）

```json
{ "type": "combo", "keys": ["Key.ctrl_l", "c"] }
```

---

### mouse_click（クリック）

```json
{ "type": "mouse_click", "button": "left", "count": 2 }
```

* `button`: `"left"` / `"right"` / `"middle"`
* `count`: 1=クリック、2=ダブルクリック

---

### mouse_button（クリック押しっぱなし）

* `action`: `"tap"` / `"press"` / `"release"`
* `button`: `"left"` / `"right"` / `"middle"`

例：左クリックを 10 秒押しっぱなし

```json
{ "type": "mouse_button", "button": "left", "action": "press" },
{ "type": "wait", "seconds": 10 },
{ "type": "mouse_button", "button": "left", "action": "release" }
```

---

### mouse_move（マウス移動）

```json
{ "type": "mouse_move", "mode": "relative", "x": 50, "y": -10 }
```

`mode` は `"relative"` / `"absolute"`。

---

### mouse_scroll（スクロール）

```json
{ "type": "mouse_scroll", "dx": 0, "dy": -200 }
```

---

## サンプル

### ゲーム用：W を押しっぱなし（停止するまで）

```json
{
  "trigger_hotkey": "<ctrl>+<shift>+e",
  "quit_hotkey": "<ctrl>+<shift>+q",
  "loop": true,
  "macro": [
    { "type": "key", "key": "w", "action": "press" },
    { "type": "wait", "seconds": 99999 }
  ]
}
```

トリガ再押下で停止すると、W は必ず release されます。

---

## トラブルシューティング

### ゲームに入力が届かない

* ゲームが管理者実行なら、スクリプトも管理者で実行
* ゲームによっては注入入力を無視する場合があります

### JSONDecodeError（設定ファイルが読めない）

* JSONはコメント不可、末尾カンマ不可
* 検証：`py -m json.tool macros.json`
