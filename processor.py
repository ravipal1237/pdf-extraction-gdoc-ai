"""
DocAI processor wrapper (dynamic, no hardcoded secrets)
- Uses google-cloud-documentai v1
- Exposes DocAIProcessor.process_document(file_bytes, mime_type)
"""
import os
from google.cloud import documentai_v1 as documentai
from google.api_core.client_options import ClientOptions

class DocAIError(Exception):
    pass

class DocAIProcessor:
    def __init__(self, project_id: str, location: str, processor_id: str):
        # Expect environment variable GOOGLE_APPLICATION_CREDENTIALS to be set for auth.
        self.project_id = project_id
        self.location = location
        self.processor_id = processor_id
        # Client options to choose regional endpoint if needed
        api_endpoint = f"{location}-documentai.googleapis.com" if location else None
        client_opts = ClientOptions(api_endpoint=api_endpoint) if api_endpoint else None
        try:
            self.client = documentai.DocumentProcessorServiceClient(client_options=client_opts)
        except Exception as e:
            raise DocAIError(f"Failed to create Document AI client: {e}")

    def _processor_name(self):
        return self.client.processor_path(self.project_id, self.location, self.processor_id)

    def process_document(self, file_bytes: bytes, mime_type: str = "application/pdf"):
        raw_doc = documentai.RawDocument(content=file_bytes, mime_type=mime_type)
        name = self._processor_name()
        request = documentai.ProcessRequest(name=name, raw_document=raw_doc)
        try:
            result = self.client.process_document(request=request)
            # result.document is a google.cloud.documentai.Document
            return result.document, int(getattr(result, 'response', None) and 0 or 0) or 0  # latency placeholder
        except Exception as e:
            raise DocAIError(str(e))
