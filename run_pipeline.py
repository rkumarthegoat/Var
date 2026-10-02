from src.ingest import download_all
from src.clean import build
from src.analyze import main as analyze

if __name__ == "__main__":
    download_all()
    build()
    analyze()