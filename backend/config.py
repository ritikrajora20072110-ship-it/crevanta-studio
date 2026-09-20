import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

load_dotenv(BASE_DIR / ".env", override=True)

class Config:
    AI_PROVIDER: str = "ollama"
    
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    
    GMAIL_USER: str = os.getenv("GMAIL_USER", "")
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
    
    AGENCY_NAME: str = os.getenv("AGENCY_NAME", "Crevanta")
    SENDER_NAME: str = os.getenv("SENDER_NAME", "Crevanta Partnerships")
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", os.getenv("GMAIL_USER", ""))
    
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "127.0.0.1")

    @classmethod
    def reload(cls):
        load_dotenv(BASE_DIR / ".env", override=True)
        cls.AI_PROVIDER = "ollama"
        cls.OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        cls.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
        cls.GMAIL_USER = os.getenv("GMAIL_USER", "")
        cls.GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
        cls.AGENCY_NAME = os.getenv("AGENCY_NAME", "Crevanta")
        cls.SENDER_NAME = os.getenv("SENDER_NAME", "Crevanta Partnerships")
        cls.SENDER_EMAIL = os.getenv("SENDER_EMAIL", os.getenv("GMAIL_USER", ""))

    @classmethod
    def get_status(cls):
        return {
            "ai_provider": "ollama",
            "ollama_base_url": cls.OLLAMA_BASE_URL,
            "ollama_model": cls.OLLAMA_MODEL,
            "gmail_configured": bool(cls.GMAIL_USER and cls.GMAIL_APP_PASSWORD and len(cls.GMAIL_APP_PASSWORD.strip()) >= 12),
            "gmail_user": cls.GMAIL_USER if cls.GMAIL_USER else None,
            "agency_name": cls.AGENCY_NAME,
            "sender_name": cls.SENDER_NAME,
            "sender_email": cls.SENDER_EMAIL
        }

    @classmethod
    def update_settings(cls, updates: dict):
        env_path = BASE_DIR / ".env"
        current_env = {}
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        current_env[k.strip()] = v.strip()
        
        for k, v in updates.items():
            if v is not None:
                current_env[k] = str(v).strip()
        
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# Crevanta Configuration Auto-Updated\n\n")
            for k, v in current_env.items():
                f.write(f"{k}={v}\n")
        
        cls.reload()
        return cls.get_status()
