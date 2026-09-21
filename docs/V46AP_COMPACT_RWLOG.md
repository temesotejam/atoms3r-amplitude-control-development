# V46ap / 0.46.41 — Compact RWLOG

## 目的

V46aoまでで native download、1460 byte送信、partial write、HTTP Range resume を導入しても、長いRWLOGのダウンロードが開始しない／途中で停滞する症状が残りました。

V46apでは転送方式をさらに複雑化せず、**計測中に生成・保持するログ量と、ダウンロード開始時に構築するmetadata量そのものを減らします**。

制御則、姿勢推定、3 ms ZEROクロス補償、ピーク判定、Qゲイン、Ki、電流モデル、fast solver、300 mA・最大100 ms、ESTOPは変更しません。

## 1. 通常時系列を50 Hz固定へ戻す

既存の `LogSample` は258 byteで、これまでパルス中だけ20 msから2 msへ切り替えて完全な258 byte行を500 Hzで保存していました。

V46apでは `LogSample` を常に20 ms（50 Hz）で保存します。

- 既存 `LogSample`: 258 byte
- 周期: 20 ms
- 30秒の理論量: 約387 kB
- PSRAM確保: 1 MiB
- 1 MiBで約81秒分を保持可能

RWLOGの通常時系列レイアウトはv51の258 byteを維持します。

## 2. パルス中2 ms観測を26 byteへ分離

電流立ち上がりの観測は残す必要があるため、パルス中のみ2 msで `PulseAuditSample` を記録します。

1行26 byteで、次だけを保存します。

- time_us
- pulse_id
- motor_cmd_mA
- actual_current_mA
- wheel_speed_x100_rpm
- current_age_us
- wheel_speed_age_us
- current_valid
- wheel_speed_valid

このデータは既存RWLOGヘッダの未使用だったsummary領域へ格納します。

- 周期: 2 ms
- PSRAM確保: 512 KiB
- 30秒すべてがパルス中という極端な場合でも約390 kB
- 512 KiBで約40秒分を保持可能

通常の30秒振幅制御ではパルス時間は全体の一部なので、実際の使用量はこれより大幅に小さくなります。

## 3. Autonomous metadataをcompact化

従来は過去の校正、Q_IDENT、各種shadow、solver診断などの履歴を同じmetadata JSON生成器が抱えており、1 MiBをreserveし、最大896 KiBまで詳細metadataを許容していました。

V46apのAutonomous実行では専用の `v46ap_compact` metadataへ切り替え、192 KiBをreserveします。

残す主な情報は次です。

- 現在のファームウェア／姿勢推定／振幅制御revision
- 目標振幅と固定3 ms補償
- ピークイベント
- ZEROクロス状態
- rate-only予測
- 直前ピーク補正
- Q指令と予測次ピーク
- 入力直前の実電流
- 入力直前のホイール速度
- パルス幅、指令電流、実行結果

過去実験専用の巨大metadataはAutonomousでは生成しません。旧モードの出力コード自体は残しています。

## 4. ダウンロード経路

V46aoまでの以下の対策は維持します。

- native browser download
- TCP MSS相当1460 byte送信
- partial write対応
- 一時0 byte write待機
- `Connection: close`
- HTTP Range resume

V46apでは、この経路に送る前のRWLOG自体を小さくします。

## 5. CSV変換

`tools/convert_rwlog_to_csv.py` は従来の `timeseries.csv` に加えて、summary領域が存在する場合は

`pulse_audit.csv`

を出力します。

既存のピーク／ZEROクロスイベントCSVも引き続き生成します。

## 期待する効果

主な改善点は次の2つです。

1. パルス中に258 byteを500 Hzで増やさない
2. ダウンロード開始時に巨大なlegacy metadata Stringを構築しない

これによりPSRAMの占有と断片化、CRC対象データ量、Wi-Fiで送るRWLOGサイズをまとめて減らします。
