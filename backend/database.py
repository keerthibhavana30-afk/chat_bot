"""
MongoDB Backend Storage & Repository Layer.
Provides high-performance persistence for:
1. Chat conversations & metadata (language, intent, sentiment, CoT trace, latency).
2. Dynamic Few-Shot In-Context Learning Exemplars.
3. User feedback & analytics.

Includes automatic fallback to in-memory storage if MongoDB is not reachable,
ensuring zero downtime and resilience across environments.
"""

import os
import datetime
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ChatbotDatabase")

# Try importing pymongo
try:
    import pymongo
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False


def _load_env_file(filepath: str):
    """Simple .env reader without requiring external dependencies."""
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        logger.warning(f"Error loading .env file: {e}")


# Load root .env if present
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_load_env_file(os.path.join(ROOT_DIR, ".env"))


class MongoDatabaseManager:
    """
    Manages MongoDB connections, collection operations, exemplar caching,
    and automatic fallback to memory if MongoDB is offline.
    """

    def __init__(self, uri: Optional[str] = None, db_name: Optional[str] = None):
        self.uri = uri or os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        self.db_name = db_name or os.environ.get("MONGODB_DB_NAME", "customersupport_chatbot")
        self.client: Optional[Any] = None
        self.db: Optional[Any] = None
        self.connected = False
        self.last_error: Optional[str] = None

        # Fallback In-Memory storage
        self._memory_conversations: List[Dict[str, Any]] = []
        self._memory_exemplars: List[Dict[str, Any]] = []
        self._memory_feedback: List[Dict[str, Any]] = []

        # Attempt connection
        self.connect()

    def connect(self) -> bool:
        """Attempts to connect to MongoDB server."""
        if not PYMONGO_AVAILABLE:
            self.connected = False
            self.last_error = "pymongo package is not installed."
            return False

        try:
            # 2.5 second timeout so app startup is never blocked
            self.client = pymongo.MongoClient(
                self.uri,
                serverSelectionTimeoutMS=2500,
                connectTimeoutMS=2500
            )
            # Ping database to verify connection
            self.client.admin.command("ping")
            self.db = self.client[self.db_name]
            self.connected = True
            self.last_error = None
            print(f"[MongoDB] Successfully connected to database: {self.db_name}")

            # Create helpful indexes
            try:
                self.db["conversations"].create_index([("timestamp", pymongo.DESCENDING)])
                self.db["conversations"].create_index([("session_id", pymongo.ASCENDING)])
                self.db["conversations"].create_index([("language_code", pymongo.ASCENDING)])
                self.db["exemplars"].create_index([("language", pymongo.ASCENDING)])
                self.db["exemplars"].create_index([("intent", pymongo.ASCENDING)])
            except Exception as idx_err:
                logger.warning(f"Index creation notice: {idx_err}")

            return True
        except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
            if self.client:
                try:
                    self.client.close()
                except Exception:
                    pass
            self.connected = False
            self.client = None
            self.db = None
            self.last_error = str(e)
            print(f"[MongoDB] Offline or unreachable ({e}). Running in resilient Local/In-Memory fallback mode.")
            return False

    def close(self):
        """Safely close active database connections."""
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
            self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    # -------------------------------------------------------------
    # Exemplar Operations
    # -------------------------------------------------------------
    def seed_exemplars(self, initial_exemplars: List[Dict[str, Any]]):
        """Seed the database with default exemplars if not present."""
        self._memory_exemplars = list(initial_exemplars)
        if not self.connected or self.db is None:
            return

        try:
            coll = self.db["exemplars"]
            if coll.count_documents({}) == 0 and initial_exemplars:
                # Insert all exemplars with id field
                records = []
                for ex in initial_exemplars:
                    rec = dict(ex)
                    rec["_id"] = ex.get("id") or f"ex_{len(records)+1}"
                    records.append(rec)
                coll.insert_many(records)
                print(f"[MongoDB] Seeded {len(records)} exemplars into MongoDB collection 'exemplars'.")
        except Exception as e:
            logger.error(f"[MongoDB] Error seeding exemplars: {e}")

    def get_exemplars(self, lang: Optional[str] = None, intent: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve exemplars filtered by language and/or intent."""
        if self.connected and self.db is not None:
            try:
                query = {}
                if lang:
                    query["language"] = lang
                if intent:
                    query["intent"] = intent

                cursor = self.db["exemplars"].find(query)
                results = []
                for doc in cursor:
                    doc_id = str(doc.pop("_id", ""))
                    doc["id"] = doc.get("id") or doc_id
                    results.append(doc)
                if results:
                    return results
            except Exception as e:
                logger.error(f"[MongoDB] Error fetching exemplars from DB: {e}")

        # Fallback in-memory
        res = self._memory_exemplars
        if lang:
            res = [e for e in res if e.get("language") == lang]
        if intent:
            res = [e for e in res if e.get("intent") == intent]
        return res

    def save_exemplar(self, exemplar: Dict[str, Any]) -> bool:
        """Insert or update an exemplar in MongoDB."""
        self._memory_exemplars.append(exemplar)
        if not self.connected or self.db is None:
            return True

        try:
            ex_id = exemplar.get("id")
            if ex_id:
                self.db["exemplars"].replace_one({"id": ex_id}, exemplar, upsert=True)
            else:
                self.db["exemplars"].insert_one(exemplar)
            return True
        except Exception as e:
            logger.error(f"[MongoDB] Failed to save exemplar: {e}")
            return False

    # -------------------------------------------------------------
    # Conversation Logging & History
    # -------------------------------------------------------------
    def log_conversation(self, payload: Dict[str, Any]) -> str:
        """
        Store a completed customer inquiry interaction.
        Returns the conversation record ID.
        """
        record = {
            "session_id": payload.get("session_id", "default_session"),
            "user_message": payload.get("user_message", ""),
            "response": payload.get("response", ""),
            "target_language": payload.get("target_language", {}),
            "language_code": payload.get("target_language", {}).get("code", "unknown"),
            "intent": payload.get("intent", "general_inquiry"),
            "intent_confidence": payload.get("intent_confidence", 0.0),
            "sentiment": payload.get("sentiment", "Neutral"),
            "sentiment_score": payload.get("sentiment_score", 0.5),
            "entities": payload.get("entities", {}),
            "cot_trace": payload.get("cot_trace", []),
            "policy_applied": payload.get("policy_applied", {}),
            "latency_ms": payload.get("latency_ms", 0),
            "model_source": payload.get("model_source", "Native Multilingual ICL Engine"),
            "strategy": payload.get("prompt_inspection", {}).get("strategy", "few_shot"),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        # Keep in memory
        self._memory_conversations.insert(0, record)
        if len(self._memory_conversations) > 200:
            self._memory_conversations.pop()

        if self.connected and self.db is not None:
            try:
                res = self.db["conversations"].insert_one(record)
                return str(res.inserted_id)
            except Exception as e:
                logger.error(f"[MongoDB] Error logging conversation: {e}")

        return f"mem_{len(self._memory_conversations)}"

    def get_conversation_history(self, limit: int = 50, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recent conversation history."""
        if self.connected and self.db is not None:
            try:
                query = {}
                if session_id:
                    query["session_id"] = session_id
                cursor = self.db["conversations"].find(query).sort("timestamp", -1).limit(limit)
                results = []
                for doc in cursor:
                    doc["id"] = str(doc.pop("_id", ""))
                    results.append(doc)
                return results
            except Exception as e:
                logger.error(f"[MongoDB] Error retrieving conversations: {e}")

        # Fallback memory
        records = self._memory_conversations
        if session_id:
            records = [r for r in records if r.get("session_id") == session_id]
        return records[:limit]

    # -------------------------------------------------------------
    # Feedback & Quality
    # -------------------------------------------------------------
    def log_feedback(self, feedback_data: Dict[str, Any]) -> bool:
        """Store user thumbs-up/down feedback or corrections."""
        record = {
            "conversation_id": feedback_data.get("conversation_id"),
            "rating": feedback_data.get("rating", 1), # 1 = positive, -1 = negative
            "feedback_type": feedback_data.get("feedback_type", "rating"),
            "notes": feedback_data.get("notes", ""),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        self._memory_feedback.append(record)

        if self.connected and self.db is not None:
            try:
                self.db["feedback"].insert_one(record)
                return True
            except Exception as e:
                logger.error(f"[MongoDB] Error logging feedback: {e}")
                return False
        return True

    # -------------------------------------------------------------
    # Analytics & Status
    # -------------------------------------------------------------
    def get_analytics(self) -> Dict[str, Any]:
        """Aggregate high-level system usage analytics."""
        if self.connected and self.db is not None:
            try:
                total_conversations = self.db["conversations"].count_documents({})
                total_exemplars = self.db["exemplars"].count_documents({})
                total_feedback = self.db["feedback"].count_documents({})

                # Aggregation for top languages
                pipeline = [
                    {"$group": {"_id": "$language_code", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 5}
                ]
                top_langs = list(self.db["conversations"].aggregate(pipeline))

                return {
                    "total_conversations": total_conversations,
                    "total_exemplars": total_exemplars,
                    "total_feedback": total_feedback,
                    "top_languages": [{"lang": x["_id"], "count": x["count"]} for x in top_langs],
                    "storage": "MongoDB"
                }
            except Exception as e:
                logger.error(f"[MongoDB] Analytics aggregation failed: {e}")

        return {
            "total_conversations": len(self._memory_conversations),
            "total_exemplars": len(self._memory_exemplars),
            "total_feedback": len(self._memory_feedback),
            "top_languages": [],
            "storage": "In-Memory Fallback"
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns connection information and telemetry for UI inspection."""
        # Mask credentials in URI for safe display
        masked_uri = self.uri
        if "@" in masked_uri:
            prefix = masked_uri.split("@")[0]
            host_part = masked_uri.split("@")[1]
            scheme = prefix.split("://")[0]
            masked_uri = f"{scheme}://***:***@{host_part}"

        counts = {
            "conversations": 0,
            "exemplars": len(self._memory_exemplars),
            "feedback": len(self._memory_feedback)
        }

        if self.connected and self.db is not None:
            try:
                counts["conversations"] = self.db["conversations"].count_documents({})
                counts["exemplars"] = self.db["exemplars"].count_documents({})
                counts["feedback"] = self.db["feedback"].count_documents({})
            except Exception:
                pass
        else:
            counts["conversations"] = len(self._memory_conversations)

        return {
            "connected": self.connected,
            "database_name": self.db_name,
            "uri_configured": masked_uri,
            "pymongo_installed": PYMONGO_AVAILABLE,
            "status_text": "Connected" if self.connected else "Standby (In-Memory Fallback Mode)",
            "last_error": self.last_error,
            "counts": counts
        }
