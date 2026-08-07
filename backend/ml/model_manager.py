"""Central ModelManager singleton for Smart Community Platform.

Loads all machine learning models once at application startup.
Provides graceful fallbacks and health monitoring capabilities.
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional, Any

import numpy as np
if not hasattr(np, "long"):
    np.long = np.int64
if not hasattr(np, "ulong"):
    np.ulong = np.uint64

from backend.config import settings

logger = logging.getLogger(__name__)


class ModelManager:
    """Singleton that loads and holds all ML models.
    
    Load once at startup. Reuse everywhere.
    Never load a model inside an API request handler.
    """

    _instance: Optional["ModelManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self.models: dict[str, Any] = {}
        self.model_status: dict[str, str] = {}
        self.load_times: dict[str, float] = {}
        self._initialized = True

        logger.info("ModelManager initialized (models not loaded yet)")

    def load_all_models(self) -> dict[str, bool]:
        """Load all ML models at startup.
        
        Called once from main.py startup event.
        Returns status dict showing which loaded vs failed.
        Never raises exceptions (logs and marks as failed).
        """
        logger.info("Starting ML model loading sequence...")
        start = time.time()

        results: dict[str, bool] = {}
        results["text_classifier"] = self._load_text_classifier()
        results["yolo"] = self._load_yolo()
        results["sentence_transformer"] = self._load_sentence_transformer()
        results["priority_model"] = self._load_priority_model()
        results["groq_client"] = self._load_groq_client()
        results["chroma_db"] = self._load_chroma_db()

        total_time = round(time.time() - start, 2)
        loaded = sum(1 for v in results.values() if v)
        total = len(results)

        logger.info(
            f"ML models loaded: {loaded}/{total} successful in {total_time}s"
        )

        if loaded < total:
            failed = [k for k, v in results.items() if not v]
            logger.warning(
                f"Some ML models failed to load: {failed}. "
                f"Fallback methods will be used for these."
            )

        return results

    def _load_text_classifier(self) -> bool:
        """Load DistilRoBERTa / DistilBERT zero-shot pipeline for text classification."""
        try:
            t = time.time()
            logger.info("Loading DistilBERT zero-shot text classifier...")

            from transformers import pipeline

            cache_dir = settings.HUGGINGFACE_MODEL_CACHE_DIR
            os.makedirs(cache_dir, exist_ok=True)

            self.models["text_classifier"] = pipeline(
                "zero-shot-classification",
                model="cross-encoder/nli-distilroberta-base",
                device=-1,
                model_kwargs={"cache_dir": cache_dir}
            )

            self.model_status["text_classifier"] = "loaded"
            self.load_times["text_classifier"] = round(time.time() - t, 2)
            logger.info(
                f"DistilBERT loaded in {self.load_times['text_classifier']}s"
            )
            return True

        except Exception as e:
            self.model_status["text_classifier"] = f"failed: {str(e)}"
            logger.error(f"Failed to load text classifier: {e}")
            logger.info("Will use keyword fallback for text classification")
            return False

    def _load_yolo(self) -> bool:
        """Load YOLOv8n for image object detection."""
        try:
            t = time.time()
            logger.info("Loading YOLOv8n image detection model...")

            from ultralytics import YOLO

            model_path = settings.YOLO_MODEL_PATH
            os.makedirs(os.path.dirname(os.path.abspath(model_path)), exist_ok=True)

            if os.path.exists(model_path):
                self.models["yolo"] = YOLO(model_path)
            else:
                logger.info(f"Downloading YOLOv8n to local path {model_path}...")
                self.models["yolo"] = YOLO("yolov8n.pt")
                try:
                    self.models["yolo"].save(model_path)
                except Exception:
                    pass

            self.model_status["yolo"] = "loaded"
            self.load_times["yolo"] = round(time.time() - t, 2)
            logger.info(f"YOLOv8n loaded in {self.load_times['yolo']}s")
            return True

        except Exception as e:
            self.model_status["yolo"] = f"failed: {str(e)}"
            logger.error(f"Failed to load YOLO: {e}")
            logger.info("Will use metadata-only analysis for images")
            return False

    def _load_sentence_transformer(self) -> bool:
        """Load MiniLM for semantic similarity and embeddings."""
        try:
            t = time.time()
            logger.info("Loading sentence transformer (MiniLM)...")

            from sentence_transformers import SentenceTransformer

            cache_dir = settings.HUGGINGFACE_MODEL_CACHE_DIR
            os.makedirs(cache_dir, exist_ok=True)

            self.models["sentence_transformer"] = SentenceTransformer(
                "all-MiniLM-L6-v2",
                cache_folder=cache_dir
            )

            self.model_status["sentence_transformer"] = "loaded"
            self.load_times["sentence_transformer"] = round(time.time() - t, 2)
            logger.info(
                f"MiniLM loaded in {self.load_times['sentence_transformer']}s"
            )
            return True

        except Exception as e:
            self.model_status["sentence_transformer"] = f"failed: {str(e)}"
            logger.error(f"Failed to load sentence transformer: {e}")
            logger.info("Will use keyword overlap for similarity")
            return False

    def _load_priority_model(self) -> bool:
        """Load or create Random Forest priority predictor."""
        try:
            t = time.time()
            logger.info("Loading priority prediction model...")

            import pickle
            cache_dir = Path(settings.HUGGINGFACE_MODEL_CACHE_DIR)
            cache_dir.mkdir(parents=True, exist_ok=True)
            model_path = cache_dir / "priority_model.pkl"

            if model_path.exists():
                try:
                    with open(model_path, "rb") as f:
                        self.models["priority_model"] = pickle.load(f)
                    logger.info("Loaded saved priority model from disk")
                except Exception as ex:
                    logger.warning(f"Saved priority model load failed ({ex}), rebuilding default model...")
                    self.models["priority_model"] = self._create_default_priority_model()
                    with open(model_path, "wb") as f:
                        pickle.dump(self.models["priority_model"], f)
            else:
                self.models["priority_model"] = self._create_default_priority_model()
                with open(model_path, "wb") as f:
                    pickle.dump(self.models["priority_model"], f)
                logger.info("Created and saved default priority model")

            self.model_status["priority_model"] = "loaded"
            self.load_times["priority_model"] = round(time.time() - t, 2)
            return True

        except Exception as e:
            self.model_status["priority_model"] = f"failed: {str(e)}"
            logger.error(f"Failed to load priority model: {e}")
            return False

    def _create_default_priority_model(self) -> Any:
        """Creates a Random Forest model with sensible synthetic domain knowledge."""
        from sklearn.ensemble import RandomForestClassifier
        import numpy as np

        # Features: [category_score (0-8), vote_count, has_image (0/1), desc_word_count, has_urgency, has_safety, ai_confidence, length_ratio]
        # Labels: 3=critical, 2=high, 1=medium, 0=low
        X_train = []
        y_train = []

        # Synthetic samples covering categories and priorities
        sample_configs = [
            # Critical cases (safety/flooding + high urgency + safety keywords)
            (8, 25, 1, 80, 1, 1, 0.9, 3.0, 3),
            (7, 30, 1, 120, 1, 1, 0.85, 4.0, 3),
            (8, 5, 1, 40, 1, 1, 0.95, 2.5, 3),
            (6, 50, 1, 150, 1, 1, 0.88, 5.0, 3),

            # High cases (infrastructure/utilities + urgency)
            (6, 15, 1, 60, 1, 0, 0.8, 2.0, 2),
            (5, 20, 1, 70, 1, 0, 0.75, 2.5, 2),
            (7, 10, 0, 45, 1, 0, 0.5, 1.8, 2),
            (4, 25, 1, 90, 0, 0, 0.8, 3.2, 2),

            # Medium cases (waste/traffic + moderate info)
            (3, 8, 1, 35, 0, 0, 0.7, 1.5, 1),
            (4, 5, 0, 30, 0, 0, 0.5, 1.2, 1),
            (2, 12, 1, 50, 0, 0, 0.75, 2.0, 1),
            (5, 3, 0, 25, 0, 0, 0.5, 1.0, 1),

            # Low cases (minor complaints/cosmetic)
            (1, 1, 0, 15, 0, 0, 0.4, 0.8, 0),
            (2, 2, 0, 18, 0, 0, 0.5, 0.9, 0),
            (0, 0, 0, 12, 0, 0, 0.3, 0.6, 0),
            (3, 1, 0, 14, 0, 0, 0.4, 0.7, 0),
        ]

        # Duplicate with minor noise to reach 60+ samples
        np.random.seed(42)
        for cat_score, votes, img, desc_len, urg, saf, conf, ratio, label in sample_configs:
            for _ in range(4):
                noise_votes = max(0, int(votes + np.random.randint(-2, 3)))
                noise_desc = max(5, int(desc_len + np.random.randint(-5, 6)))
                noise_conf = float(np.clip(conf + np.random.uniform(-0.05, 0.05), 0.1, 1.0))
                X_train.append([cat_score, noise_votes, img, noise_desc, urg, saf, noise_conf, ratio])
                y_train.append(label)

        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight="balanced"
        )
        model.fit(X_train, y_train)
        return model

    def _load_groq_client(self) -> bool:
        """Load Groq API client for LLM features."""
        try:
            if not settings.GROQ_API_KEY:
                logger.warning("GROQ_API_KEY not set. LLM features disabled.")
                self.model_status["groq_client"] = "no api key"
                return False

            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)

            # Quick connection test
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "Ping"}],
                max_tokens=5
            )
            if response and response.choices:
                self.models["groq_client"] = client
                self.model_status["groq_client"] = "loaded"
                logger.info("Groq client connected and tested successfully")
                return True
            return False

        except Exception as e:
            self.model_status["groq_client"] = f"failed: {str(e)}"
            logger.error(f"Failed to connect Groq: {e}")
            return False

    def _load_chroma_db(self) -> bool:
        """Load ChromaDB for vector storage."""
        try:
            import chromadb

            cache_dir = Path(settings.HUGGINGFACE_MODEL_CACHE_DIR)
            persist_dir = str(cache_dir / "chroma_db")
            os.makedirs(persist_dir, exist_ok=True)

            self.models["chroma_client"] = chromadb.PersistentClient(path=persist_dir)

            self.models["issues_collection"] = (
                self.models["chroma_client"]
                .get_or_create_collection(
                    name="community_issues",
                    metadata={"hnsw:space": "cosine"}
                )
            )

            self.model_status["chroma_db"] = "loaded"
            count = self.models["issues_collection"].count()
            logger.info(f"ChromaDB loaded. Issues indexed: {count}")
            return True

        except Exception as e:
            self.model_status["chroma_db"] = f"failed: {str(e)}"
            logger.error(f"Failed to load ChromaDB: {e}")
            return False

    def get(self, model_name: str) -> Any:
        """Get a loaded model instance. Returns None if not loaded."""
        return self.models.get(model_name)

    def is_loaded(self, model_name: str) -> bool:
        """Check if a model is loaded and ready."""
        return (
            model_name in self.models
            and self.model_status.get(model_name) == "loaded"
        )

    def get_status(self) -> dict[str, Any]:
        """Get status of all models for monitoring endpoints."""
        all_model_keys = [
            "text_classifier", "yolo",
            "sentence_transformer", "priority_model",
            "groq_client", "chroma_db"
        ]
        return {
            "models": {
                name: {
                    "status": self.model_status.get(name, "not_attempted"),
                    "load_time_seconds": self.load_times.get(name)
                }
                for name in all_model_keys
            },
            "total_loaded": sum(
                1 for s in self.model_status.values() if s == "loaded"
            ),
            "total_models": len(all_model_keys)
        }

    def retrain_priority_model(self, training_data: list[dict[str, Any]]) -> bool:
        """Retrain priority model with real accumulated issue data."""
        try:
            if len(training_data) < 20:
                logger.warning("Not enough data to retrain priority model (need 20+ samples)")
                return False

            from sklearn.ensemble import RandomForestClassifier
            import pickle

            X = [item["features"] for item in training_data]
            y = [item["label"] for item in training_data]

            new_model = RandomForestClassifier(
                n_estimators=200,
                max_depth=15,
                random_state=42,
                class_weight="balanced"
            )
            new_model.fit(X, y)

            self.models["priority_model"] = new_model

            model_path = Path(settings.HUGGINGFACE_MODEL_CACHE_DIR) / "priority_model.pkl"
            with open(model_path, "wb") as f:
                pickle.dump(new_model, f)

            logger.info(f"Priority model retrained successfully with {len(training_data)} samples")
            return True

        except Exception as e:
            logger.error(f"Priority model retraining failed: {e}")
            return False


# Global singleton instance
model_manager = ModelManager()
