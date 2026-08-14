import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'config.json'

root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)

path = filedialog.askopenfilename(
    title='Choose existing VIN master workbook',
    filetypes=[('Excel workbooks', '*.xlsx *.xlsm'), ('All files', '*.*')]
)
if not path:
    root.destroy()
    raise SystemExit('No workbook selected.')

python = ROOT / '.venv' / 'Scripts' / 'python.exe'
lookup = f'"{python}" "{ROOT / "vin_lookup.py"}"'
CONFIG.write_text(json.dumps({
    'masterWorkbook': path,
    'vinLookupCommand': lookup,
    'port': 8765
}, indent=2), encoding='utf-8')

messagebox.showinfo(
    'Workbook saved',
    f'This computer will use:\n{path}\n\n'
    'The selection is saved locally. Use START DIEHL VIN whenever the local worker needs to be started or restarted.'
)
root.destroy()
