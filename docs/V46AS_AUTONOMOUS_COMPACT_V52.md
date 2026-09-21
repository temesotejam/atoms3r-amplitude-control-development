# V46as / 0.46.44 — Autonomous compact RWLOG v52

## 目的

現在の8°・30秒Autonomous振幅制御では、歴史的に積み上がった258 byteの汎用 `LogSample` に、現在の解析で使わないMadgwick比較系列・旧beta系列・旧診断項目が多数残っていました。

V46asでは、**現在のAutonomous測定だけ専用の40 byte時系列へ切り替えます。**
制御則・姿勢推定・安全条件・ダウンロード転送方式は変更しません。

## 主時系列

RWLOG v52のAutonomous主時系列は `AutonomousCompactSample` です。

- 40 byte / row
- 20 ms = 50 Hz
- 30秒で約60,000 byte

保存項目:

- time
- test time
- pulse id
- MEKF measurement-relative angle
- 3 ms補償後のcontrol angle
- pitch rate
- motor command
- Roller actual current
- battery voltage
- pulse width
- current freshness
- IMU freshness
- state
- pulse active / direction
- LED sync event
- current validity
- MEKF accel update/trust diagnostics

旧258 byte `LogSample` は過去形式と非Autonomous経路の互換用に残しますが、現在のAutonomous Runでは保存・CRC・送信しません。

## 2 ms Pulse Audit

V46apの26 byte `PulseAuditSample` は維持します。

モータpulse中だけ2 msで、

- command current
- actual current
- wheel speed
- current age
- wheel-speed age
- validity

を保存します。

## 制御イベント

Autonomous metadataは現在必要な情報だけに絞ります。

Peak:
- peak time / side / amplitude
- target / error
- side integrals
- pending Q

Zero cross:
- zero-cross time / rate
- previous peak
- rate-only baseline
- previous-peak correction
- target
- Q feed-forward / integral / command / predicted effective Q
- predicted next peak
- battery
- pre-input measured current + freshness
- pre-input wheel speed + freshness
- solver width
- command current / pulse width
- output / validity / reason

過去のQ_IDENT、calibration、E2、旧shadow、solver-audit全体などは現在のAutonomous metadataには入れません。

## ダウンロード

転送方式は変更しません。

- V46ar: metadata/header/CRCをDownload要求前に準備
- V46aq/V46al: 4096 byte単位のHTTP 200直接送信
- HTTP Rangeなし
- native-download holdなし

## RWLOG version

- legacy / non-Autonomous: v51
- current Autonomous compact: **v52**

`tools/convert_rwlog_to_csv.py` はv23–v52を読み込み、v52も `timeseries.csv`、`pulse_audit.csv`、Autonomous event CSVへ変換できます。
