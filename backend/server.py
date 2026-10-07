"""
High-Performance HTTP REST API & Static File Server.
Built using standard library http.server and ThreadingHTTPServer.
Runs reliably out of the box with zero third-party pip dependencies.
"""

import http.server
import json
import urllib.parse
import os
import mimetypes
from typing import Dict, Any

from .nlp.language_detector import LanguageDetector
from .nlp.retrieval import ExemplarRetriever
from .nlp.prompt_builder import PromptBuilder
from .nlp.generator import MultilingualGenerator
from .nlp.evaluator import PromptEvaluator
from .nlp.llm_client import LLMClient

# Initialize NLP Pipeline singletons
language_detector = LanguageDetector()
exemplar_retriever = ExemplarRetriever()
prompt_builder = PromptBuilder()
response_generator = MultilingualGenerator()
prompt_evaluator = PromptEvaluator()
llm_client = LLMClient()

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

class ChatbotRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS and caching headers
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def _send_json(self, status_code: int, data: Dict[str, Any]):
        response_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def _read_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return {}
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(body)
        except Exception:
            return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query_params = urllib.parse.parse_qs(parsed.query)

        # API Routes
        if path == "/api/health":
            self._send_json(200, {
                "status": "healthy",
                "title": "Low-resource and Multilingual Language Modeling via Prompt Engineering and ICL",
                "engine": "Native In-Context Learning + Optional LLM Pass-through",
                "languages_supported": len(language_detector.languages)
            })
            return

        elif path == "/api/languages":
            self._send_json(200, {
                "languages": language_detector.languages,
                "tiers": {
                    "high": [k for k, v in language_detector.languages.items() if v.get("tier") == "high"],
                    "medium": [k for k, v in language_detector.languages.items() if v.get("tier") == "medium"],
                    "low": [k for k, v in language_detector.languages.items() if v.get("tier") == "low"]
                }
            })
            return

        elif path == "/api/exemplars":
            lang_filter = query_params.get("lang", [None])[0]
            intent_filter = query_params.get("intent", [None])[0]
            
            exs = exemplar_retriever.exemplars
            if lang_filter:
                exs = [e for e in exs if e.get("language") == lang_filter]
            if intent_filter:
                exs = [e for e in exs if e.get("intent") == intent_filter]
                
            self._send_json(200, {"count": len(exs), "exemplars": exs})
            return

        elif path == "/api/policies":
            self._send_json(200, {"policies": response_generator.kb})
            return

        elif path == "/api/glossaries":
            self._send_json(200, {"glossaries": prompt_builder.glossaries})
            return

        # Serve static frontend files
        if path == "/" or path == "/index.html":
            file_path = os.path.join(FRONTEND_DIR, "index.html")
        else:
            rel_path = path.lstrip("/")
            file_path = os.path.join(FRONTEND_DIR, rel_path)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = "application/octet-stream"
            
            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_json(404, {"error": "Resource not found", "path": path})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path == "/api/detect-language":
            text = body.get("text", "")
            detected_lang, confidence = language_detector.detect(text)
            lang_info = language_detector.languages.get(detected_lang, {})
            self._send_json(200, {
                "detected_code": detected_lang,
                "name": lang_info.get("name", "Unknown"),
                "native_name": lang_info.get("native_name", ""),
                "tier": lang_info.get("tier", "low"),
                "confidence": confidence
            })
            return

        elif path == "/api/chat":
            user_msg = body.get("message", "").strip()
            if not user_msg:
                self._send_json(400, {"error": "Message cannot be empty"})
                return

            req_lang = body.get("language", "auto")
            strategy = body.get("strategy", "few_shot")
            k_shots = int(body.get("k_shots", 3))
            use_grounding = bool(body.get("grounding", True))

            # 1. Detect or validate language
            if req_lang == "auto" or not req_lang:
                target_lang, lang_conf = language_detector.detect(user_msg)
            else:
                target_lang = req_lang
                lang_conf = 1.0

            lang_info = language_detector.languages.get(target_lang, language_detector.languages.get("en", {}))

            # 2. Dynamic Demonstration Retrieval
            exemplars = exemplar_retriever.retrieve(
                query=user_msg,
                target_lang=target_lang,
                k=k_shots,
                strategy=strategy
            )

            # 3. Prompt Engineering & In-Context Prompt Synthesis
            prompt_payload = prompt_builder.build_prompt(
                query=user_msg,
                target_lang=target_lang,
                lang_info=lang_info,
                strategy=strategy,
                exemplars=exemplars,
                use_lexicon_grounding=use_grounding
            )

            # 4. Multilingual Response Generation
            gen_result = response_generator.generate_response(
                query=user_msg,
                target_lang=target_lang,
                prompt_data=prompt_payload,
                exemplars=exemplars
            )

            # 5. Check if external LLM should override response
            if llm_client.is_configured():
                external_resp = llm_client.call_llm(
                    assembled_prompt=prompt_payload["assembled_prompt"],
                    system_prompt=prompt_payload["system_prompt"]
                )
                if external_resp:
                    gen_result["response"] = external_resp
                    gen_result["model_source"] = f"External LLM ({llm_client.model})"
                else:
                    gen_result["model_source"] = "Native Multilingual ICL Engine"
            else:
                gen_result["model_source"] = "Native Multilingual ICL Engine"

            # Combine response with full prompt engineering metadata for the UI Inspector
            response_payload = {
                "user_message": user_msg,
                "response": gen_result["response"],
                "target_language": {
                    "code": target_lang,
                    "name": lang_info.get("name", target_lang),
                    "native_name": lang_info.get("native_name", ""),
                    "tier": lang_info.get("tier", "low"),
                    "flag": lang_info.get("flag", "🌐"),
                    "detection_confidence": lang_conf
                },
                "intent": gen_result["intent"],
                "intent_confidence": gen_result["intent_confidence"],
                "sentiment": gen_result["sentiment"],
                "sentiment_score": gen_result["sentiment_score"],
                "entities": gen_result["entities"],
                "cot_trace": gen_result["cot_trace"],
                "policy_applied": gen_result["policy_applied"],
                "latency_ms": gen_result["latency_ms"],
                "model_source": gen_result["model_source"],
                "prompt_inspection": prompt_payload
            }

            self._send_json(200, response_payload)
            return

        elif path == "/api/evaluate":
            selected_langs = body.get("languages", None)
            benchmark_results = prompt_evaluator.run_benchmark(selected_langs)
            self._send_json(200, benchmark_results)
            return

        else:
            self._send_json(404, {"error": "API route not found"})

def run_server(port: int = 8000, host: str = "0.0.0.0"):
    server_address = (host, port)
    httpd = http.server.ThreadingHTTPServer(server_address, ChatbotRequestHandler)
    print(f"================================================================================")
    print(f" Low-Resource & Multilingual NLP Customer Support Chatbot System")
    print(f" In-Context Learning (ICL) & Prompt Engineering Framework")
    print(f" Server running at: http://localhost:{port}")
    print(f" Static files served from: {FRONTEND_DIR}")
    print(f" Press Ctrl+C to stop the server.")
    print(f"================================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer shutting down gracefully.")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
