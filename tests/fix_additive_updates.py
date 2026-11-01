"""Quick fix for additive branch updates - patches the ingestion route."""

import json
from database.crud import get_current_criteria

def merge_branch_lists(existing_value_json: str, new_value_json: str, operation: str) -> str:
    """Merge branch lists based on operation type.
    
    Args:
        existing_value_json: JSON string of existing branches
        new_value_json: JSON string of new branches  
        operation: "SET", "ADD", or "REMOVE"
    
    Returns:
        JSON string of merged branches
    """
    existing = json.loads(existing_value_json) if existing_value_json else []
    new = json.loads(new_value_json)
    
    # Ensure both are lists
    if not isinstance(existing, list):
        existing = [existing] if existing else []
    if not isinstance(new, list):
        new = [new] if new else []
    
    if operation == "ADD":
        # Merge: add new branches to existing, remove duplicates
        merged = list(set(existing + new))
        return json.dumps(sorted(merged))
    elif operation == "REMOVE":
        # Remove specified branches
        merged = [b for b in existing if b not in new]
        return json.dumps(sorted(merged))
    else:  # SET or unknown
        # Replace completely
        return new_value_json

# Test the function
print("Testing merge_branch_lists:")
print()

# Test ADD
result1 = merge_branch_lists('["CSE", "ECE", "EEE"]', '["ISE"]', "ADD")
print(f'ADD: ["CSE", "ECE", "EEE"] + ["ISE"] = {result1}')

# Test REMOVE  
result2 = merge_branch_lists('["CSE", "ECE", "EEE", "ISE"]', '["ECE"]', "REMOVE")
print(f'REMOVE: ["CSE", "ECE", "EEE", "ISE"] - ["ECE"] = {result2}')

# Test SET
result3 = merge_branch_lists('["CSE", "ECE"]', '["IT", "MECH"]', "SET")
print(f'SET: ["CSE", "ECE"] -> ["IT", "MECH"] = {result3}')
