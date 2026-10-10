"""
Test script to demonstrate the decoupled Rich progress observer.

Run this script directly:
uv run python examples/test_progress.py
"""

import time

from episteme_pipeline.events.bus import SimpleEventEmitter
from episteme_pipeline.events.models import ProgressStarted, ProgressAdvanced, ProgressCompleted
from episteme_pipeline.events.progress_observer import RichProgressObserver


def mock_phase1(emitter):
    task_name = "Phase 1: 5 docs"
    total = 5
    emitter.emit(ProgressStarted(task_name=task_name, total_items=total, description="Data Foundation"))
    
    for _ in range(total):
        time.sleep(0.4)  # Simulate processing chunk
        emitter.emit(ProgressAdvanced(task_name=task_name, advance=1))
        
    emitter.emit(ProgressCompleted(task_name=task_name))

def mock_phase2(emitter):
    task_name = "Phase 2: 120 chunks"
    total = 120
    batch_size = 10
    emitter.emit(ProgressStarted(task_name=task_name, total_items=total, description="Entity Discovery"))
    
    for i in range(0, total, batch_size):
        time.sleep(0.3)  # Simulate LLM NER & Linking batch
        advance = min(batch_size, total - i)
        emitter.emit(ProgressAdvanced(task_name=task_name, advance=advance))
        
    emitter.emit(ProgressCompleted(task_name=task_name))

def main():
    import logging
    
    emitter = SimpleEventEmitter()
    
    with RichProgressObserver(third_party_log_level=logging.WARNING) as observer:
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            handlers=[observer.get_rich_handler(rich_tracebacks=True, show_path=False)],
            force=True,
        )
        logger = logging.getLogger("pipeline")
        
        emitter.register_observer(observer)
        
        logger.info("Testing decoupled ProgressObserver...")
        logger.info("This will show simulated pipeline execution using rich progress bars.\n")
        
        # Simulate pipeline execution
        logger.info("Starting Data Foundation...")
        mock_phase1(emitter)
        time.sleep(0.5)
        
        logger.warning("Simulated Warning: Document was missing TOC!")
        time.sleep(0.5)
        
        logger.info("Starting Entity Discovery...")
        mock_phase2(emitter)
        
    logger.info("Pipeline simulated successfully!")

if __name__ == "__main__":
    main()
