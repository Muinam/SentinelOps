from pydantic_settings import BaseSettings     # BaseSettings - .env se auto values uthata hai
from pydantic import Field
from functools import lru_cache                # lru_cache - settings ko baar baar load hone se bachata hai

class Settings(BaseSettings):
    """
    Ye class hamari poori app ki configuration define karti hai.
    Har attribute automatically .env file ya system environment se match ho kar fill hota hai.
    """

    # Field(...) ka matlab ye required hai, agar .env me na mile to error aayega
    groq_api_key:str = Field(..., description="Groq Api Key (free tier)")

    # open-source model choose karega
    groq_model:str = Field(
        default="llama-3.3-70b-versatile",
        description='Which open-source model to use via Groq'
    )

    faiss_index_path:str = Field(
        default="./data/faiss_index.bin",
        description='Path to the saved FAISS vector index file'   
    )

    # postgres/Supabase connection string
    database_url:str = Field(..., description='Postgres/Supabase connection string')

    class Config:
        # Pydantic ko batata hai ke values ".env" naam ki file se uthani hain
        env_file='.env'
        # Agar .env me extra unused variables hon to error na de
        extra = 'ignore'



@lru_cache()  # Decorator - is function ka result ek dafa compute ho ga, phir cache se milega
def get_settings() -> Settings:
    """
    Settings object ko lazily (jab zaroorat ho tab) banata hai aur cache karta hai.
    Poore app me hum isi function ko call karenge settings access karne ke liye.
    """
    return Settings()  # .env file read kar ke Settings object return karta hai
