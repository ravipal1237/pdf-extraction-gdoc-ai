# Invoice Extraction Prototype (DocAI + Streamlit)

This repository contains a dynamic, enterprise-minded prototype that uses **Google Document AI (Invoice Processor)** for parsing invoices and a post-processing layer to normalize, validate, and compute confidence scores. Nothing is hardcoded — you must supply GCP credentials and processor information via environment variables.

## What's included
- `app.py` — Streamlit app (UI) that uploads and processes invoices, shows confidence and validations, and allows JSON download.
- `processor.py` — thin wrapper around Google Document AI (dynamic, picks regional endpoint based on DOCAI_LOCATION)
- `postprocess.py` — normalization, parsing, and confidence calculations (locale-aware)
- `requirements.txt` — Python dependencies
- `README.md` — this file

## Setup (local)

1. **Create a Google Cloud project** and enable the Document AI API.
2. **Create a Document AI Processor** (type: Invoice / Procurement) following [Google's guide].
   - Note the **processor ID** and **location** (e.g., `us`).
3. **Create a service account** with the `Document AI API` roles (Document AI Admin or Document AI Editor) and download the JSON key.
4. **Set environment variables** locally:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export DOCAI_PROJECT_ID="your-gcp-project"
export DOCAI_PROCESSOR_ID="your-invoice-processor-id"
export DOCAI_LOCATION="us"  # or eu, asia, etc.
```
5. Install dependencies:
```bash
python -m pip install -r requirements.txt
```
6. Run the app:
```bash
streamlit run app.py
```
7. Upload varied invoices (multi-page, multi-language). Use the locale hint (e.g., `de_DE`) when you expect European number formats.

## Tips to improve Document AI accuracy
- Use the **Invoice Processor** (pretrained) rather than generic OCR for invoices.
- Create a **custom processor** / train a specialized processor using labeled examples from your vendor set for higher accuracy on specific layouts.
- Provide **locale and language hints** in the UI to improve number/date parsing. (The processor itself may detect languages but locale helps post-processing.)
- Preprocess PDFs: deskew, enhance contrast, split very long PDFs into page-samples for faster processing.
- Use **HITL**: display low-confidence fields for human correction and feed corrections back into training data.
- For addresses, add libpostal or a dedicated address normalization pipeline when you need postal-grade parsing.
- Monitor model errors and build vendor-specific templates or rules for frequent suppliers.
- For sensitive data, ensure processor location/data residency matches legal requirements (use EU processors for EU data if needed).

## Notes & next steps
- This prototype intentionally avoids hardcoding IDs/regions — set them via environment variables.
- Add persistence (Cloud SQL, Firestore) and human review UI for enterprise usage.
- Consider Cloud Run + Pub/Sub pipeline for batch ingestion and autoscaling.


----------

# 2. Create virtual environment (recommended: Python 3.10+)
python3 -m venv venv

# 3. Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# 4. Upgrade pip inside venv
pip install --upgrade pip

# 5. Install dependencies
pip install -r requirements.txt

# 6. Export env vars for Document AI
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export DOCAI_PROJECT_ID="your-gcp-project-id"
export DOCAI_PROCESSOR_ID="your-processor-id"
export DOCAI_LOCATION="us"   # or eu, asia

# 7. Run streamlit app
streamlit run app.py
