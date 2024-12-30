from app import db, Part
parts = Part.query.all()
for part in parts:
    print(part.name)