# V46at / 0.46.45 — Partial-write-safe direct RWLOG download

## 観測された実機症状

V46asでRWLOGを約178 kBまで小さくした後、ブラウザはダウンロードを開始できるようになったが、
約89.5 kB地点で送信が止まり、Chromeが「再開しています…」になる症状を確認した。

この時点で問題はRWLOG生成量ではなく、送信途中の切断に絞られた。

## 原因候補と修正

V46asまでの単純送信は、4096 byteを要求して `client.write()` が4096 byteすべてを受理しなければ即座に失敗としていた。

TCP/Wi-Fi側のbackpressureでは、正常でも1回の `write()` が要求量未満しか受理しないことがある。
V46atではこれをエラー扱いせず、未送信分を続けて送る。

## V46at送信

- 単一HTTP 200
- Content-Lengthあり
- HTTP Rangeなし
- native download holdなし
- 1回のwrite要求: 1460 byte（TCP MSS相当）
- partial write: 送れたbyte数だけ進め、残りを続ける
- 0 byte: 1 ms待って再試行
- 15秒間進捗ゼロ: fail closed
- client切断: fail closed

V46asの40 byte/50 Hz RWLOG v52、26 byte/2 ms Pulse Audit、事前metadata/header/CRC生成は変更しない。

## 制御

以下は変更しない。

- V46al previous-peak active control
- V46aj fixed 3 ms compensation
- 300 mA
- max 100 ms
- ESTOP
- MEKF
- peak / zero-cross logic
