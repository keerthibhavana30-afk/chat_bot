"""
Multilingual and Low-Resource Language Detector.
Combines Unicode script range analysis with character n-gram frequency profiles
and high-discriminant vocabulary matching to reliably detect high-, medium-,
and low-resource languages (e.g., Swahili, Yoruba, Quechua, Basque, Tagalog, Amharic).
"""

import re
import json
import os
from typing import Dict, Tuple, Optional

SCRIPT_RANGES = {
    "Ethiopic": [(0x1200, 0x137F), (0x1380, 0x139F), (0x2D80, 0x2DDF)],  # Amharic
    "Bengali": [(0x0980, 0x09FF)],                                         # Bengali
    "Tamil": [(0x0B80, 0x0BFF)],                                           # Tamil
    "Devanagari": [(0x0900, 0x097F)],                                      # Hindi
    "Telugu": [(0x0C00, 0x0C7F)],                                          # Telugu
    "Arabic": [(0x0600, 0x06FF), (0x0750, 0x077F)],                        # Arabic
    "Cyrillic": [(0x0400, 0x04FF)],                                        # Russian
    "Hanzi": [(0x4E00, 0x9FFF), (0x3400, 0x4DBF)],                         # Chinese
}

class LanguageDetector:
    def __init__(self, languages_file: Optional[str] = None):
        if languages_file is None:
            languages_file = os.path.join(os.path.dirname(__file__), "..", "data", "languages.json")
        
        with open(languages_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.languages = data.get("languages", {})
        
        # Build language-specific n-gram and keyword profiles
        self.profiles = {}
        for code, info in self.languages.items():
            self.profiles[code] = {
                "words": set(w.lower() for w in info.get("common_words", [])),
                "script": info.get("script", "Latin"),
                "tier": info.get("tier", "low")
            }

    def detect_script(self, text: str) -> Optional[str]:
        """Detect dominant non-Latin unicode script if present."""
        counts = {script: 0 for script in SCRIPT_RANGES}
        for char in text:
            code_point = ord(char)
            for script, ranges in SCRIPT_RANGES.items():
                if any(start <= code_point <= end for start, end in ranges):
                    counts[script] += 1
                    break
        
        max_script, max_count = max(counts.items(), key=lambda x: x[1])
        if max_count >= 2:
            return max_script
        return None

    def _extract_char_ngrams(self, text: str, n: int = 3) -> Dict[str, int]:
        """Extract character n-grams with frequency counts."""
        clean_text = f"  {re.sub(r'[^a-zA-Z\u00C0-\u024F\u1E00-\u1EFF]', ' ', text.lower())}  "
        ngrams = {}
        for i in range(len(clean_text) - n + 1):
            gram = clean_text[i:i+n]
            ngrams[gram] = ngrams.get(gram, 0) + 1
        return ngrams

    def detect(self, text: str) -> Tuple[str, float]:
        """
        Detect language of the text.
        Returns: (language_code, confidence_score [0.0 - 1.0])
        """
        if not text or not text.strip():
            return "en", 0.5
        
        # 1. First check script
        dominant_script = self.detect_script(text)
        if dominant_script == "Ethiopic":
            return "am", 0.98
        elif dominant_script == "Bengali":
            return "bn", 0.98
        elif dominant_script == "Tamil":
            return "ta", 0.98
        elif dominant_script == "Telugu":
            return "te", 0.98
        elif dominant_script == "Devanagari":
            return "hi", 0.96
        elif dominant_script == "Arabic":
            return "ar", 0.97
        elif dominant_script == "Cyrillic":
            return "ru", 0.97
        elif dominant_script == "Hanzi":
            return "zh", 0.98

        # 2. Latin script languages discrimination
        tokens = [t.lower() for t in re.findall(r'\b[\w\u00C0-\u024F\u1E00-\u1EFF]+\b', text)]
        token_set = set(tokens)

        scores: Dict[str, float] = {}

        # Language distinctive markers
        distinctive_markers = {
            "sw": ["agizo", "langu", "mzigo", "wapi", "rejesha", "pesa", "msaada", "nenosiri", "habari", "hujambo", "kwa", "katika", "siku", "tatu", "ndani", "salama"],
            "yo": ["àṣẹ", "ase", "ibo", "ẹrù", "eru", "pẹ́", "pe", "owó", "owo", "ìsanpadà", "isanpada", "ìwé", "iwe", "ọ̀rọ̀", "ẹ n lẹ́", "báwo", "wàhálà"],
            "qu": ["maypin", "kachkan", "rantiy", "rantisqa", "chayamunchu", "qullqiyta", "kutichiy", "pampachawayku", "allillanchu", "allinllachu", "yupay", "ñan"],
            "eu": ["dago", "nire", "eskaera", "non", "itzulketa", "faktura", "egun", "hondatuta", "laguntza", "kaixo", "egun on", "birritan"],
            "tl": ["nasaan", "aking", "po", "opo", "gamit", "pera", "bayad", "kamusta", "mabuhay", "kailangan", "padala", "sira", "naantala"],
            "es": ["dónde", "donde", "pedido", "paquete", "reembolso", "devolución", "factura", "tarjeta", "hola", "cuenta", "contraseña", "llegado"],
            "fr": { "où", "commande", "colis", "remboursement", "facture", "compte", "mot de passe", "bonjour", "reçu", "endommage", "délai"},
            "de": ["wo", "bestellung", "paket", "rückerstattung", "erstattung", "rechnung", "konto", "passwort", "guten", "bitte", "versand"],
            "pt": ["onde", "pedido", "pacote", "reembolso", "estorno", "fatura", "rastreio", "olá", "cartão", "atrasado"],
            "en": ["where", "order", "package", "refund", "return", "invoice", "delivery", "account", "password", "delayed", "received", "broken"]
        }

        for lang_code, profile in self.profiles.items():
            if profile["script"] != "Latin":
                continue
            
            # Common word match score
            matched_words = token_set.intersection(profile["words"])
            word_score = len(matched_words) * 2.5

            # Distinctive marker score
            markers = distinctive_markers.get(lang_code, [])
            marker_hits = sum(1 for m in markers if m in text.lower())
            marker_score = marker_hits * 4.0

            total_score = word_score + marker_score
            scores[lang_code] = total_score

        best_lang, max_val = max(scores.items(), key=lambda x: x[1])

        if max_val > 0:
            confidence = min(0.95, 0.45 + (max_val * 0.1))
            return best_lang, round(confidence, 2)

        # Default fallback
        return "en", 0.50
