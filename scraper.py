import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import time
import os
import sys
import boto3

URL = "https://www.sportovisteznojmo.cz/bazen-louka"
TIMEOUT = (3, 7)  # connect timeout, read timeout


# ------------------------
# Logging
# ------------------------
def log_event(event, **kwargs):
    payload = {
        "event": event,
        "ts": datetime.now(ZoneInfo("UTC")).isoformat(),
        **kwargs
    }
    print(json.dumps(payload), flush=True)


# ------------------------
# Operating hours logic
# ------------------------
def is_within_operating_hours():
    tz = ZoneInfo("Europe/Prague")
    now = datetime.now(tz)

    weekday = now.weekday()  # 0=Mon, 6=Sun
    current_minutes = now.hour * 60 + now.minute

    def in_range(start_h, start_m, end_h, end_m):
        start = start_h * 60 + start_m
        end = end_h * 60 + end_m
        return start <= current_minutes <= end

    if weekday == 6:  # Sunday
        allowed = in_range(10, 55, 21, 5)
    else:
        allowed = in_range(5, 55, 21, 5)

    return allowed, now


# ------------------------
# Scraping logic
# ------------------------
def scrape_capacity():
    response = requests.get(URL, timeout=TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    canvas = soup.find("canvas", attrs={"data-text": True})

    if not canvas:
        raise ValueError("canvas with data-text not found")

    value = canvas["data-text"].strip()

    if not value.isdigit():
        raise ValueError(f"unexpected value: {value}")

    return int(value)


# ------------------------
# CSV generation
# ------------------------
def build_csv(timestamp, value):
    return f"timestamp,value\n{timestamp},{value}\n"


# ------------------------
# S3 upload
# ------------------------
def upload_to_s3(bucket, key, body):
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="text/csv"
    )


# ------------------------
# Main
# ------------------------
def main():
    start = time.time()

    # Check operating hours
    allowed, local_now = is_within_operating_hours()

    if not allowed:
        log_event(
            "skipped",
            reason="outside_operating_hours",
            local_time=local_now.isoformat()
        )
        return 0

    try:
        # Scrape
        value = scrape_capacity()

        # Timestamp (UTC canonical)
        timestamp = datetime.now(ZoneInfo("UTC")).isoformat()

        duration_ms = int((time.time() - start) * 1000)

        log_event(
            "scrape_success",
            value=value,
            unit="people",
            timestamp=timestamp,
            duration_ms=duration_ms
        )

        # CSV
        csv_data = build_csv(timestamp, value)

        # S3 upload (optional)
        bucket = os.environ.get("BUCKET")
        if bucket:
            try:
                key = datetime.fromisoformat(timestamp).strftime(
                    "raw/year=%Y/month=%m/day=%d/%H-%M-%S-%f.csv"
                )

                upload_to_s3(bucket, key, csv_data)

                log_event(
                    "s3_success",
                    bucket=bucket,
                    key=key
                )

            except Exception as e:
                log_event("s3_failed", error=str(e))

        # Print CSV (stdout fallback / debugging)
        print(csv_data.strip())

        return 0

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        log_event(
            "scrape_failed",
            error=str(e),
            duration_ms=duration_ms
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())