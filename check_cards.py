from database.db import query_one

row = query_one("SELECT COUNT(*) AS total, COUNT(rfid_uid) AS with_card FROM students")
print(f"Students: {row['total']}, with a card: {row['with_card']}")