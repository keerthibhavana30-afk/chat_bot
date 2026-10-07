"""
Unit and Integration Tests for NLP Components:
- LanguageDetector
- ExemplarRetriever
- PromptBuilder
- MultilingualGenerator
- PromptEvaluator
"""

import unittest
import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.nlp.language_detector import LanguageDetector
from backend.nlp.retrieval import ExemplarRetriever
from backend.nlp.prompt_builder import PromptBuilder
from backend.nlp.generator import MultilingualGenerator
from backend.nlp.evaluator import PromptEvaluator

class TestMultilingualNLP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = LanguageDetector()
        cls.retriever = ExemplarRetriever()
        cls.builder = PromptBuilder()
        cls.generator = MultilingualGenerator()
        cls.evaluator = PromptEvaluator()

    def test_language_detection_high_resource(self):
        """Test detection of English, Spanish, and French."""
        lang, conf = self.detector.detect("Where is my order #ORD-12345? It is late.")
        self.assertEqual(lang, "en")
        self.assertGreaterEqual(conf, 0.5)

        lang_es, _ = self.detector.detect("¿Dónde está mi pedido y mi reembolso?")
        self.assertEqual(lang_es, "es")

    def test_language_detection_low_resource(self):
        """Test detection of low-resource languages: Swahili, Yoruba, Quechua, Basque, Tagalog, Amharic, Bengali, Tamil."""
        # Swahili
        lang_sw, _ = self.detector.detect("Agizo langu liko wapi? Nimepokea mzigo uliochelewa.")
        self.assertEqual(lang_sw, "sw")

        # Yoruba
        lang_yo, _ = self.detector.detect("Ibo ni àṣẹ mi wà? Mo fẹ́ da nǹkan padà nítorí ó bàjẹ́.")
        self.assertEqual(lang_yo, "yo")

        # Quechua
        lang_qu, _ = self.detector.detect("Maypin kachkan rantiy apachisqa? Qullqiyta kutichipuway.")
        self.assertEqual(lang_qu, "qu")

        # Basque
        lang_eu, _ = self.detector.detect("Non dago nire eskaera? Diru-itzulketa nahi dut.")
        self.assertEqual(lang_eu, "eu")

        # Tagalog
        lang_tl, _ = self.detector.detect("Nasaan na po ang aking order na gamit?")
        self.assertEqual(lang_tl, "tl")

        # Bengali (Script-based)
        lang_bn, _ = self.detector.detect("আমার অর্ডার কোথায়? টাকা ফেরত চাই।")
        self.assertEqual(lang_bn, "bn")

        # Tamil (Script-based)
        lang_ta, _ = self.detector.detect("எனது ஆர்டர் எங்கே உள்ளது? உதவி தேவை.")
        self.assertEqual(lang_ta, "ta")

        # Amharic (Script-based)
        lang_am, _ = self.detector.detect("የትእዛዝ ቁጥሬ የት ደረሰ? እቃው ዘግይቷል።")
        self.assertEqual(lang_am, "am")

        # Telugu (Script-based)
        lang_te, _ = self.detector.detect("నా ఆర్డర్ #ORD-88312 ఎక్కడ ఉంది? ఆలస్యమైంది.")
        self.assertEqual(lang_te, "te")

    def test_exemplar_retrieval(self):
        """Test dynamic in-context demonstration retrieval."""
        results = self.retriever.retrieve(
            query="Agizo langu #ORD-99120 liko wapi?",
            target_lang="sw",
            k=2,
            strategy="few_shot"
        )
        self.assertGreater(len(results), 0)
        self.assertTrue(any(ex["language"] == "sw" for ex in results))
        self.assertIn("similarity_score", results[0])

    def test_prompt_builder_strategies(self):
        """Test prompt construction across all 5 paradigms."""
        lang_info = self.detector.languages["sw"]
        exemplars = self.retriever.retrieve("Agizo langu wapi?", target_lang="sw", k=2)

        for strat in ["few_shot", "cross_lingual_icl", "chain_of_thought", "pivot_grounding", "zero_shot"]:
            payload = self.builder.build_prompt(
                query="Agizo langu #ORD-12345 wapi?",
                target_lang="sw",
                lang_info=lang_info,
                strategy=strat,
                exemplars=exemplars,
                use_lexicon_grounding=True
            )
            self.assertIn("assembled_prompt", payload)
            self.assertIn("system_prompt", payload)
            if strat == "zero_shot":
                self.assertEqual(payload["demonstrations_block"], "")
            elif strat == "pivot_grounding":
                self.assertIn("BILINGUAL GLOSSARY", payload["assembled_prompt"])

    def test_entity_extraction(self):
        """Test extraction of order IDs, invoice IDs, and emails."""
        entities = self.generator.extract_entities("Where is #ORD-44912 from support@company.com? Invoice was #INV-99210")
        self.assertEqual(entities.get("order_id"), "#ORD-44912")
        self.assertEqual(entities.get("invoice_id"), "#INV-99210")
        self.assertEqual(entities.get("email"), "support@company.com")

    def test_response_generation_and_cot(self):
        """Test end-to-end response generation and Chain-of-Thought trace."""
        prompt_payload = self.builder.build_prompt(
            query="Where is my order #ORD-11223?",
            target_lang="en",
            lang_info=self.detector.languages["en"],
            strategy="chain_of_thought"
        )
        res = self.generator.generate_response(
            query="Where is my order #ORD-11223?",
            target_lang="en",
            prompt_data=prompt_payload
        )
        self.assertEqual(res["intent"], "order_tracking")
        self.assertIn("#ORD-11223", res["response"])
        self.assertIn("cot_trace", res)
        self.assertEqual(len(res["cot_trace"]), 5)

    def test_evaluation_benchmark(self):
        """Test quick execution of evaluation benchmark."""
        results = self.evaluator.run_benchmark(selected_languages=["sw", "yo"])
        self.assertIn("summary", results)
        self.assertIn("few_shot", results["summary"])
        self.assertIn("zero_shot", results["summary"])
        self.assertGreater(results["summary"]["few_shot"]["intent_accuracy"], 0)

    def test_telugu_support(self):
        """Test Telugu prompt construction and generation."""
        te_info = self.detector.languages["te"]
        exemplars = self.retriever.retrieve("నా ఆర్డర్ ఎక్కడ ఉంది?", target_lang="te", k=2)
        prompt_payload = self.builder.build_prompt(
            query="నా ఆర్డర్ #ORD-88312 ఎక్కడ ఉంది?",
            target_lang="te",
            lang_info=te_info,
            strategy="chain_of_thought",
            exemplars=exemplars,
            use_lexicon_grounding=True
        )
        res = self.generator.generate_response(
            query="నా ఆర్డర్ #ORD-88312 ఎక్కడ ఉంది?",
            target_lang="te",
            prompt_data=prompt_payload,
            exemplars=exemplars
        )
        self.assertEqual(res["intent"], "order_tracking")
        self.assertIn("#ORD-88312", res["response"])
        self.assertIn("రవాణాలో ఉంది", res["response"])

if __name__ == "__main__":
    unittest.main()
