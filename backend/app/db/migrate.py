# migrate.py
#
# Is file ka kaam: database ko models.py ke mutabiq banana - PURANI DATA ko chhede bina.
#   1) Jo tables maujood nahi (jaise incident_events) wo bana deta hai
#   2) Maujooda tables me jo columns missing hain wo ALTER TABLE se jod deta hai
# SQLAlchemy ka create_all purani table me naye columns NAHI jodta - isliye ye file zaroori hai.
# Dobara chalane par kuch nahi badalta (idempotent). Professional teams iske liye Alembic use karti hain.
#
# Run karne ka tareeqa (ek dafa, backend folder se):
#   python -m app.db.migrate

from sqlalchemy import inspect, text                    # inspect - maujooda columns dekhne ke liye, text - raw SQL
from app.db.database import engine as default_engine, Base   # Hamara engine aur models ki base
import app.db.models                                      # Models import karna zaroori hai (tables register hon)


def ensure_schema(engine=None) -> list:
    """
    Database ko models ke mutabiq banata hai. Return: jo columns naye jode gaye ("table.column" ki list).
    engine - testing ke liye koi aur engine de sakte hain; None to asli engine.
    """
    eng = engine or default_engine                          # Kaunsa database
    Base.metadata.create_all(bind=eng)                       # Missing TABLES bana do (maujooda ko nahi chhedta)

    inspector = inspect(eng)                                  # Database ki maujooda structure dekhne wala
    added = []                                                 # Naye jode gaye columns

    for table in Base.metadata.sorted_tables:                 # Har model ki table ke liye
        existing = {col["name"] for col in inspector.get_columns(table.name)}   # Database me maujooda columns
        for column in table.columns:                           # Model ke har column ke liye
            if column.name in existing:                         # Pehle se hai
                continue                                         # Kuch nahi karna
            column_type = column.type.compile(dialect=eng.dialect)   # Is database ke liye type ka SQL naam (TEXT, FLOAT...)
            default_sql = ""                                      # Default value (agar ho)
            if column.default is not None and getattr(column.default, "is_scalar", False):
                default_sql = f" DEFAULT {column.default.arg!r}"     # Jaise retry_count ke liye DEFAULT 0
            if not column.nullable and not default_sql:           # Purani rows ke liye value kahan se aaye?
                raise RuntimeError(f"{table.name}.{column.name}: NOT NULL column bina default ke jod nahi sakte")
            with eng.begin() as conn:                              # Ek transaction me ALTER chalao
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column_type}{default_sql}"))
            added.append(f"{table.name}.{column.name}")             # Record karo

    return added


if __name__ == "__main__":
    changes = ensure_schema()                                  # Asli database par chalao
    if changes:
        print("Naye columns jode gaye:")
        for item in changes:
            print(f"  + {item}")
    else:
        print("Database pehle se up-to-date hai, kuch badla nahi.")
