import json, os, re, socket, sqlite3, subprocess, threading, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent