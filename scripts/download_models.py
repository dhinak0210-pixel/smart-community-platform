#!/usr/bin/env python3
"""Pre-download script for Smart Community Platform AI/ML models."""

import os
import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting model pre-download sequence...")
    start_time = time.time()

    cache_dir = os.getenv("HUGGINGFACE_MODEL_CACHE_DIR", "./ml_models")
    os.makedirs(cache_dir, exist_ok=True)
    logger.info(f"Model cache directory: {os.path.abspath(cache_dir)}")

    # 1. DistilRoBERTa Zero-shot Classifier
    try:
        logger.info("1/4 Downloading DistilRoBERTa zero-shot classifier...")
        from transformers import pipeline
        pipeline(
            "zero-shot-classification",
            model="cross-encoder/nli-distilroberta-base",
            model_kwargs={"cache_dir": cache_dir}
        )
        logger.info("✓ DistilRoBERTa downloaded successfully.")
    except Exception as e:
        logger.error(f"✗ Failed to download DistilRoBERTa: {e}")

    # 2. YOLOv8n
    try:
        logger.info("2/4 Downloading YOLOv8n object detection model...")
        from ultralytics import YOLO
        yolo_path = os.path.join(cache_dir, "yolov8n.pt")
        model = YOLO("yolov8n.pt")
        model.save(yolo_path)
        logger.info(f"✓ YOLOv8n saved to {yolo_path}")
    except Exception as e:
        logger.error(f"✗ Failed to download YOLOv8n: {e}")

    # 3. MiniLM Embeddings
    try:
        logger.info("3/4 Downloading all-MiniLM-L6-v2 sentence transformer...")
        from sentence_transformers import SentenceTransformer
        SentenceTransformer("all-MiniLM-L6-v2", cache_folder=cache_dir)
        logger.info("✓ SentenceTransformer downloaded successfully.")
    except Exception as e:
        logger.error(f"✗ Failed to download SentenceTransformer: {e}")

    # 4. ChromaDB Storage Init
    try:
        logger.info("4/4 Initializing ChromaDB vector store...")
        import chromadb
        chroma_dir = os.path.join(cache_dir, "chroma_db")
        os.makedirs(chroma_dir, exist_ok=True)
        client = chromadb.PersistentClient(path=chroma_dir)
        client.get_or_create_collection(name="community_issues", metadata={"hnsw:space": "cosine"})
        logger.info("✓ ChromaDB storage initialized successfully.")
    except Exception as e:
        logger.error(f"✗ Failed to initialize ChromaDB: {e}")

    elapsed = round(time.time() - start_time, 2)
    logger.info(f"Model pre-download complete in {elapsed}s")


if __name__ == "__main__":
    main()
