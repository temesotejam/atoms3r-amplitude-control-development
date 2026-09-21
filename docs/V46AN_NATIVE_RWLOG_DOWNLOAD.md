# V46an / 0.46.39 — Native RWLOG download

## 目的

V46alの制御とV46amのサーバ側RWLOG送信対策を維持したまま、
ブラウザ側のダウンロード開始方式だけを変更します。

V46amでは `fetch('/download/rwlog')` で全データを受信し、
`blob()` 化してから保存を開始していました。
そのためブラウザのダウンロード表示は全受信後まで現れず、
実機では「ダウンロードが始まらない」ように見えました。

## V46anの方式

- Download RWLOGは通常の `href="/download/rwlog" download` を使う
- クリック直後にブラウザ標準のnative downloadを開始
- JavaScriptはRWLOG本体を `fetch` / `blob` しない
- native download中は `downloading=true` のまま保持
- `/status.json` pollingは完全停止
- 自動タイムアウトでは再開しない
- ダウンロード完了後に **Resume UI after download** を押して状態通信を再開

ブラウザはHTTP接続中のダウンロード完了をJavaScriptへ確実に通知できないため、
自動再開よりも競合を起こさないことを優先して明示的なResume方式にしています。

## サーバ側

V46amで追加した次の処理はそのままです。

- 1460 byte単位
- partial writeは送れた分だけ前進
- 一時0 byte書き込みは最大15秒待つ
- client切断時は失敗
- `Connection: close`

## 変更しないもの

- V46al previous-peak active control
- V46aj MEKF
- ZEROクロス3 ms固定補償
- ピーク検出
- Q gain / Ki
- 電流モデル / I0
- 300 mA / 最大100 ms
- ESTOP / 安全条件
- V46akの電流・wheel速度観測
- RWLOG v51 / 258 byte sample layout
- 測定ログ内容

識別子:

```text
attitude_validation_revision = v46aj_fixed_3ms_compensation_20260920
amplitude_control_revision = v46al_previous_peak_active_control_20260921
rwlog_download_revision = v46an_native_download_hold_20260921
```
