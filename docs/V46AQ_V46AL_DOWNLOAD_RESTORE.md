# V46aq / 0.46.42 — V46al download restore + compact RWLOG

## 目的

V46am / V46an / V46aoではRWLOG転送の安定化を狙って、partial write対応、native browser download、HTTP Range resumeを段階的に追加しました。
しかし実機ではダウンロード不能が解消しなかったため、転送方式を**V46al / 0.46.37で使用していた単純な方式**へ戻します。

一方、V46apで導入したログ軽量化は維持します。

## 維持するもの

- V46alの直前ピーク実制御
- V46ajの3 ms ZEROクロス補償
- MEKF姿勢推定
- 300 mA / 最大100 ms
- ESTOP
- 通常258 byteログを50 Hz固定
- パルス中2 msの26 byte Pulse Audit
- compact Autonomous metadata
- CSV変換時の `pulse_audit.csv`

## 戻すもの: V46al download path

サーバ側はV46alと同じ考え方へ戻します。

- `STREAM_CHUNK_BYTES = 4096`
- `WiFiClient client = server.client()`
- 4096 byte以下の単位で `client.write()`
- 書けたbyte数が要求byte数と一致しなければ失敗
- HTTP 200の単一レスポンス
- `Content-Length = header.crc_offset + sizeof(crc)`
- Range要求は扱わない
- `Connection: close` を追加しない
- partial-write再送を行わない

ブラウザ側もV46al方式へ戻します。

- 通常の `<a href="/download/rwlog">`
- native-download holdなし
- 手動Resume UIなし
- HTTP Range resumeなし
- クリック後は約3秒だけUI側をdownload中扱いにして、その後status pollingへ戻る

## V46apとの組み合わせ

V46al当時との違いは送るRWLOGが小さい点です。

通常30秒の時系列は約387 kBです。
Pulse Auditは極端に30秒全てpulse activeでも約390 kBで、通常はそれより大幅に小さくなります。
Autonomous metadataはlegacy巨大metadataではなくcompact profileです。

したがってV46aqでは、**実績のある単純な転送経路に、軽量化したRWLOGを載せる**ことを狙います。
