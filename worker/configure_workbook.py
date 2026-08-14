import os, secrets, socket
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
ROOT=Path(__file__).resolve().parent; envp=ROOT/'worker.env'
root=tk.Tk(); root.withdraw(); root.attributes('-topmost',True)
messagebox.showinfo('Diehl VIN Worker','Choose the EXISTING Excel workbook that should remain the master database.\n\nThe worker writes to this same file so your validation, formulas, tables and formatting remain in place.')
path=filedialog.askopenfilename(title='Choose existing VIN master workbook',filetypes=[('Excel workbooks','*.xlsx *.xlsm *.xlsb'),('All files','*.*')])
if not path: raise SystemExit('No workbook selected.')
secret=os.environ.get('DIEHL_WORKER_SECRET','').strip() or input('Paste the DTNA_WORKER_SECRET from Vercel, then press Enter: ').strip()
if not secret: raise SystemExit('Worker secret is required.')
base=input('Vercel site URL [https://diehl-vin-platform.vercel.app]: ').strip() or 'https://diehl-vin-platform.vercel.app'
worker_id=f'{socket.gethostname()}-{secrets.token_hex(3)}'
envp.write_text(f'VERCEL_BASE_URL={base.rstrip("/")}\nDTNA_WORKER_SECRET={secret}\nMASTER_WORKBOOK={path}\nWORKER_ID={worker_id}\nPOLL_SECONDS=4\nVIN_LOOKUP_COMMAND=\n',encoding='utf-8')
print('\nConfigured workbook:',path); print('Worker ID:',worker_id)
messagebox.showinfo('Configured',f'Active master workbook:\n{path}\n\nYou can run CONFIGURE_WORKBOOK.bat later to change it.')
