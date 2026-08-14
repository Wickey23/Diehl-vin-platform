import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'config.json'

root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)

messagebox.showinfo(
    'Diehl VIN Initializer',
    'Choose the EXISTING Excel workbook this computer should use.\n\n'
    'The worker writes into this same workbook so your data validation, formulas, tables and formatting remain in place.'
)
path = filedialog.askopenfilename(
    title='Choose existing VIN master workbook',
    filetypes=[('Excel workbooks', '*.xlsx *.xlsm'), ('All files', '*.*')]
)
if not path:
    raise SystemExit('No workbook selected.')

python = ROOT / '.venv' / 'Scripts' / 'python.exe'
lookup = f'"{python}" "{ROOT / "vin_lookup.py"}"'
CONFIG.write_text(json.dumps({
    'masterWorkbook': path,
    'vinLookupCommand': lookup,
    'port': 8765
}, indent=2), encoding='utf-8')

messagebox.showinfo(
    'Initialization complete',
    f'Workbook selected:\n{path}\n\n'
    'The Diehl worker will now start automatically with Windows.\n'
    'From now on, open the website and press Start.'
)
