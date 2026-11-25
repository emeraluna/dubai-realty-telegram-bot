import sqlite3
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "data" / "realty.db"
c = sqlite3.connect(p)
c.execute(
    "UPDATE listings SET owner_name=NULL, owner_phone=NULL, owner_source='unknown' "
    "WHERE owner_name LIKE 'REPLACE%' OR owner_phone LIKE 'REPLACE%' "
    "OR (owner_name='ALEJANDRO VEGA GONZALEZ' AND owner_phone='971501046096')"
)
c.commit()
c.close()
print("cleared placeholder owners in listings")