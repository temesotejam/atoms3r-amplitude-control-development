# V46am / 0.46.38 — RWLOGダウンロード安定化

## 目的

V46alの測定・姿勢推定・実制御を変更せず、測定後のRWLOGダウンロードだけを安定化します。

実機では、測定完了後のRWLOGダウンロード中に転送速度が低下し、
ブラウザが最終的に「再開を待機」する症状が確認されました。

## 原因として修正した2点

### 1. Web UIの3秒固定解除

V46al以前はDownload RWLOGを押すとローカルの `downloading` をtrueにしますが、
3秒後に強制的にfalseへ戻していました。

そのため3秒を超えるダウンロードでは、ページが再び1秒周期で
`/status.json` を取得し始め、RWLOG転送と同じAtomS3R Wi-Fi接続を競合させていました。

V46amでは `fetch('/download/rwlog')` が完全に終了するまで
`downloading=true` を維持し、その間はstatus pollingを行いません。

### 2. Wi-Fi部分書き込み

旧実装は4096 byteを書こうとして `client.write()` が4096未満を返すと、
一部が正常送信されていても即座に `rwlog_stream_failed` として終了していました。

V46amでは

- TCP MSS相当の1460 byte単位
- partial writeは送れた分だけ前進して残りを再送
- 0 byteの一時停滞は最大15秒待つ
- client切断だけは即失敗
- HTTPレスポンスは `Connection: close`

とします。

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
- RWLOG v51の時系列バイナリ配置
- RWLOGに保存する測定内容

識別子:

```text
attitude_validation_revision = v46aj_fixed_3ms_compensation_20260920
amplitude_control_revision = v46al_previous_peak_active_control_20260921
rwlog_download_revision = v46am_fetch_backpressure_20260921
```
