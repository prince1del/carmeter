# MeterDigit

Excel se **Small** (6) aur **Big** (5) numbers bulk upload → har row ki alag **JPG**.

- Meter photo pe original PSD digits
- Sample-style **random crop** (left/right tilt, zoom in/out)
- Daytime **shade** variation
- Filename = Small number (`165105.jpg`)

## Start Online (Desktop shortcut)

Windows pe **ek baar** chalao:

```bat
desktop\create_desktop_shortcut.bat
```

Phir Desktop pe **MeterDigit Online** double-click → server start + browser open  
(`http://127.0.0.1:43127`). Node.js LTS chahiye.

Bina shortcut: `desktop\start_online.bat`

## Desktop app (offline window)

```bat
desktop\start_desktop.bat
```

Ya: `pip install -r requirements-desktop.txt` → `python desktop/meterdigit_desktop.py`

Windows `.exe` build: [`desktop/README.md`](desktop/README.md).

## Excel format

| Small  | Big    |
|--------|--------|
| 165105 | 0703.0 |
| 165309 | 09124  |

- Headers: `Small`, `Big` (case-insensitive)
- Max **2000** rows / batch
- Sample: `public/samples/sample_digits.xlsx`

## Assets

| Path | Role |
|------|------|
| `templates/digit_template.psd` | Digit PSD |
| `data/digit-cache/` | Extracted digit layers |
| `data/meter_background.jpg` | Meter cluster photo |

```bash
npm run extract-digits   # after replacing the PSD
```

## Production (Docker)

Binds **only** loopback for host nginx (`car.houseofprizm.com` → `43129`):

```bash
docker compose up -d --build
# → http://127.0.0.1:43129  (container also listens on 43129)
```

Local without Docker: `npm install && npm run build && npm start` (port **43127**).
