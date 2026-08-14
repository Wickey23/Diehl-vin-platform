from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv'
CONFIG = ROOT / 'config.json'
SITE = 'https://diehl-vin-platform.vercel.app'
HEALTH = 'http://127.0.0.1:8765/