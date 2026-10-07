"""
Prompt Engineering and In-Context Learning (ICL) Synthesizer.
Constructs structured, theoretically grounded multilingual prompts for customer support.
Supports 5 NLP paradigms:
1. Direct Few-Shot (Monolingual ICL)
2. Cross-Lingual In-Context Learning (X-ICL)
3. Multilingual Chain-of-Thought (X-CoT)
4. Pivot Grounding with Low-Resource Bilingual Glossaries
5. Zero-Shot Baseline
"""

import json
import os
from typing import List, Dict, Any, Optional

STRATEGY_DESCRIPTIONS = {
    "few_shot": "Monolingual Few-Shot ICL: Leverages target-language in-context demonstrations to guide format, domain tone, and entity binding.",
    "cross_lingual_icl": "Cross-Lingual In-Context Learning (X-ICL): Uses high-resource (English) reasoning demonstrations as a cognitive scaffold while instructing the model to generate the final resolution in the low-resource target language.",
    "chain_of_thought": "Multilingual Chain-of-Thought (X-CoT): Enforces step-by-step cognitive decomposition (Language ID -> Intent Classification -> Entity Slot Filling -> Policy Resolution -> Polite Target Generation).",
    "pivot_grounding": "Pivot-Based Bilingual Lexicon Grounding: Injects low-resource domain dictionary terms directly into context to constrain hallucinations and preserve correct e-commerce nomenclature.",
    "zero_shot": "Zero-Shot Baseline: Direct instruction without exemplar demonstrations, providing a benchmark comparison for in-context learning gains."
}

