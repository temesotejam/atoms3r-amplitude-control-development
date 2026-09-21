# V46ar / 0.46.43 — Prepared RWLOG before download

## 目的

V46aqでダウンロード経路をV46alの単純な4096 byte直接送信へ戻しても、実機ではダウンロード開始不能が残りました。

このためV46arでは、**Download要求を受けてからmetadata生成とCRC計算を行う設計を廃止**します。

## 変更

測定終了後、Webサーバが次の要求を処理する前に一度だけ次を実行します。

1. compact Autonomous metadataを生成
2. RWLOG headerを確定
3. 通常50 Hz samplesと2 ms Pulse Auditを含むCRC32を計算
4. metadata、header、CRC、総byte数をキャッシュ

この処理が成功した場合だけ `rwlog_downloadable=yes` になります。

Download要求側ではmetadata生成もCRC計算も行わず、既に準備済みの

- header
- metadata
- 50 Hz samples
- 2 ms Pulse Audit
- CRC

をV46alの4096 byte直接送信で順番に送ります。

## WebUI診断

WebUIには次を表示します。

- `rwlog_prepare_state`
- metadata bytes
- total RWLOG bytes
- metadata生成時間
- CRC計算時間
- 合計準備時間

状態は主に次です。

- `not_prepared`
- `metadata`
- `metadata_failed`
- `crc`
- `ready`
- `sending`
- `send_failed`

準備に失敗した場合はDownloadボタンを有効にしません。

## シリアル

成功時は `RWLOG prepared ...`、metadata生成失敗時は `RWLOG prepare FAIL ...` を出力します。

これにより、ブラウザ側で「ダウンロードが始まらない」場合でも、押す前にRWLOG準備が完了しているかを確認できます。

## 維持するもの

- V46alの直前ピーク実制御
- V46ajの3 ms補償
- V46ap compact RWLOG
- V46aqのV46al 4096 byte直接送信
- 300 mA / 最大100 ms
- ESTOP
