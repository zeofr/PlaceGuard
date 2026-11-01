#!/usr/bin/env python3
"""Check what criteria are in the database."""

import json
from database.connection import get_db_context
from database.crud import get_current_criteria

with get_db_context() as db:
    criteria = get_current_criteria(db, 'DRIVE_TECHMAHINDRA')
    print('TechMahindra Criteria:')
    for c in criteria:
        parsed_value = json.loads(c.value)
        print(f'  {c.criterion_type}:')
        print(f'    Raw value: {repr(c.value)}')
        print(f'    Parsed: {parsed_value} (type: {type(parsed_value).__name__})')
