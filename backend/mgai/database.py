from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class Database:
    def __init__(self, settings):
        self.engine = create_engine(
            settings.database_url, pool_pre_ping=True, echo=False
        )
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.cipher = Fernet(settings.encryption_key.encode())

    def encrypt(self, value):
        import json

        return self.cipher.encrypt(json.dumps(value, ensure_ascii=False).encode())

    def decrypt(self, value):
        import json

        return json.loads(self.cipher.decrypt(value))

    def close(self):
        self.engine.dispose()
