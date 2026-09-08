from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from shared_workbook import find_shared_workbook, load_cached_path

APP_NAME = "DiehlDTNAManual"
ROOT = Path(__file__).resolve().parent
LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", ROOT))

SHARED_ROOT = LOCAL_APPDATA / APP_NAME
PROFILE_DIR = SHARED_ROOT / "browser_profile"
DATA_ROOT = SHARED_ROOT / "data"

OUTPUT_DIR = DATA_ROOT / "output"
CONFIG_FILE = DATA_ROOT / "workbook_config.json"
REPORT_DIR = DATA_ROOT / "report_downloads"
HISTORY_DIR = DATA_ROOT / "history"
CHANGES_DIR = DATA_ROOT / "changes"
LOG_DIR = DATA_ROOT / "logs"

SALES_URL = "https://salesorder-dtna.prd.freightliner.com/SalesOrder/"
API_URL = "https://salesorder-dtna.prd.freightliner.com/SalesOrder/getMainTableData"
REPORT_URL = "https://dealerreporting-dtna.prd.freightliner.com/DealerReporting/?app=salesorder"

PAYLOAD = {
    "soCode": "GNPD",
    "chassisDate": "",
    "glider": "N",
    "customer": "default",
    "baseModel": "default",
    "orderPreApproval": True,
    "orderToReview": True,
    "orderVehSerNo": "default",
    "poUnitNumberSales": "default",
    "salesPerson": "default",
    "soCdList": "",
}

TRACK_FIELDS = [
    "statusMsg", "statusDate", "scheduled", "chassisStartDate",
    "destRecvDate", "origProjDelvDate", "projDelvDate",
    "dispatchDate", "deliveredDate", "customer", "baseMdl", "errorFlag"
]


def ensure_dirs() -> None:
    for p in (PROFILE_DIR, OUTPUT_DIR, REPORT_DIR, HISTORY_DIR, CHANGES_DIR, LOG_DIR):
        p.mkdir(parents=True, exist_ok=True)


def get_working_excel() -> Path:
    """Return this computer's configured Diehl VIN workbook."""
    cached = load_cached_path(ROOT / "config.json")
    workbook = find_shared_workbook(cached)
    log(f"Using configured platform workbook: {workbook}")
    return workbook.resolve()


def migrate_package_data_once() -> None:
    """Copy prior package-local data into the shared persistent data folder once."""
    ensure_dirs()
    migration_marker = DATA_ROOT / "migration_complete.txt"
    if migration_marker.exists():
        return

    for folder_name, destination in (
        ("output", OUTPUT_DIR),
        ("report_downloads", REPORT_DIR),
        ("history", HISTORY_DIR),
        ("changes", CHANGES_DIR),
        ("logs", LOG_DIR),
    ):
        old_folder = ROOT / folder_name
        if not old_folder.exists():
            continue
        destination.mkdir(parents=True, exist_ok=True)
        for item in old_folder.iterdir():
            target = destination / item.name
            try:
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                elif not target.exists():
                    shutil.copy2(item, target)
            except Exception:
                pass

    migration_marker.write_text(
        f"Shared data location: {DATA_ROOT}\n"
        f"Migrated/checked: {datetime.now():%Y-%m-%d %H:%M:%S}\n",
        encoding="utf-8",
    )


def log(message: str) -> None:
    ensure_dirs()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line)
    with (LOG_DIR / "dtna_manual_sync.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def norm_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", clean(value).lower())


def norm_serial(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean(value).upper())


def norm_vin(value: Any) -> str:
    v = norm_serial(value)
    return v if len(v) == 17 else ""


def norm_date(value: Any) -> str:
    raw = clean(value)
    if not raw:
        return ""
    parsed = pd.to_datetime(raw, errors="coerce")
    if pd.isna(parsed):
        return raw
    return parsed.strftime("%Y-%m-%d")


