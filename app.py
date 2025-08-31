"""
Streamlit Invoice Extraction Prototype
"""
from pathlib import Path
import os
import json
import hashlib
import time
from typing import List, Optional

import streamlit as st
from processor import DocAIProcessor, DocAIError
from postprocess import normalize_docai_document, compute_confidence

# UI ---------------------------------------------------------------------
st.set_page_config(page_title="Invoice Extractor (DocAI) - Prototype", layout="wide")
st.title("📄 Invoice Extraction Demo(Google Document AI)")

with st.sidebar:
    st.header("⚙️ Settings (env-driven)")
    st.write("Make sure you exported required environment variables before starting the app.")
    st.markdown("""
    **Required env vars**:
    - `GOOGLE_APPLICATION_CREDENTIALS` -> service account JSON path
    - `DOCAI_PROJECT_ID` -> Document AI project
    - `DOCAI_PROCESSOR_ID` -> Invoice processor id
    - `DOCAI_LOCATION` -> processor location (e.g., `us`, `eu`)
    """)
    st.markdown("Optional: locale hint (eg `en_US`) and language codes (eg `en,de,fr`)")

    locale_hint = st.text_input("Locale hint (optional, e.g., en_US)", value="")
    lang_codes = st.text_input("Language codes (comma separated, e.g., en,de,fr)", value="")

uploaded = st.file_uploader("Upload PDF/image invoice", type=["pdf","png","jpg","jpeg","tiff"])
run_btn = st.button("Process")

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def try_get_env(name: str) -> Optional[str]:
    return os.environ.get(name)

if run_btn and uploaded:
    # Load dynamic envs (no hardcoding)
    project_id = try_get_env("DOCAI_PROJECT_ID")
    processor_id = try_get_env("DOCAI_PROCESSOR_ID")
    location = try_get_env("DOCAI_LOCATION",) or try_get_env("DOCAI_PROCESSOR_LOCATION")
    cred = try_get_env("GOOGLE_APPLICATION_CREDENTIALS")
    if not all([project_id, processor_id, location, cred]):
        st.error("Missing one or more required environment variables. See sidebar for names.")
    else:
        content = uploaded.read()
        mime = uploaded.type or "application/pdf"
        st.info(f"File: **{uploaded.name}** — {len(content)} bytes — {mime}")
        with st.spinner("Calling Google Document AI…"):
            try:
                client = DocAIProcessor(project_id=project_id, location=location, processor_id=processor_id)
                doc, latency_ms = client.process_document(content, mime_type=mime)
            except DocAIError as e:
                st.error(f"Document AI error: {e}")
                st.stop()
            except Exception as e:
                st.error(f"Unexpected error calling Document AI: {e}")
                st.stop()

        # Normalize & compute confidence
        normalized = normalize_docai_document(doc, locale_hint or None, [c.strip() for c in lang_codes.split(",") if c.strip()])
        normalized["document_id"] = f"sha256:{sha256_bytes(content)}"
        normalized.setdefault("source", {})["file_name"] = uploaded.name
        normalized["source"]["pages"] = len(getattr(doc, "pages", []) or [])
        normalized["source"]["mime_type"] = mime
        normalized.setdefault("audit", {})["latency_ms"] = latency_ms
        normalized = compute_confidence(normalized)

        # Display top metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Overall confidence", f"{normalized['confidence']['overall']:.2f}")
        c2.metric("Pages", normalized["source"]["pages"])
        c3.metric("Latency (ms)", normalized["audit"]["latency_ms"])

        # Header & parties
        st.subheader("Header")
        header_cols = st.columns(4)
        inv = normalized["invoice"]
        header_cols[0].write(f"**Invoice #**: {inv.get('invoice_number')}")
        header_cols[1].write(f"**Issue date**: {inv.get('issue_date')}")
        header_cols[2].write(f"**Due date**: {inv.get('due_date')}")
        header_cols[3].write(f"**Currency**: {inv.get('currency')}")

        st.subheader("Parties")
        p1, p2, p3 = st.columns(3)
        v = normalized["vendor"]
        p1.write(f"**Vendor**: {v.get('name')}\n\nVAT: {v.get('vat_id')}\n\n{(v.get('address') or {}).get('raw')}")
        b = normalized["bill_to"]
        p2.write(f"**Bill To**: {b.get('name')}\n\n{(b.get('address') or {}).get('raw')}")
        s2 = normalized["ship_to"]
        p3.write(f"**Ship To**: {s2.get('name')}\n\n{(s2.get('address') or {}).get('raw')}")

        st.subheader("Amounts")
        a = normalized["amounts"]
        a_cols = st.columns(6)
        keys = ["subtotal","tax","shipping","discount","total","amount_due"]
        for i,k in enumerate(keys):
            a_cols[i].metric(k.replace("_"," ").title(), str(a.get(k)))

        st.subheader("Line items")
        import pandas as pd
        df = pd.DataFrame(normalized.get("line_items", []))
        st.dataframe(df, use_container_width=True)

        st.subheader("Confidence by field")
        cf = pd.DataFrame([{"field":k,"confidence":v} for k,v in normalized["confidence"]["by_field"].items()])
        st.dataframe(cf.sort_values("confidence", ascending=False), use_container_width=True)

        st.subheader("Validation")
        st.json(normalized.get("audit", {}).get("validation", {}))

        # Download JSON
        json_bytes = json.dumps(normalized, indent=2, ensure_ascii=False).encode("utf-8")
        st.download_button("Download extracted JSON", data=json_bytes, file_name=f"{Path(uploaded.name).stem}.json", mime="application/json")

        with st.expander("Raw Document AI output (debug)"):
            # WARNING: large output could be heavy
            st.json(json.loads(doc.to_json() if hasattr(doc,"to_json") else doc.__class__.to_json(doc)))
