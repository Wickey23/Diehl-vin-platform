from __future__ import annotations

import json
import os
from pathlib import Path

WORKBOOK_NAME = 'DIEHL-VIN-PLATFORM WORKBOOK.xlsx'


def _unique_paths(values):
    seen = set()
    out = []
    for value in values:
        if not value:
            continue
        try:
            path = Path(os.path.expandvars(str(value))).expanduser()
            key = os.path.normcase(os.path.abspath(str(path)))
        except Exception:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def onedrive_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        os.environ.get('OneDriveCommercial'),
        os.environ.get('OneDrive'),
        os.environ.get('OneDriveConsumer'),
    ]
    try:
        candidates.extend(str(p) for p in home.glob('OneDrive*') if p.is_dir())
    except Exception:
        pass
    return [p for p in _unique_paths(candidates) if p.exists() and p.is_dir()]


def is_target(path: Path | str | None) -> bool:
    if not path:
        return False
    try:
        p = Path(path)
        return p.name.casefold() == WORKBOOK_NAME.casefold() and p.exists() and p.is_file()
    except Exception:
        return False


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path_abs = Path(os.path.abspath(str(path)))
        root_abs = Path(os.path.abspath(str(root)))
        return os.path.commonpath([str(path_abs), str(root_abs)]) == str(root_abs)
    except Exception:
        return False


def is_onedrive_target(path: Path | str | None, roots: list[Path] | None = None) -> bool:
    if not is_target(path):
        return False
    p = Path(path)
    roots = roots if roots is not None else onedrive_roots()
    return any(_is_inside(p, root) for root in roots)


def find_shared_workbook(cached_path: str | Path | None = None) -> Path:
    roots = onedrive_roots()

    # Reuse a cached path ONLY when it is still the exact workbook and is inside
    # one of the detected OneDrive roots. This prevents an old local copy from
    # silently becoming the DTNA write target.
    if is_onedrive_target(cached_path, roots):
        return Path(cached_path)

    matches: list[Path] = []

    # Check the OneDrive roots themselves first, then exact-name recursive matches.
    for root in roots:
        direct = root / WORKBOOK_NAME
        if direct.exists() and direct.is_file():
            matches.append(direct)

    if not matches:
        for root in roots:
            try:
                for match in root.rglob(WORKBOOK_NAME):
                    if match.is_file():
                        matches.append(match)
            except (OSError, PermissionError):
                continue

    # Deduplicate aliases/case variants.
    deduped = _unique_paths(matches)
    if len(deduped) == 1:
        return deduped[0]
    if len(deduped) > 1:
        paths = '\n'.join(f' - {p}' for p in deduped[:10])
        raise RuntimeError(
            f'Multiple copies of {WORKBOOK_NAME} were found in OneDrive. '
            'Keep only the company shared/synced copy on this PC so Diehl VIN cannot write to the wrong workbook.\n' + paths
        )

    roots_text = '\n'.join(f' - {p}' for p in roots) if roots else ' - No OneDrive sync root was detected.'
    cached_text = str(cached_path or '').strip()
    cached_note = ''
    if cached_text and is_target(cached_text):
        cached_note = (
            f'\n\nIgnored cached workbook because it is not inside a detected OneDrive root:\n - {cached_text}'
        )

    raise RuntimeError(
        f'{WORKBOOK_NAME} was not found in this PC\'s synced OneDrive folders.\n\n'
        'Open OneDrive/SharePoint and sync the Diehl shared folder that contains the workbook, then press START DIEHL VIN again.\n\n'
        f'Searched:\n{roots_text}{cached_note}'
    )


def load_cached_path(config_path: Path) -> str:
    try:
        data = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
        return str(data.get('masterWorkbook') or '').strip()
    except Exception:
        return ''