def normalize_response(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [r for r in value if isinstance(r, dict)]
    if isinstance(value, dict):
        for key in ("data", "results", "records", "items"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [r for r in rows if isinstance(r, dict)]
    raise ValueError(f"Unexpected DTNA response type: {type(value).__name__}")


def launch_context(playwright):
    # Use Edge's normal sandbox. Playwright defaults Chromium sandboxing off,
    # which adds --no-sandbox and can make the persistent DTNA Edge profile
    # unstable. Also suppress the crash-restore bubble from prior forced exits.
    args = dict(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        viewport={"width": 1500, "height": 900},
        accept_downloads=True,
        chromium_sandbox=True,
        args=["--disable-session-crashed-bubble"],
    )
    try:
        return playwright.chromium.launch_persistent_context(channel="msedge", **args)
    except PlaywrightError as exc:
        log(f"Installed Edge launch failed; falling back to bundled Chromium: {exc}")
        return playwright.chromium.launch_persistent_context(**args)


def auto_click_login_if_available(page) -> None:
    """
    If DTNA opens to a login page with credentials already autofilled,
    click the Login/Sign In button automatically and wait for navigation.
    """
    page.wait_for_timeout(1200)

    patterns = [
        r"^Login$",
        r"^Log\s*In$",
        r"^Sign\s*In$",
        r"Continue",
    ]

    for pattern in patterns:
        candidates = [
            page.get_by_role("button", name=re.compile(pattern, re.I)),
            page.get_by_role("link", name=re.compile(pattern, re.I)),
            page.get_by_text(re.compile(pattern, re.I), exact=True),
        ]

        for locator in candidates:
            try:
                for i in range(locator.count()):
                    item = locator.nth(i)
                    if not item.is_visible():
                        continue

                    item.click()
                    log(f'Clicked login control matching: {pattern}')
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=30000)
                    except Exception:
                        pass
                    page.wait_for_timeout(2500)
                    return
            except Exception:
                continue


def fetch_sales_orders_from_logged_in_page(page) -> Any:
    return page.evaluate(
        """async ({apiUrl, payload}) => {
            const response = await fetch(apiUrl, {
                method: "POST",
                credentials: "include",
                headers: {
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const contentType = response.headers.get("content-type") || "";
            const bodyText = await response.text();

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${bodyText.slice(0, 500)}`);
            }
            if (!contentType.includes("application/json")) {
                throw new Error(
                    "DTNA returned HTML instead of JSON. The login is not complete."
                );
            }
            return JSON.parse(bodyText);
        }""",
        {"apiUrl": API_URL, "payload": PAYLOAD},
    )


def click_visible(page, patterns: list[str]) -> bool:
    for pattern in patterns:
        candidates = [
            page.get_by_role("button", name=re.compile(pattern, re.I)),
            page.get_by_role("link", name=re.compile(pattern, re.I)),
            page.get_by_text(re.compile(pattern, re.I), exact=False),
        ]
        for locator in candidates:
            try:
                for i in range(locator.count()):
                    item = locator.nth(i)
                    if item.is_visible():
                        item.click()
                        return True
            except Exception:
                continue
    return False


def select_auto_vin(page) -> None:
    for i in range(page.locator("select").count()):
        sel = page.locator("select").nth(i)
        try:
            options = sel.locator("option").all_text_contents()
            match = next((x for x in options if "AUTO VIN" in x.upper()), None)
            if match:
                sel.select_option(label=match)
                return
        except Exception:
            pass

    for locator in [
        page.get_by_text("AUTO VIN", exact=True),
        page.get_by_role("option", name="AUTO VIN"),
    ]:
        try:
            if locator.count() and locator.first.is_visible():
                locator.first.click()
                return
        except Exception:
            pass

    for i in range(page.get_by_role("combobox").count()):
        combo = page.get_by_role("combobox").nth(i)
        try:
            if combo.is_visible():
                combo.click()
                page.wait_for_timeout(500)
                option = page.get_by_text("AUTO VIN", exact=True)
                if option.count() and option.first.is_visible():
                    option.first.click()
                    return
        except Exception:
            pass

    raise RuntimeError("Could not select the saved AUTO VIN template.")


def set_order_received_date_max_range(page) -> None:
    print()
    print('Opening the Order Received Date calendar...')

    calendar_clicked = False

    try:
        label = page.get_by_text(
            re.compile(r"^Order\s*Received\s*Date$", re.I),
            exact=True
        )
        for i in range(label.count()):
            item = label.nth(i)
            if not item.is_visible():
                continue

            handle = item.element_handle()
            if handle:
                clicked = page.evaluate(
                    """label => {
                        const containers = [
                            label.parentElement,
                            label.parentElement?.parentElement,
                            label.closest('div'),
                            label.closest('mat-form-field'),
                            label.closest('.form-group'),
                            label.closest('.field-container')
                        ].filter(Boolean);

                        for (const container of containers) {
                            const candidates = Array.from(container.querySelectorAll(
                                'button, [role="button"], mat-datepicker-toggle, ' +
                                'svg, i, span[class*="calendar"], span[class*="date"]'
                            ));

                            for (const el of candidates) {
                                const rect = el.getBoundingClientRect();
                                const visible = rect.width > 0 && rect.height > 0;
                                const text = (el.getAttribute('aria-label') || '') + ' ' +
                                             (el.getAttribute('title') || '') + ' ' +
                                             (el.className?.baseVal || el.className || '');
                                if (!visible) continue;

                                const looksCalendar =
                                    /calendar|date|picker/i.test(text) ||
                                    el.tagName.toLowerCase() === 'mat-datepicker-toggle';

                                const isSmallControl = rect.width <= 60 && rect.height <= 60;

                                if (looksCalendar && isSmallControl) {
                                    (el.closest('button,[role="button"]') || el).click();
                                    return true;
                                }
                            }
                        }
                        return false;
                    }""",
                    handle
                )
                if clicked:
                    calendar_clicked = True
                    break
    except Exception:
        pass

    if not calendar_clicked:
        try:
            range_text = page.get_by_text(
                re.compile(r"\d{1,2}/\d{1,2}/\d{4}\s*-\s*\d{1,2}/\d{1,2}/\d{4}")
            )
            for i in range(range_text.count()):
                item = range_text.nth(i)
                if not item.is_visible():
                    continue
                handle = item.element_handle()
                if handle:
                    clicked = page.evaluate(
                        """el => {
                            const row = el.parentElement || el.closest('div');
                            if (!row) return false;

                            const candidates = Array.from(row.querySelectorAll(
                                'button, [role="button"], svg, i, mat-datepicker-toggle'
                            ));

                            for (const c of candidates) {
                                const rect = c.getBoundingClientRect();
                                const er = el.getBoundingClientRect();
                                const visible = rect.width > 0 && rect.height > 0;
                                const toRight = rect.left >= er.right - 10;
                                const nearby = rect.left - er.right < 120;
                                const small = rect.width <= 60 && rect.height <= 60;

                                if (visible && toRight && nearby && small) {
                                    (c.closest('button,[role="button"]') || c).click();
                                    return true;
                                }
                            }
                            return false;
                        }""",
                        handle
                    )
                    if clicked:
                        calendar_clicked = True
                        break
        except Exception:
            pass

    if not calendar_clicked:
        for pattern in (
            r"calendar",
            r"choose\s*date",
            r"open\s*calendar",
            r"date\s*picker",
        ):
            locator = page.get_by_role("button", name=re.compile(pattern, re.I))
            try:
                for i in range(locator.count()):
                    btn = locator.nth(i)
                    if btn.is_visible():
                        btn.click()
                        calendar_clicked = True
                        break
            except Exception:
                pass
            if calendar_clicked:
                break

    if not calendar_clicked:
        print()
        print("The program could not click the small calendar icon automatically.")
        print("Please click the small calendar icon next to Order Received Date yourself.")
        input("After the date picker opens, return here and press ENTER... ")

    page.wait_for_timeout(700)

    selected = False

    try:
        selected = page.evaluate(
            """() => {
                const normalize = s => (s || '')
                    .replace(/[–—−]/g, '-')
                    .replace(/\s+/g, ' ')
                    .trim()
                    .toLowerCase();

                const nodes = Array.from(document.querySelectorAll(
                    'button, a, li, div, span, p, [role="option"]'
                ));

                const match = nodes.find(el => {
                    const t = normalize(el.innerText || el.textContent);
                    return t.includes('-48 months to +12 months');
                });

                if (!match) return false;
                const target =
                    match.closest('button, a, li, [role="button"], [role="option"]') || match;
                target.click();
                return true;
            }"""
        )
    except Exception:
        selected = False

    if not selected:
        locator = page.get_by_text(
            re.compile(r"-\s*48\s*months\s*to\s*\+\s*12\s*months", re.I),
            exact=False
        )
        try:
            for i in range(locator.count()):
                item = locator.nth(i)
                if item.is_visible():
                    item.click()
                    selected = True
                    break
        except Exception:
            pass

    if not selected:
        print()
        print('Please select "-48 months to +12 months" manually.')
        input("After selecting it, return here and press ENTER... ")

    page.wait_for_timeout(500)

    ok_clicked = False
    ok = page.get_by_role("button", name=re.compile(r"^OK$", re.I))
    try:
        for i in reversed(range(ok.count())):
            btn = ok.nth(i)
            if btn.is_visible():
                btn.click()
                ok_clicked = True
                break
    except Exception:
        pass

    if not ok_clicked:
        print("Click OK in the calendar picker manually.")
        input("After clicking OK, return here and press ENTER... ")

    page.wait_for_timeout(800)
    log('Order Received Date set to "-48 months to +12 months" using the calendar picker.')


def _reporting_ready(page, timeout_ms: int = 12000) -> bool:
    try:
        page.get_by_text(re.compile(r"Order\s*Received\s*Date", re.I), exact=False).first.wait_for(
            state="visible", timeout=timeout_ms
        )
        return True
    except Exception:
        return False


def open_reporting_page(page) -> None:
    """Open Dealer Reporting with one automatic clean retry if the SPA hangs."""
    last_error = None
    for attempt in range(1, 3):
        try:
            log(f"Opening Dealer Reporting (attempt {attempt}/2)...")
            page.goto(REPORT_URL, wait_until="domcontentloaded", timeout=60_000)
            auto_click_login_if_available(page)
            if _reporting_ready(page, 15_000):
                log("Dealer Reporting loaded and Order Received Date is visible.")
                return
            last_error = RuntimeError("Order Received Date did not appear after Dealer Reporting navigation.")
        except Exception as exc:
            last_error = exc

        if attempt == 1:
            log(f"Dealer Reporting first load did not complete: {last_error}. Retrying cleanly...")
            try:
                page.goto("about:blank", wait_until="domcontentloaded", timeout=10_000)
            except Exception:
                pass
            page.wait_for_timeout(700)

    raise RuntimeError(
        "Dealer Reporting did not finish loading after two attempts. "
        f"Last error: {last_error}"
    )


def download_auto_vin_report(page) -> Path:
    try:
        open_reporting_page(page)
    except Exception as exc:
        print()
        print("Dealer Reporting did not load normally.")
        print(f"Details: {exc}")
        print("You can finish login/MFA or refresh Dealer Reporting manually in the open Edge window.")
        input("When Order Received Date is visible, return here and press ENTER to continue... ")

    set_order_received_date_max_range(page)

    if not click_visible(page, [r"Export\s*to\s*Excel", r"Export"]):
        raise RuntimeError("Could not find Export to Excel on Dealer Reporting.")

    page.wait_for_timeout(1500)
    select_auto_vin(page)
    page.wait_for_timeout(700)

    with page.expect_download(timeout=120_000) as info:
        clicked = False
        for pattern in (r"^Export$", r"Download", r"Export\s*to\s*Excel"):
            locator = page.get_by_role("button", name=re.compile(pattern, re.I))
            try:
                for i in reversed(range(locator.count())):
                    item = locator.nth(i)
                    if item.is_visible():
                        item.click()
                        clicked = True
                        break
            except Exception:
                pass
            if clicked:
                break

        if not clicked:
            raise RuntimeError("Could not click the final Export button.")

    download = info.value
    suffix = Path(download.suggested_filename).suffix or ".xlsx"
    dest = REPORT_DIR / f"AUTO_VIN_{datetime.now():%Y%m%d_%H%M%S}{suffix}"
    download.save_as(str(dest))
    log(f"AUTO VIN report downloaded: {dest.name}")
    return dest


def read_report(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str).fillna("")
    return pd.read_excel(path, dtype=str).fillna("")


def find_col(df: pd.DataFrame, names: list[str]) -> str | None:
    normalized = {norm_header(c): c for c in df.columns}
    for name in names:
        k = norm_header(name)
        if k in normalized:
            return normalized[k]
    for k, original in normalized.items():
        if any(norm_header(name) in k for name in names):
            return original
    return None


def build_report_map(path: Path) -> dict[str, dict[str, str]]:
    df = read_report(path)

    serial_col = find_col(df, ["Serial Number", "Vehicle Serial Number", "Serial No"])
    service_col = find_col(df, ["In-Service Date", "In Service Date", "Inservice Date"])
    vin_col = find_col(df, ["VIN", "Vehicle Identification Number", "Full VIN"])

    if not serial_col or not service_col or not vin_col:
        raise RuntimeError(
            "AUTO VIN report must contain Serial Number, In-Service Date, and VIN. "
            f"Found columns: {list(df.columns)}"
        )

    mapping: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        serial = norm_serial(row.get(serial_col, ""))
        vin = norm_vin(row.get(vin_col, ""))
        service = norm_date(row.get(service_col, ""))

        keys: set[str] = set()
        if serial:
            keys.add(serial)
            if len(serial) >= 8:
                keys.add(serial[-8:])
            if len(serial) >= 7:
                keys.add(serial[-7:])
        if vin:
            keys.add(vin[-8:])
            keys.add(vin[-7:])

        for key in keys:
            existing = mapping.get(key, {"VIN": "", "inServiceDate": ""})
            mapping[key] = {
                "VIN": vin or existing["VIN"],
                "inServiceDate": service or existing["inServiceDate"],
            }

    return mapping


def enrich(records: list[dict[str, Any]], mapping: dict[str, dict[str, str]]) -> None:
    for row in records:
        serial = norm_serial(row.get("serialNo"))
        lead = norm_serial(row.get("leadSerialNo"))

        keys = []
        for candidate in (serial, lead):
            if candidate:
                keys.append(candidate)
                if len(candidate) >= 8:
                    keys.append(candidate[-8:])
                if len(candidate) >= 7:
                    keys.append(candidate[-7:])

        found = None
        method = ""
        for key in keys:
            if key in mapping:
                found = mapping[key]
                method = "Serial Number"
                break

        if found:
            row["VIN"] = found.get("VIN", "")
            row["inServiceDate"] = found.get("inServiceDate", "")
            row["vinSource"] = "Dealer Reporting AUTO VIN"
            row["vinMatchMethod"] = method
        else:
            row.setdefault("VIN", "")
            row.setdefault("inServiceDate", "")
            row["vinSource"] = ""
            row["vinMatchMethod"] = ""


def clean_for_compare(value: Any) -> str:
    raw = clean(value)
    raw = re.sub(r"^CURRENT:\s*", "", raw, flags=re.I)
    return re.sub(r"\s+", " ", raw).strip()


def row_key(row: dict[str, Any]) -> str:
    return "|".join([
        clean(row.get("serialNo")),
        clean(row.get("leadSerialNo")),
        clean(row.get("soCode")),
        clean(row.get("baseMdl")),
        clean(row.get("customer")),
    ])


def previous_snapshot() -> list[dict[str, Any]]:
    path = HISTORY_DIR / "latest_snapshot.json"
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except Exception:
        return []


def compare(old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    old = {row_key(r): r for r in old_rows}
    new = {row_key(r): r for r in new_rows}
    when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    changes: list[dict[str, Any]] = []

    for key, row in new.items():
        prior = old.get(key)
        if prior is None:
            changes.append({
                "changeTime": when, "changeType": "NEW ORDER",
                "serialNo": clean(row.get("serialNo")), "VIN": clean(row.get("VIN")),
                "customer": clean(row.get("customer")), "baseMdl": clean(row.get("baseMdl")),
                "field": "", "oldValue": "", "newValue": ""
            })
            continue

        for field in TRACK_FIELDS:
            before = clean_for_compare(prior.get(field))
            after = clean_for_compare(row.get(field))
            if before != after:
                changes.append({
                    "changeTime": when, "changeType": "FIELD CHANGED",
                    "serialNo": clean(row.get("serialNo")), "VIN": clean(row.get("VIN")),
                    "customer": clean(row.get("customer")), "baseMdl": clean(row.get("baseMdl")),
                    "field": field, "oldValue": before, "newValue": after
                })

    for key, row in old.items():
        if key not in new:
            changes.append({
                "changeTime": when, "changeType": "ORDER REMOVED",
                "serialNo": clean(row.get("serialNo")), "VIN": clean(row.get("VIN")),
                "customer": clean(row.get("customer")), "baseMdl": clean(row.get("baseMdl")),
                "field": "", "oldValue": "", "newValue": ""
            })

    return changes


def add_change_notes_to_current_rows(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    by_serial: dict[str, list[str]] = {}
    change_times: dict[str, str] = {}

    for change in changes:
        serial = norm_serial(change.get("serialNo"))
        if not serial:
            continue

        change_type = clean(change.get("changeType"))
        field = clean(change.get("field"))
        old_value = clean(change.get("oldValue"))
        new_value = clean(change.get("newValue"))

        if change_type == "FIELD CHANGED":
            note = f"{field}: {old_value or '[blank]'} -> {new_value or '[blank]'}"
        elif change_type == "NEW ORDER":
            note = "NEW ORDER"
        elif change_type == "ORDER REMOVED":
            note = "ORDER REMOVED"
        else:
            note = change_type or "Changed"

        by_serial.setdefault(serial, []).append(note)
        change_times[serial] = clean(change.get("changeTime"))

    for row in records:
        serial = norm_serial(row.get("serialNo"))
        notes = by_serial.get(serial, [])
        row["changeCount"] = len(notes)
        row["changeNotes"] = " | ".join(notes)
        row["lastChangeTime"] = change_times.get(serial, "")


def preserve_date_history(old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> None:
    old = {row_key(r): r for r in old_rows}
    date_fields = {
        "statusDate": "Status Date",
        "chassisStartDate": "Scheduled Chassis Start",
        "destRecvDate": "Destination Receive Date",
        "origProjDelvDate": "Original Projected Delivery",
        "projDelvDate": "Projected Delivery",
        "dispatchDate": "Dispatch Date",
        "deliveredDate": "Delivered Date",
    }

    for row in new_rows:
        prior = old.get(row_key(row))
        if not prior:
            continue

        history = dict(prior.get("_dateHistory") or {})
        for field, label in date_fields.items():
            previous = clean_for_compare(prior.get(field))
            current = clean_for_compare(row.get(field))
            if previous and current and previous != current:
                values = history.get(field, [])
                if not isinstance(values, list):
                    values = [clean(values)] if clean(values) else []
                if previous not in values:
                    values.append(previous)
                history[field] = values

                prior_text = " | ".join(values)
                row[field] = f"CURRENT: {current}\nPRIOR: {prior_text}"

        if history:
            row["_dateHistory"] = history


def load_open_excel_workbook(excel, destination: Path):
    target = os.path.normcase(os.path.abspath(str(destination)))
    for i in range(1, excel.Workbooks.Count + 1):
        candidate = excel.Workbooks.Item(i)
        try:
            full_name = os.path.normcase(os.path.abspath(str(candidate.FullName)))
        except Exception:
            continue
        if full_name == target:
            return candidate
    return None


def write_dataframe_into_same_excel(df: pd.DataFrame, destination: Path) -> None:
    """Update the selected workbook and its existing DTNA sheet in place."""
    try:
        import pythoncom
        import win32com.client
    except Exception as exc:
        raise RuntimeError(
            "pywin32 is required to update the exact selected Excel workbook. "
            f"Details: {exc}"
        ) from exc

    pythoncom.CoInitialize()
    excel = None
    workbook = None
    opened_by_script = False
    created_excel_instance = False

    try:
        destination = destination.resolve()
        destination_text = str(destination)

        try:
            excel = win32com.client.GetActiveObject("Excel.Application")
            workbook = load_open_excel_workbook(excel, destination)
        except Exception:
            excel = None

        if workbook is None:
            if excel is None:
                excel = win32com.client.DispatchEx("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
                created_excel_instance = True

            workbook = excel.Workbooks.Open(
                destination_text,
                UpdateLinks=0,
                ReadOnly=False,
                IgnoreReadOnlyRecommended=True,
                AddToMru=False,
            )
            opened_by_script = True
            log(f"Opened selected workbook in hidden Excel: {destination}")

        if workbook is None:
            raise RuntimeError(
                "Excel did not return a workbook object for the selected file."
            )

        if excel is None:
            excel = workbook.Application

        excel.DisplayAlerts = False
        excel.ScreenUpdating = False
        excel.EnableEvents = False
        try:
            excel.Calculation = -4135
        except Exception:
            pass

        if bool(workbook.ReadOnly):
            raise RuntimeError(
                "The selected workbook opened read-only. Close duplicate copies, "
                "wait for OneDrive synchronization to finish, and run again."
            )

        try:
            sheet = workbook.Worksheets("DTNA")
        except Exception:
            sheet = workbook.Worksheets.Add(After=workbook.Worksheets(workbook.Worksheets.Count))
            sheet.Name = "DTNA"

        log('Writing full DTNA dataset to shared workbook sheet: DTNA')

        headers = [str(c) for c in df.columns]
        if not headers:
            raise RuntimeError("No DTNA columns were available to write.")

        table = None
        try:
            if sheet.ListObjects.Count > 0:
                for i in range(1, sheet.ListObjects.Count + 1):
                    candidate = sheet.ListObjects.Item(i)
                    if str(candidate.Name).strip().lower() in {"dtna", "dtnadata"}:
                        table = candidate
                        break
                if table is None:
                    table = sheet.ListObjects.Item(1)
        except Exception:
            table = None

        if table is not None:
            try:
                if table.DataBodyRange is not None:
                    table.DataBodyRange.ClearContents()
            except Exception:
                pass
            try:
                table.HeaderRowRange.ClearContents()
            except Exception:
                pass
        else:
            sheet.UsedRange.ClearContents()

        sheet.Range(
            sheet.Cells(1, 1),
            sheet.Cells(1, len(headers))
        ).Value2 = tuple(headers)

        rows = []
        for raw_row in df.itertuples(index=False, name=None):
            safe = []
            for value in raw_row:
                if value is None:
                    safe.append("")
                    continue
                try:
                    if pd.isna(value):
                        safe.append("")
                        continue
                except Exception:
                    pass
                safe.append(str(value))
            rows.append(tuple(safe))

        block_size = 75
        for offset in range(0, len(rows), block_size):
            block = rows[offset:offset + block_size]
            first_row = offset + 2
            last_row = first_row + len(block) - 1
            sheet.Range(
                sheet.Cells(first_row, 1),
                sheet.Cells(last_row, len(headers))
            ).Value2 = tuple(block)

            if offset % 300 == 0:
                log(f"Writing Excel rows {first_row}-{last_row} of {len(rows) + 1}")

        if table is not None:
            table.Resize(
                sheet.Range(
                    sheet.Cells(1, 1),
                    sheet.Cells(max(2, len(rows) + 1), len(headers))
                )
            )
        else:
            try:
                table = sheet.ListObjects.Add(
                    1,
                    sheet.Range(
                        sheet.Cells(1, 1),
                        sheet.Cells(max(2, len(rows) + 1), len(headers))
                    ),
                    None,
                    1,
                )
                table.Name = "DTNAData"
            except Exception:
                pass

        header_lookup = {name: idx + 1 for idx, name in enumerate(headers)}
        for name in (
            "statusDate", "chassisStartDate", "destRecvDate",
            "origProjDelvDate", "projDelvDate", "dispatchDate",
            "deliveredDate", "changeNotes"
        ):
            col = header_lookup.get(name)
            if col:
                sheet.Columns(col).WrapText = True
                sheet.Columns(col).ColumnWidth = 24

        for name, width in {
            "VIN": 20,
            "inServiceDate": 16,
            "serialNo": 16,
            "leadSerialNo": 18,
            "customer": 28,
            "statusMsg": 22,
        }.items():
            col = header_lookup.get(name)
            if col:
                sheet.Columns(col).ColumnWidth = width

        workbook.Save()
        log(f"Updated shared Excel database successfully: {destination} -> DTNA")

    except Exception as exc:
        raise RuntimeError(
            "Excel could not update the shared workbook. "
            f"Selected path: {destination}\nDetails: {exc}"
        ) from exc
    finally:
        try:
            if excel is not None:
                excel.ScreenUpdating = True
                excel.EnableEvents = True
                try:
                    excel.Calculation = -4105
                except Exception:
                    pass
        except Exception:
            pass

        if workbook is not None and opened_by_script:
            try:
                workbook.Close(SaveChanges=True)
            except Exception:
                pass

        if excel is not None and created_excel_instance:
            try:
                excel.Quit()
            except Exception:
                pass

        pythoncom.CoUninitialize()


def save_all(records: list[dict[str, Any]], changes: list[dict[str, Any]], working_excel: Path) -> None:
    ensure_dirs()

    add_change_notes_to_current_rows(records, changes)
    df = pd.json_normalize(records)
    preferred = [
        "VIN", "inServiceDate", "serialNo", "leadSerialNo",
        "changeCount", "changeNotes", "lastChangeTime",
        "vinSource", "vinMatchMethod", "soCode", "baseMdl", "customer",
        "statusMsg", "statusDate", "scheduled", "chassisStartDate",
        "destRecvDate", "origProjDelvDate", "projDelvDate",
        "dispatchDate", "deliveredDate", "errorFlag"
    ]
    ordered = [c for c in preferred if c in df.columns]
    ordered += [c for c in df.columns if c not in ordered]
    df = df[ordered]

    write_dataframe_into_same_excel(df, working_excel)

    df.to_excel(OUTPUT_DIR / "dtna_sales_orders.xlsx", index=False, sheet_name="DTNA")
    df.to_csv(OUTPUT_DIR / "dtna_sales_orders.csv", index=False, encoding="utf-8-sig")
    (OUTPUT_DIR / "dtna_sales_orders_raw.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    change_columns = [
        "changeTime", "changeType", "serialNo", "VIN", "customer",
        "baseMdl", "field", "oldValue", "newValue"
    ]
    latest = pd.DataFrame(changes, columns=change_columns)
    latest.to_excel(CHANGES_DIR / "latest_changes.xlsx", index=False, sheet_name="Latest_Changes")
    latest.to_csv(CHANGES_DIR / "latest_changes.csv", index=False, encoding="utf-8-sig")

    history_csv = CHANGES_DIR / "dtna_change_log.csv"
    full_hist = latest

    if history_csv.exists() and history_csv.stat().st_size > 0:
        try:
            old_hist = pd.read_csv(history_csv, dtype=str).fillna("")
            if not old_hist.empty:
                full_hist = pd.concat([old_hist, latest], ignore_index=True)
        except pd.errors.EmptyDataError:
            log("Existing change-history CSV was empty. Rebuilding it.")
        except Exception as exc:
            log(f"Could not read existing change-history CSV; rebuilding it: {exc}")

    full_hist.to_csv(history_csv, index=False, encoding="utf-8-sig")
    full_hist.to_excel(CHANGES_DIR / "dtna_change_log.xlsx", index=False, sheet_name="Change_Log")

    snapshot = json.dumps(records, indent=2, ensure_ascii=False)
    (HISTORY_DIR / "latest_snapshot.json").write_text(snapshot, encoding="utf-8")
    (HISTORY_DIR / f"snapshot_{datetime.now():%Y%m%d_%H%M%S}.json").write_text(
        snapshot, encoding="utf-8"
    )

    vin_count = sum(bool(clean(r.get("VIN"))) for r in records)
    service_count = sum(bool(clean(r.get("inServiceDate"))) for r in records)
    status = {
        "status": "SUCCESS",
        "lastRun": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "orderCount": len(records),
        "vinCount": vin_count,
        "inServiceDateCount": service_count,
        "changeCount": len(changes),
        "loginProfile": str(PROFILE_DIR),
        "databaseWorkbook": str(working_excel),
        "databaseSheet": "DTNA",
    }
    (DATA_ROOT / "SYNC_STATUS.txt").write_text(
        "\n".join(f"{k}: {v}" for k, v in status.items()), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--login-only", action="store_true")
    args, _ = parser.parse_known_args()

    ensure_dirs()
    migrate_package_data_once()
    working_excel = get_working_excel()
    log(f"Starting interactive DTNA sync. Workbook: {working_excel}")

    with sync_playwright() as p:
        context = launch_context(p)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(SALES_URL, wait_until="domcontentloaded", timeout=120_000)
            auto_click_login_if_available(page)

            if args.login_only:
                print()
                print("DTNA login initialization opened for this Windows user.")
                print("Complete your own login/MFA in Edge.")
                input("After login is complete, press ENTER to close this login window... ")
                return 0

            try:
                raw = fetch_sales_orders_from_logged_in_page(page)
            except Exception:
                print()
                print("DTNA Sales Order is not authenticated yet.")
                print("Complete login / MFA in Edge, then return here.")
                input("After Sales Order is fully loaded, press ENTER to continue... ")
                raw = fetch_sales_orders_from_logged_in_page(page)

            records = normalize_response(raw)
            log(f"Downloaded {len(records)} Sales Order rows.")

            old_rows = previous_snapshot()
            report_path = download_auto_vin_report(page)
            report_map = build_report_map(report_path)
            enrich(records, report_map)
            preserve_date_history(old_rows, records)
            changes = compare(old_rows, records)
            save_all(records, changes, working_excel)

            print()
            print("DTNA sync complete.")
            print(f"Workbook: {working_excel}")
            print(f"Current rows: {len(records)}")
            print(f"Changes this run: {len(changes)}")
            print(f"History: {CHANGES_DIR / 'dtna_change_log.xlsx'}")
            return 0

        finally:
            context.close()


if __name__ == "__main__":
    raise SystemExit(main())
