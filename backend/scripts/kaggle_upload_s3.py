import os
from pathlib import Path
from dotenv import load_dotenv
import boto3
load_dotenv()

def main() -> None:
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET is required")

    prefix = os.getenv("S3_CSV_PREFIX", "data/structured")
    source_dir = Path(os.getenv("KAGGLE_DOWNLOAD_DIR", "./data/kaggle"))

    if not source_dir.exists():
        raise RuntimeError(f"Source directory not found: {source_dir}")

    s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))

    for file in source_dir.glob("*.csv"):
        key = f"{prefix.rstrip('/')}/{file.name}"
        s3.upload_file(str(file), bucket, key)
        print(f"Uploaded {file.name} to s3://{bucket}/{key}")


if __name__ == "__main__":
    main()
