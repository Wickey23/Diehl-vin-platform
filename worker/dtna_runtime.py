from __future__ import annotations

import re

import dtna_base as base


# Keep the known-good Sales Order behavior used by the working local program.
try:
    base.PAYLOAD['orderToReview'] = True
except Exception:
    pass


def select_auto_vin(page) -> None:
    """Select AUTO VIN from the Templates field in the Export to Excel dialog.

    Dealer Reporting renders this field as a custom Angular/Material dropdown,
    so generic combobox scanning is unreliable. Scope every click to the export
    dialog and fall back to a manual selection instead of aborting the sync.
    """
    # Wait for the Export to Excel dialog itself, not just the page.
    dialog = None
    for selector in ('[role="dialog"]', 'mat-dialog-container', '.mat-dialog-container', '.mat-mdc-dialog-container'):
        try:
            loc = page.locator(selector)
            for i in range(loc.count()):
                item = loc.nth(i)
                if item.is_visible() and 'Export to Excel' in (item.inner_text() or ''):
                    dialog = item
                    break
        except Exception:
            pass
        if dialog is not None:
            break

    if dialog is None:
        try:
            title = page.get_by_text(re.compile(r'^\s*Export\s+to\s+Excel\s*$', re.I), exact=False)
            title.first.wait_for(state='visible', timeout=15000)
            dialog = title.first.locator('xpath=ancestor::*[@role="dialog" or self::mat-dialog-container][1]')
        except Exception:
            dialog = None

    scope = dialog if dialog is not None else page

    # Native select, if DTNA ever exposes one.
    try:
        selects = scope.locator('select')
        for i in range(selects.count()):
            sel = selects.nth(i)
            if not sel.is_visible():
                continue
            opts = sel.locator('option').all_text_contents()
            match = next((x for x in opts if re.fullmatch(r'\s*AUTO\s*VIN\s*', x or '', re.I)), None)
            if match:
                sel.select_option(label=match)
                return
    except Exception:
        pass

    # Target the visible Templates field shown on the left side of the modal.
    opened = False
    try:
        template_text = scope.get_by_text(re.compile(r'^\s*Templates\s*$', re.I), exact=True)
        for i in range(template_text.count()):
            label = template_text.nth(i)
            if not label.is_visible():
                continue
            opened = bool(label.evaluate("""el => {
                const candidates = [
                    el.closest('mat-select'),
                    el.closest('[role=combobox]'),
                    el.parentElement && el.parentElement.querySelector('mat-select'),
                    el.parentElement && el.parentElement.querySelector('[role=combobox]'),
                    el.parentElement,
                    el.closest('mat-form-field') && el.closest('mat-form-field').querySelector('mat-select,[role=combobox]')
                ].filter(Boolean);
                for (const c of candidates) {
                    const r = c.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        c.click();
                        return true;
                    }
                }
                return false;
            }"""))
            if opened:
                break
    except Exception:
        pass

    # Fallback: use the first visible select/combobox inside this modal, which
    # is the Templates control in the current Dealer Reporting UI.
    if not opened:
        for selector in ('mat-select', '[role="combobox"]', '.mat-select-trigger', '.mat-mdc-select-trigger'):
            try:
                loc = scope.locator(selector)
                for i in range(loc.count()):
                    item = loc.nth(i)
                    if item.is_visible():
                        item.click()
                        opened = True
                        break
            except Exception:
                pass
            if opened:
                break

    if opened:
        page.wait_for_timeout(700)
        for locator in (
            page.get_by_role('option', name=re.compile(r'^\s*AUTO\s*VIN\s*$', re.I)),
            page.get_by_text(re.compile(r'^\s*AUTO\s*VIN\s*$', re.I), exact=True),
        ):
            try:
                for i in range(locator.count()):
                    option = locator.nth(i)
                    if option.is_visible():
                        option.click()
                        page.wait_for_timeout(400)
                        return
            except Exception:
                pass

    print()
    print('AUTO VIN could not be selected automatically.')
    print('In the Export to Excel window, open Templates and choose AUTO VIN.')
    input('After AUTO VIN is selected, return here and press ENTER to continue... ')


# Override only the fragile selector. All other behavior comes from the
# supplied known-good DTNA program.
base.select_auto_vin = select_auto_vin


if __name__ == '__main__':
    raise SystemExit(base.main())
