from __future__ import annotations
import os
from evalos.memory import Memory

def test_memory_record_and_get():
    # Setup test memory db
    db_path = "test_memory.json"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    memory = Memory(db_path=db_path)
    
    # Record failures
    memory.record_failures("gpt-4", ["clarity", "accuracy", "clarity"])
    
    # Get recurring failures
    recurring = memory.get_recurring_failures("gpt-4", top_k=2)
    assert recurring == ["clarity", "accuracy"]
    
    # Record more
    memory.record_failures("gpt-4", ["accuracy", "accuracy"])
    recurring = memory.get_recurring_failures("gpt-4", top_k=2)
    assert recurring == ["accuracy", "clarity"]
    
    # Test for non-existent model
    assert memory.get_recurring_failures("unknown-model") == []
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)
