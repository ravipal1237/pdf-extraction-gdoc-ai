# Invoice Extraction Prototype (DocAI + Streamlit)


## Setup (local)

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
