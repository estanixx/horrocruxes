import os
from pathlib import Path
from dotenv import load_dotenv
import kagglehub
load_dotenv()

def main() -> None:
    dataset = os.getenv("KAGGLE_DATASET", "gulsahdemiryurek/harry-potter-dataset")
    target_dir = os.getenv("KAGGLE_DOWNLOAD_DIR", "./data/kaggle")

    path = kagglehub.dataset_download(dataset)
    path_obj = Path(path)
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    for file in path_obj.glob("*.csv"):
        destination = target_path / file.name
        if destination.exists():
            continue
        destination.write_bytes(file.read_bytes())

    print(f"Downloaded dataset to: {target_path}")


if __name__ == "__main__":
    main()
