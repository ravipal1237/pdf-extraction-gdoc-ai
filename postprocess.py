"""
Post-processing: normalization, parsing of numbers/dates, line-item extraction, and confidence math.
Designed to be locale-aware and dynamic.
"""
from typing import Any, Dict, List, Optional
import dateparser
from babel.numbers import parse_decimal, NumberFormatError
import hashlib
import re

def sha256_bytes(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()

def normalize_date(s: Optional[str], languages: Optional[List[str]] = None) -> Optional[str]:
    if not s:
        return None
    dt = dateparser.parse(s, languages=languages)
    if not dt:
        return None
    return dt.date().isoformat()

def parse_money(value: Optional[str], locale_hint: Optional[str] = None) -> Optional[float]:
    if not value:
        return None
    s = value.replace('\u00A0', ' ').strip()
    # remove currency symbols (we keep currency separately)
    s = re.sub(r'[^\d,.\-]', '', s)
    if s == '' or s == '-' or s == '--':
        return None
    # Try babel parse
    try:
        if locale_hint:
            return float(parse_decimal(s, locale=locale_hint))
        return float(parse_decimal(s))
    except Exception:
        # fallback heuristics
        s2 = s.replace(',', '')
        try:
            return float(s2)
        except Exception:
            # flip comma/period if looks european
            if s.count(',') > 0 and s.count('.') == 0:
                s3 = s.replace('.', '').replace(',', '.')
                try:
                    return float(s3)
                except Exception:
                    return None
            return None

def entity_value(entity) -> Optional[str]:
    if not entity:
        return None
    if getattr(entity, "normalized_value", None) and getattr(entity.normalized_value, "text", None):
        return entity.normalized_value.text
    return getattr(entity, "mention_text", None)

def entity_conf(entity) -> float:
    if not entity:
        return 0.0
    return float(getattr(entity, "confidence", 0.0))

def safe_get_first(entities, typ):
    for e in entities:
        if getattr(e, "type_", None) == typ:
            return e
    return None

def normalize_docai_document(doc, locale_hint: Optional[str]=None, lang_codes: List[str]=None) -> Dict[str, Any]:
    lang_codes = lang_codes or []
    entities = getattr(doc, "entities", []) or []
    # map common invoice entity types (DocAI invoice processor uses named entities)
    def ev(t): return entity_value(safe_get_first(entities, t))
    vendor_name = ev("supplier_name") or ev("vendor_name") or ev("supplier")
    vendor_tax = ev("supplier_tax_id") or ev("supplier_tax_number") or ev("supplier_tax_id")
    vendor_addr = ev("supplier_address")
    bill_to_name = ev("bill_to_name")
    bill_to_addr = ev("bill_to_address")
    ship_to_name = ev("ship_to_name")
    ship_to_addr = ev("ship_to_address")

    inv_no = ev("invoice_id") or ev("id") or ev("invoice_number")
    po_no = ev("po_number") or ev("purchase_order")
    issue_dt = ev("invoice_date") or ev("issue_date")
    due_dt = ev("due_date")
    currency = ev("currency") or getattr(doc, "document_style", None) and getattr(getattr(doc, "document_style"), "currency", None)

    subtotal = ev("subtotal_amount") or ev("net_amount")
    tax = ev("tax_amount")
    shipping = ev("shipping_amount")
    discount = ev("discount_amount")
    total = ev("total_amount") or ev("invoice_total")
    amount_due = ev("amount_due") or total

    # Normalize
    issue_iso = normalize_date(issue_dt, languages=lang_codes)
    due_iso = normalize_date(due_dt, languages=lang_codes)
    subtotal_f = parse_money(subtotal, locale_hint)
    tax_f = parse_money(tax, locale_hint)
    shipping_f = parse_money(shipping, locale_hint)
    discount_f = parse_money(discount, locale_hint)
    total_f = parse_money(total, locale_hint)
    due_f = parse_money(amount_due, locale_hint)

    # Extract line items from entities with type 'line_item' (DocAI standard)
    line_items = []
    for e in entities:
        if getattr(e, "type_", None) == "line_item":
            props = {getattr(p, "type_", ""): getattr(p, "mention_text", "") for p in getattr(e, "properties", [])}
            qty = parse_money(props.get("line_item/quantity") or props.get("quantity") or "", locale_hint)
            unit_price = parse_money(props.get("line_item/unit_price") or props.get("unit_price") or "", locale_hint)
            amount = parse_money(props.get("line_item/amount") or props.get("amount") or "", locale_hint)
            desc = props.get("line_item/description") or props.get("description") or ""
            sku = props.get("line_item/sku") or props.get("sku") or ""
            tax_rate = None
            tr = props.get("line_item/tax_rate") or props.get("tax_rate") or ""
            if tr:
                try:
                    tax_rate = float(tr.replace('%','').strip())/100.0
                except Exception:
                    tax_rate = None
            line_items.append({
                "line_number": len(line_items)+1,
                "description": desc,
                "sku": sku,
                "quantity": qty,
                "unit_price": unit_price,
                "discount": parse_money(props.get("line_item/discount") or props.get("discount") or "", locale_hint) or 0.0,
                "tax_rate": tax_rate,
                "tax_amount": parse_money(props.get("line_item/tax_amount") or props.get("tax_amount") or "", locale_hint) or None,
                "line_total": amount,
                "confidence": entity_conf(e)
            })

    out = {
        "vendor": {"name": vendor_name, "vat_id": vendor_tax, "address": {"raw": vendor_addr}},
        "bill_to": {"name": bill_to_name, "address": {"raw": bill_to_addr}},
        "ship_to": {"name": ship_to_name, "address": {"raw": ship_to_addr}},
        "invoice": {
            "type": "credit_note" if (total_f is not None and total_f < 0) else "invoice",
            "invoice_number": inv_no,
            "po_number": po_no,
            "issue_date": issue_iso,
            "due_date": due_iso,
            "currency": currency
        },
        "amounts": {
            "subtotal": subtotal_f, "tax": tax_f, "shipping": shipping_f,
            "discount": discount_f, "total": total_f, "amount_due": due_f if due_f is not None else total_f
        },
        "line_items": line_items,
        "confidence": {"overall": None, "by_field": {}},
        "audit": {"parser": "docai-invoice-processor"}
    }
    # fill initial field confidences from entities
    field_map = {
        "invoice.invoice_number": ["invoice_id","id","invoice_number"],
        "invoice.issue_date": ["invoice_date","issue_date"],
        "invoice.due_date": ["due_date"],
        "invoice.currency": ["currency"],
        "vendor.name": ["supplier_name","vendor_name"],
        "vendor.vat_id": ["supplier_tax_id","supplier_tax_number"],
        "amounts.total": ["total_amount","invoice_total"],
        "amounts.subtotal": ["subtotal_amount","net_amount"],
        "amounts.tax": ["tax_amount"]
    }
    by_field = {}
    for k, candidates in field_map.items():
        conf = 0.0
        for c in candidates:
            ent = safe_get_first(entities, c)
            if ent:
                conf = max(conf, entity_conf(ent))
        by_field[k] = conf
    out["confidence"]["by_field"] = by_field
    return out

# confidence math
def approx_equal(a: Optional[float], b: Optional[float], abs_tol=0.02, rel_tol=0.002) -> Optional[bool]:
    if a is None or b is None:
        return None
    if abs(a-b) <= abs_tol:
        return True
    if abs(a-b) <= rel_tol * max(abs(a), abs(b)):
        return True
    return False

def field_adjusted_conf(model_conf: float, validation_ok: Optional[bool], heuristic_ok: Optional[bool]) -> float:
    v = 1.0 if validation_ok is True else (0.6 if validation_ok is None else 0.0)
    h = 1.0 if heuristic_ok is True else (0.6 if heuristic_ok is None else 0.0)
    return (model_conf * 0.7) + (0.3 * (0.5*v + 0.5*h))

def compute_confidence(doc: Dict[str, Any]) -> Dict[str, Any]:
    amounts = doc.get("amounts", {})
    subtotal, tax, shipping, discount, total = [amounts.get(k) for k in ("subtotal","tax","shipping","discount","total")]
    expected = None
    if subtotal is not None:
        expected = (subtotal or 0) + (tax or 0) + (shipping or 0) - (discount or 0)
    totals_ok = approx_equal(expected, total) if expected is not None and total is not None else None

    issue = doc["invoice"].get("issue_date"); due = doc["invoice"].get("due_date")
    dates_ok = None
    try:
        dates_ok = (issue is None or due is None) or (issue <= due)
    except Exception:
        dates_ok = None

    currency_ok = doc["invoice"].get("currency") is not None

    doc.setdefault("audit", {}).setdefault("validation", {})
    doc["audit"]["validation"].update({
        "totals_ok": totals_ok if totals_ok is not None else False,
        "date_sane": dates_ok if dates_ok is not None else True,
        "currency_consistent": currency_ok
    })

    bf = doc["confidence"].get("by_field", {})
    bf_adj = {}
    bf_adj["amounts.total"] = field_adjusted_conf(bf.get("amounts.total",0), totals_ok, True)
    bf_adj["invoice.invoice_number"] = field_adjusted_conf(bf.get("invoice.invoice_number",0), True, True)
    bf_adj["invoice.issue_date"] = field_adjusted_conf(bf.get("invoice.issue_date",0), dates_ok, True)
    bf_adj["invoice.due_date"] = field_adjusted_conf(bf.get("invoice.due_date",0), dates_ok, True)
    bf_adj["invoice.currency"] = field_adjusted_conf(bf.get("invoice.currency",0), currency_ok, True)
    bf_adj["vendor.name"] = field_adjusted_conf(bf.get("vendor.name",0), True, True)
    bf_adj["vendor.vat_id"] = field_adjusted_conf(bf.get("vendor.vat_id",0), True, True)
    bf_adj["amounts.subtotal"] = field_adjusted_conf(bf.get("amounts.subtotal",0), totals_ok, True)
    bf_adj["amounts.tax"] = field_adjusted_conf(bf.get("amounts.tax",0), totals_ok, True)

    weights = {
        "amounts.total": 3, "invoice.invoice_number": 2, "invoice.issue_date": 2,
        "vendor.name": 2, "invoice.currency": 2,
        "vendor.vat_id": 1, "amounts.subtotal": 1, "amounts.tax": 1, "invoice.due_date": 1
    }
    s = 0.0; w = 0.0
    for k, v in bf_adj.items():
        s += v * weights.get(k, 1)
        w += weights.get(k, 1)
    overall = s / w if w else 0.0
    if totals_ok is False:
        overall = min(overall, 0.6)
    if not currency_ok:
        overall = min(overall, 0.7)
    doc["confidence"]["by_field"] = {k: round(v,4) for k,v in bf_adj.items()}
    doc["confidence"]["overall"] = round(overall,4)
    return doc
