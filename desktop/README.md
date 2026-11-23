# MeterDigit Desktop

## One-click Online (Desktop shortcut)

Windows PC pe project folder open karke **ek baar** yeh chalao:

```
desktop\create_desktop_shortcut.bat
```

Desktop pe **MeterDigit Online** shortcut ban jayega.

Uske baad har baar:

1. Desktop pe **MeterDigit Online** double-click
2. Black window open rahe (server) — band mat karo
3. Browser automatically `http://127.0.0.1:43127` khulega
4. Excel upload → JPG ZIP download

Zarurat: [Node.js](https://nodejs.org) installed (LTS).

Direct bina shortcut ke: `desktop\start_online.bat`

---

## Offline window (no browser)

```
desktop\start_desktop.bat
```

Ya source se:

```bash
pip install -r requirements.txt
pip install -r requirements-desktop.txt
python desktop/meterdigit_desktop.py
```

1. **Choose Excel** (`Small`, `Big` columns)
2. **Output folder**
3. **Generate JPGs** (optional ZIP)

---

## Build Windows `.exe`

On a **Windows** PC (Python 3.11+):

```bat
pip install -r requirements.txt
pip install -r requirements-desktop.txt
desktop\build_windows.bat
```

Result: `dist\MeterDigit\MeterDigit.exe`  
Distribute the whole `dist\MeterDigit\` folder (assets are bundled).

> This cloud Linux environment cannot produce a Windows `.exe` directly. Build the bat file on Windows once; after that users only need the EXE folder.
