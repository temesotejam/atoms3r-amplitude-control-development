# V46al / 0.46.37 — 直前ピークを使う実制御

## 目的

V46akで取得した5 Runから、次ピーク誤差と直前ピーク振幅の関係を確認しました。
V46alでは、その関係をshadowではなく**実際のQ決定**へ使います。

変更するのは次ピーク予測の基準振幅だけです。次は変更しません。

- 6-state MEKF
- BMI270取得とMEKF設定
- ZEROクロスの3 ms固定補償
- ピーク検出
- side判定
- Q1のside別ゲイン
- Ki
- 電流モデルとI0推定
- bounded fast solver
- 300 mA・最大100 ms
- ESTOPと既存安全条件
- V46akの直前電流・wheel速度観測
- RWLOG v51の時系列バイナリ配置

## 元のV46ak予測

```text
A_free = rate_only(|omega0|, side)
A_pred = A_free + g_side * Q
```

## V46al

V46akの予測誤差
`actual_next_peak - V46ak_predicted_next_peak`
を、10〜30秒区間の5 Run・target 8°で次ピークsideごとに直前ピークへ回帰しました。

```text
correction = c_side + k_side * (A_prev - 8 deg)
A_free_v46al = max(0, A_free_v46ak + clamp(correction, -0.70, +0.70))
A_pred_v46al = A_free_v46al + g_side * Q
```

最終係数:

```text
next side +:
  c = +0.591392151 deg
  k = -0.442636343
  previous-peak support = 7.19424 .. 9.34474 deg

next side -:
  c = -0.157912422 deg
  k = +0.585367534
  previous-peak support = 6.95706 .. 8.75588 deg
```

## 適用条件

補正は次をすべて満たすときだけ使います。

- target = 8.0 deg
- t_test >= 10.0 s
- previous peakがfinite
- previous peakがnext sideごとの5 Run測定support内

それ以外はV46ak/V46ajのrate-only予測をそのまま使います。
10°・12°へは8°データを外挿しません。

## なぜ複雑な再回帰を使わないか

5 Runの閉ループデータではZEROクロス角速度とQが強く相関しています。
角速度・Q・wheel速度などを同時に再フィットすると、予測RMSEは下がっても
実制御に使う係数が閉ループ相関を拾う可能性があります。

そのためV46alでは、既存rate-only式とQ gainを固定し、
5 Runすべてで改善した**直前ピーク残差補正だけ**を追加します。

leave-one-run-outで、現在予測RMSEは約0.436°、
直前ピーク補正（±0.70° cap）のモデル族は約0.295°でした。
この数値は閉ループ改善を保証するものではないため、V46alで実制御評価します。

## 次の測定

まず target 8°、3 ms固定、30秒を3 Run取得します。
主評価は10〜30秒です。

- target 8°に対するpeak RMSE / MAE / bias
- + / - side別誤差
- Qとpulse width
- previous_peak_control_applied / clamped / reason
- 振幅の交互振動や発散がないか
- V46ak 5 Runとの比較

改善しなければV46akへ戻せるよう、V46aj/V46akの確定部分は変更しません。
