# V46ao / 0.46.40 — HTTP RangeによるRWLOG途中再開

## 目的

V46alの制御、V46amの部分書き込み対応、V46anのnative downloadを維持したまま、
RWLOG転送が途中で切れた場合にブラウザが**続きから再開**できるようにします。

実機動画では、約72.8 KB / 894 KBで転送が停止し、Chromeが
「再開しています…」へ移行したまま進まないことを確認しました。

## 原因

Chromeは途中切断後に次のようなHTTP Range要求で再開を試みます。

```http
Range: bytes=728xx-
```

V46an以前のAtomS3R側はRangeを解釈せず、常に先頭から200 OKで返していたため、
ブラウザの途中再開が成立しませんでした。

## V46ao

`/download/rwlog` は次に対応します。

- 初回: `200 OK`
- 再開: `206 Partial Content`
- `Accept-Ranges: bytes`
- `Content-Range: bytes start-end/total`
- 範囲外: `416 Range Not Satisfiable`
- `bytes=N-`
- `bytes=N-M`
- `bytes=-N`

RWLOG全体を別バッファへコピーせず、

1. RWLOG header
2. metadata JSON
3. time-series samples
4. CRC32

を1つの仮想ファイルとして扱い、要求されたbyte範囲と交差する部分だけ送信します。

## 継承する転送対策

V46amの次の対策はそのままです。

- 1460 byte単位
- partial write対応
- 一時的な0 byte write待機
- client切断検出
- `Connection: close`

V46anの次の対策も維持します。

- ブラウザ標準native download
- JavaScriptでRWLOG全体をblob化しない
- download中のstatus polling停止
- Resume UIまでstatus通信を自動再開しない

## 変更しないもの

- V46al previous-peak active control
- V46aj MEKF / 3 ms ZEROクロス補償
- peak detector
- Q gain / Ki
- current model / I0
- 300 mA / max 100 ms
- ESTOP
- V46ak observation
- RWLOG v51 / 258 byte sample layout
- 測定ログの内容