class PromptBuilder:
    def __init__(self, glossaries_file: Optional[str] = None):
        if glossaries_file is None:
            glossaries_file = os.path.join(os.path.dirname(__file__), "..", "data", "glossaries.json")
        
        with open(glossaries_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.glossaries = data.get("glossaries", {})

    def build_prompt(
        self,
        query: str,
        target_lang: str,
        lang_info: Dict[str, Any],
        strategy: str = "few_shot",
        exemplars: Optional[List[Dict[str, Any]]] = None,
        use_lexicon_grounding: bool = True
    ) -> Dict[str, Any]:
        """
        Assemble the complete multilingual prompt payload.
        """
        if exemplars is None:
            exemplars = []

        lang_name = lang_info.get("name", "Target Language")
        native_name = lang_info.get("native_name", lang_name)
        tier = lang_info.get("tier", "low")

        # 1. Base System Instruction
        system_lines = [
            "### ROLE & OBJECTIVE",
            f"You are an enterprise AI Customer Support Specialist fluent in {lang_name} ({native_name}).",
            "Your mission is to resolve customer inquiries accurately, empathetically, and strictly adhering to store policies.",
            "",
            "### CORE OPERATIONAL CONSTRAINTS",
            f"1. LANGUAGE STRICTNESS: You MUST generate your final resolution strictly in {lang_name} ({native_name}). Do not revert to English unless quoting specific tracking codes or order IDs.",
            "2. POLICY COMPLIANCE: Adhere to standard 30-day refund guarantee, 24-48h tracking updates, and 1-year hardware warranty.",
            "3. ACTIONABLE RESOLUTION: Provide specific next steps, status confirmations, or escalation numbers (#ESC-XXXX).",
            "4. TONE: Professional, polite, helpful, and culturally respectful."
        ]

        # 2. Strategy Specific Instructions
        if strategy == "chain_of_thought":
            system_lines.extend([
                "",
                "### REASONING PARADIGM (Chain-of-Thought)",
                "Before providing the final customer response, decompose your reasoning step-by-step:",
                "Step 1 [Language Identification]: Identify customer dialect and script.",
                "Step 2 [Intent & Sentiment]: Classify core intent and customer emotion.",
                "Step 3 [Entity Extraction]: Extract Order ID (#ORD-), Invoice ID (#INV-), or product references.",
                "Step 4 [Policy Verification]: Check refund/shipping/security SLA rules.",
                f"Step 5 [Response Synthesis]: Synthesize courteous, complete resolution in {lang_name}."
            ])
        elif strategy == "cross_lingual_icl":
            system_lines.extend([
                "",
                "### CROSS-LINGUAL TRANSFER INSTRUCTIONS",
                "Learn the conversational reasoning structure from the English demonstrations below, but synthesize your entire final output naturally and natively in the target language."
            ])

        # 3. Lexical Grounding Block (Domain Dictionary)
        grounding_block = ""
        glossary_items = {}
        if (strategy == "pivot_grounding" or use_lexicon_grounding) and target_lang in self.glossaries:
            terms = self.glossaries[target_lang].get("terms", {})
            glossary_items = terms
            grounding_lines = [
                "",
                f"### DOMAIN BILINGUAL GLOSSARY ({lang_name} Grounding)",
                "To ensure exact terminology and prevent lexical drift, utilize the following verified domain vocabulary:"
            ]
            for en_term, target_term in terms.items():
                grounding_lines.append(f"- \"{en_term}\" -> {target_term}")
            grounding_block = "\n".join(grounding_lines)
            system_lines.append(grounding_block)

        system_prompt = "\n".join(system_lines)

        # 4. In-Context Demonstrations Block
        demonstrations_block = ""
        if strategy != "zero_shot" and exemplars:
            demo_lines = ["\n### IN-CONTEXT DEMONSTRATIONS (Few-Shot Exemplars)"]
            for i, ex in enumerate(exemplars, 1):
                demo_lines.append(f"\n--- Exemplar {i} [Language: {ex.get('language')}, Intent: {ex.get('intent')}] ---")
                demo_lines.append(f"Customer: {ex.get('user_query')}")
                
                # If Chain-of-Thought is active, include the reasoning trace
                if strategy == "chain_of_thought" or "thought" in ex:
                    demo_lines.append(f"Thought: {ex.get('thought', 'Reasoning step executed.')}")
                
                demo_lines.append(f"Support Agent: {ex.get('bot_response')}")
            demonstrations_block = "\n".join(demo_lines)

        # 5. User Turn
        user_turn_lines = [
            "\n### CURRENT CUSTOMER QUERY",
            f"Customer ({lang_name}): {query}"
        ]
        if strategy == "chain_of_thought":
            user_turn_lines.append(f"Support Agent ({lang_name}, provide Thought breakdown followed by Final Response):")
        else:
            user_turn_lines.append(f"Support Agent ({lang_name}):")
        
        user_turn = "\n".join(user_turn_lines)

        # Full prompt assembly
        assembled_prompt = f"{system_prompt}\n{demonstrations_block}\n{user_turn}"

        # Estimate tokens (approx. 4 chars per token for Latin, ~1-2 chars for Non-Latin scripts)
        char_count = len(assembled_prompt)
        estimated_tokens = max(10, int(char_count / 3.2))

        return {
            "strategy": strategy,
            "strategy_description": STRATEGY_DESCRIPTIONS.get(strategy, ""),
            "target_language": target_lang,
            "language_name": lang_name,
            "language_tier": tier,
            "system_prompt": system_prompt,
            "grounding_block": grounding_block,
            "glossary_count": len(glossary_items),
            "glossary_sample": list(glossary_items.items())[:6] if glossary_items else [],
            "demonstrations_block": demonstrations_block,
            "exemplar_count": len(exemplars),
            "exemplars_used": [
                {
                    "id": ex.get("id"),
                    "language": ex.get("language"),
                    "intent": ex.get("intent"),
                    "similarity_score": ex.get("similarity_score", 0.0),
                    "user_query": ex.get("user_query")
                }
                for ex in exemplars
            ],
            "user_turn": user_turn,
            "assembled_prompt": assembled_prompt,
            "token_estimate": estimated_tokens
        }
