import sqlite3
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "data" / "dld_owners.sqlite"
if p.is_file():
    c = sqlite3.connect(p)
    c.execute(
        "UPDATE property_owners SET owner_name=NULL, owner_phone=NULL WHERE owner_name LIKE 'REPLACE%'"
    )
    c.commit()
    c.close()
    print("cleared placeholders in", p)