"""Cross-site extraction of visible interactive controls from the live DOM."""

from typing import Any

from playwright.async_api import Page

from browser_agent.observation.accessibility import accessible_label, accessible_role
from browser_agent.schemas.observation import InteractiveElement

_DOM_SNAPSHOT_SCRIPT = r"""() => {
  const clean = value => (value || '').replace(/\s+/g, ' ').trim().slice(0, 1000);
  const visible = el => {
    if (el.hidden || el.getAttribute('aria-hidden') === 'true') return false;
    const style = window.getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden' &&
      style.visibility !== 'collapse' && el.getClientRects().length > 0;
  };
  const isDisabled = el => el.matches(':disabled') || el.getAttribute('aria-disabled') === 'true';
  const byId = id => id ? document.getElementById(id) : null;
  const labelText = node => {
    const clone = node.cloneNode(true);
    clone.querySelectorAll('input, select, textarea, button, [role="button"], [role="checkbox"], [role="radio"], [role="combobox"], [role="textbox"]').forEach(control => control.remove());
    return clean(clone.textContent);
  };
  const labelFor = el => {
    const labels = el.labels ? Array.from(el.labels) : [];
    const labelledBy = (el.getAttribute('aria-labelledby') || '').split(/\s+/)
      .map(byId).filter(Boolean);
    const text = [...labels.map(labelText), ...labelledBy.map(labelText)];
    const wrapping = el.closest('label');
    if (wrapping) text.push(labelText(wrapping));
    // input.labels and closest('label') often refer to the same wrapping label.
    // Deduplicate identical sources while preserving order and distinct text.
    return clean([...new Set(text.map(clean).filter(Boolean))].join(' ')) || null;
  };
  const elements = new Set(document.querySelectorAll(
    'button, a[href], input, textarea, select, [role="button"], [role="link"], ' +
    '[role="checkbox"], [role="radio"], [role="combobox"], [role="switch"], ' +
    '[role="textbox"], [role="searchbox"], [role="spinbutton"], [role="slider"], ' +
    '[role="menuitem"], [role="tab"], [contenteditable="true"], [tabindex]:not([tabindex="-1"])'
  ));
  const controls = [];
  for (const el of elements) {
    if (!visible(el)) continue;
    const tag = el.tagName.toLowerCase();
    const inputType = tag === 'input' ? (el.getAttribute('type') || 'text').toLowerCase() : null;
    if (inputType === 'hidden') continue;
    const role = el.getAttribute('role') || (el.isContentEditable ? 'textbox' : null);
    let kind = 'interactive';
    if (tag === 'button' || ['button', 'menuitem', 'tab'].includes(role) ||
        (tag === 'input' && ['button', 'submit', 'reset', 'image'].includes(inputType))) kind = 'button';
    else if (tag === 'a' || role === 'link') kind = 'link';
    else if (tag === 'select' || role === 'combobox') kind = 'dropdown';
    else if (tag === 'textarea') kind = 'textarea';
    else if (el.isContentEditable || role === 'textbox' || role === 'searchbox') kind = 'text_input';
    else if (inputType === 'checkbox' || role === 'checkbox' || role === 'switch') kind = 'checkbox';
    else if (inputType === 'radio' || role === 'radio') kind = 'radio';
    else if (inputType === 'file') kind = 'file_upload';
    else if (tag === 'input') kind = 'text_input';
    const ariaLabel = clean(el.getAttribute('aria-label')) || null;
    const buttonValue = ['button', 'submit', 'reset', 'image'].includes(inputType) ? el.value : '';
    const text = clean(el.innerText || buttonValue || el.getAttribute('alt')) || null;
    const name = el.getAttribute('name');
    const id = el.getAttribute('id');
    const title = el.getAttribute('title');
    const placeholder = el.getAttribute('placeholder');
    const label = labelFor(el);
    // Arbitrary sites do not provide reliable sensitivity metadata. Keep
    // editable values out of snapshots rather than risk capturing user data.
    controls.push({
      tag_name: tag, element_type: kind, role, label, text,
      placeholder: clean(placeholder) || null, name: clean(name) || null,
      id_attribute: clean(id) || null, aria_label: ariaLabel,
      title: clean(title) || null,
      required: el.required === true || el.getAttribute('aria-required') === 'true',
      disabled: isDisabled(el), visible: true, enabled: !isDisabled(el), input_type: inputType,
      is_submit_control: (tag === 'button' && el.type === 'submit' && Boolean(el.form)) ||
        (tag === 'input' && Boolean(el.form) && ['submit', 'image'].includes(inputType)),
      options: tag === 'select' ? Array.from(el.options).map(option => clean(option.textContent)).filter(Boolean) : [],
      current_value: null,
      checked: ['checkbox', 'radio'].includes(inputType) ? Boolean(el.checked) :
        (['checkbox', 'radio', 'switch'].includes(role) && el.getAttribute('aria-checked') !== null ? el.getAttribute('aria-checked') === 'true' : null),
      selected_index: tag === 'select' ? el.selectedIndex : null
    });
  }
  const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
    .filter(visible).map(el => clean(el.innerText)).filter(Boolean);
  return {
    url: location.href,
    title: document.title || '',
    headings,
    page_text: clean(document.body?.innerText || '').slice(0, 20000),
    controls
  };
}"""


class DOMParser:
    """Read a rendered page into normalized page and control data."""

    async def parse(self, page: Page) -> dict[str, Any]:
        """Return an atomic DOM snapshot, filtering hidden controls and values."""
        return await page.evaluate(_DOM_SNAPSHOT_SCRIPT)

    def parse_elements(self, controls: list[dict[str, Any]]) -> list[InteractiveElement]:
        """Convert raw descriptors into snapshot models with unique local IDs."""
        parsed: list[InteractiveElement] = []
        for index, item in enumerate(controls, start=1):
            parsed.append(
                InteractiveElement(
                    element_id=f"e{index:04d}",
                    tag_name=item.get("tag_name") or "unknown",
                    element_type=item.get("element_type") or "interactive",
                    role=accessible_role(item),
                    label=accessible_label(item),
                    text=item.get("text"),
                    placeholder=item.get("placeholder"),
                    name=item.get("name"),
                    id_attribute=item.get("id_attribute"),
                    aria_label=item.get("aria_label"),
                    required=bool(item.get("required", False)),
                    disabled=bool(item.get("disabled", False)),
                    visible=bool(item.get("visible", True)),
                    enabled=bool(item.get("enabled", True)),
                    input_type=item.get("input_type"),
                    is_submit_control=bool(item.get("is_submit_control", False)),
                    options=item.get("options") or [],
                    current_value=item.get("current_value"),
                    checked=item.get("checked"),
                    selected_index=item.get("selected_index"),
                )
            )
        return parsed
