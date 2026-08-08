#!/usr/bin/env python3
"""
Lightweight model setup for free tier deployment.
Downloads only scikit-learn models.
Skips heavy torch/transformers models.
Initializes ChromaDB vector storage.
"""

import os
import sys
import pickle
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("HUGGINGFACE_MODEL_CACHE_DIR", "./ml_models"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def setup_priority_model() -> bool:
    """Create lightweight default Random Forest priority model."""
    model_path = CACHE_DIR / "priority_model.pkl"

    if model_path.exists():
        logger.info("Priority model already exists, skipping creation.")
        return True

    logger.info("Creating default scikit-learn priority model...")

    try:
        from sklearn.ensemble import RandomForestClassifier
        import numpy as np

        X_train = [
            [8, 20, 1, 150, 1, 1, 0.9, 5.0],
            [8, 5,  1, 80,  1, 1, 0.7, 3.0],
            [7, 15, 1, 120, 1, 0, 0.8, 4.0],
            [7, 8,  0, 100, 1, 0, 0.6, 3.5],
            [6, 10, 1, 90,  0, 0, 0.7, 3.0],
            [6, 3,  1, 70,  0, 0, 0.6, 2.5],
            [5, 5,  0, 80,  0, 0, 0.5, 3.0],
            [4, 8,  1, 60,  0, 0, 0.5, 2.0],
            [4, 2,  0, 50,  0, 0, 0.4, 2.0],
            [3, 3,  0, 40,  0, 0, 0.3, 1.5],
            [2, 1,  0, 30,  0, 0, 0.3, 1.5],
            [1, 0,  0, 25,  0, 0, 0.2, 1.0],
            [0, 0,  0, 20,  0, 0, 0.2, 1.0],
            [8, 50, 1, 200, 1, 1, 0.95, 6.0],
            [7, 30, 1, 180, 1, 0, 0.85, 5.0],
            [6, 25, 1, 150, 0, 0, 0.75, 4.0],
            [5, 15, 0, 120, 0, 0, 0.65, 3.5],
            [3, 5,  0, 60,  0, 0, 0.40, 2.0],
            [2, 2,  0, 40,  0, 0, 0.30, 1.5],
            [8, 0,  0, 200, 1, 1, 0.50, 8.0],
        ]

        y_train = [3, 3, 2, 2, 2, 1, 1, 1, 1, 0, 0, 0, 0, 3, 2, 1, 1, 0, 0, 3]

        X = np.array(X_train)
        y = np.array(y_train)

        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            random_state=42,
            class_weight="balanced"
        )
        model.fit(X, y)

        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        logger.info("✅ Scikit-learn priority model created successfully.")
        return True

    except Exception as e:
        logger.error(f"Priority model creation failed: {e}")
        return False


def setup_chroma_db() -> bool:
    """Initialize ChromaDB vector storage directory."""
    chroma_dir = CACHE_DIR / "chroma_db"
    chroma_dir.mkdir(parents=True, exist_ok=True)

    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection = client.get_or_create_collection(
            name="community_issues",
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"✅ ChromaDB initialized. Collection count: {collection.count()}")
        return True
    except Exception as e:
        logger.error(f"ChromaDB setup failed: {e}")
        return False


def main():
    logger.info("Setting up lightweight ML components for free tier...")
    logger.info(f"Target Cache Directory: {CACHE_DIR.absolute()}")

    results = {
        "priority_model": setup_priority_model(),
        "chroma_db": setup_chroma_db()
    }

    success = sum(results.values())
    total = len(results)

    logger.info(f"Lightweight setup complete: {success}/{total} components ready.")
    for component, ok in results.items():
        status = "✅" if ok else "❌"
        logger.info(f"  {status} {component}")

    if success < total:
        logger.warning("Some components failed, but platform fallback is active.")


if __name__ == "__main__":
    main()
