"""
Dynamic In-Context Exemplar Retrieval Engine.
Implements subword character n-gram TF-IDF and BM25-style lexical scoring
to retrieve the most relevant demonstrations for In-Context Learning across
both high-resource and low-resource multilingual queries.
"""

import re
import json
import math
import os
from typing import List, Dict, Any, Optional

class ExemplarRetriever:
    def __init__(self, exemplars_file: Optional[str] = None, exemplars_list: Optional[List[Dict[str, Any]]] = None):
        if exemplars_list is not None:
            self.exemplars = list(exemplars_list)
        else:
            if exemplars_file is None:
                exemplars_file = os.path.join(os.path.dirname(__file__), "..", "data", "exemplars.json")
            with open(exemplars_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.exemplars = data.get("exemplars", [])
            
        self._build_index()

    def update_exemplars(self, new_exemplars: List[Dict[str, Any]]):
        """Update exemplar store and rebuild BM25/TF-IDF indexes."""
        self.exemplars = list(new_exemplars)
        self._build_index()

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize into both word tokens and character n-grams.
        This provides subword robustness for low-resource agglutinative & inflected languages.
        """
        clean = text.lower()
        words = re.findall(r'\b\w+\b', clean)
        tokens = list(words)
        
        # Add character trigrams for words with len >= 3
        for w in words:
            if len(w) >= 3:
                for i in range(len(w) - 2):
                    tokens.append(f"_{w[i:i+3]}_")
        return tokens

    def _build_index(self):
        """Build term frequencies and document frequencies for BM25/TF-IDF."""
        self.doc_tokens = []
        self.doc_lens = []
        self.df = {}
        self.total_docs = len(self.exemplars)

        for ex in self.exemplars:
            # Combine user query, intent, and thought for rich retrieval index
            indexed_text = f"{ex['user_query']} {ex['intent']} {ex.get('thought', '')}"
            tokens = self._tokenize(indexed_text)
            self.doc_tokens.append(tokens)
            self.doc_lens.append(len(tokens))

            seen_in_doc = set(tokens)
            for token in seen_in_doc:
                self.df[token] = self.df.get(token, 0) + 1

        self.avg_doc_len = sum(self.doc_lens) / max(1, self.total_docs)

    def _calculate_bm25_score(self, query_tokens: List[str], doc_idx: int, k1: float = 1.5, b: float = 0.75) -> float:
        """Compute BM25 score between query tokens and document index."""
        doc = self.doc_tokens[doc_idx]
        doc_len = self.doc_lens[doc_idx]
        score = 0.0

        doc_tf = {}
        for t in doc:
            doc_tf[t] = doc_tf.get(t, 0) + 1

        for qt in query_tokens:
            if qt not in doc_tf:
                continue
            tf = doc_tf[qt]
            df_val = self.df.get(qt, 1)
            # Standard smoothed IDF
            idf = math.log((self.total_docs - df_val + 0.5) / (df_val + 0.5) + 1.0)
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_len / max(1, self.avg_doc_len)))
            score += idf * (numerator / max(1e-5, denominator))

        return score

    def retrieve(
        self,
        query: str,
        target_lang: str = "en",
        k: int = 3,
        strategy: str = "few_shot"
    ) -> List[Dict[str, Any]]:
        """
        Dynamically retrieve top-k exemplars.
        
        Strategies:
        - 'few_shot' / 'chain_of_thought': Prefer target language; fallback to cross-lingual if scarce.
        - 'cross_lingual_icl': Explicitly select high-resource (English) exemplars for target query reasoning.
        - 'pivot_grounding': Prioritize target language or cross-lingual with bilingual anchors.
        - 'zero_shot': Returns empty list.
        """
        if k <= 0 or strategy == "zero_shot":
            return []

        q_tokens = self._tokenize(query)
        scored_exemplars = []

        for idx, ex in enumerate(self.exemplars):
            ex_lang = ex.get("language", "en")
            
            # Apply strategy-specific filtering / weighting
            lang_multiplier = 1.0
            if strategy == "cross_lingual_icl":
                # For cross-lingual ICL, high-resource (en) demonstrations act as the cognitive pivot
                if ex_lang == "en":
                    lang_multiplier = 1.4
                else:
                    lang_multiplier = 0.8
            else:
                # Direct few-shot / CoT: favor native language if available
                if ex_lang == target_lang:
                    lang_multiplier = 2.0
                elif ex_lang == "en":
                    lang_multiplier = 1.0
                else:
                    lang_multiplier = 0.5

            base_score = self._calculate_bm25_score(q_tokens, idx)
            
            # Detect exact entity matching (e.g. #ORD-, #INV-)
            if "#ORD-" in query and "#ORD-" in ex["user_query"]:
                base_score += 3.0
            if "#INV-" in query and "#INV-" in ex["user_query"]:
                base_score += 3.0

            final_score = base_score * lang_multiplier
            scored_exemplars.append((final_score, ex))

        # Sort descending by score
        scored_exemplars.sort(key=lambda x: x[0], reverse=True)

        # Select top k with normalized similarity score (0.0 - 1.0)
        max_score = scored_exemplars[0][0] if scored_exemplars and scored_exemplars[0][0] > 0 else 1.0
        results = []
        for score, ex in scored_exemplars[:k]:
            normalized_score = round(min(0.99, max(0.40, score / max(1e-5, max_score))), 3)
            ex_copy = dict(ex)
            ex_copy["similarity_score"] = normalized_score
            results.append(ex_copy)

        return results
