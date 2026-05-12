# Pool Occupancy Pipeline

Production-style event-driven data collection pipeline that scrapes swimming pool occupancy data from the Znojmo public pool website and stores it as immutable time-series data in Amazon S3.

---

## Overview

This project collects pool occupancy measurements every minute during configured opening hours using a fully serverless/containerized AWS architecture.

The system:

- Scrapes occupancy data from `https://www.sportovisteznojmo.cz/bazen-louka`
- Extracts occupancy from HTML `<canvas data-text="...">`
- Stores one immutable CSV object per measurement in S3
- Uses CloudWatch Logs for observability
- Uses Athena for querying and analysis

The project intentionally prioritizes:

- Simplicity
- Reliability
- Observability
- Low operational overhead
- Low monthly cost

---

## Architecture

```text
                EventBridge
           (runs every minute)
                       |
                       v
                ECS / Fargate
          (stateless container task)
                       |
        +--------------+--------------+
        |                             |
        v                             v
  Pool Website                 CloudWatch Logs
 (scrape occupancy)             (observability)
        |
        v
        S3 Bucket
 (immutable CSV objects)
        |
        v
      Athena
(SQL analytics over S3)
```

---

## Why ECS/Fargate Instead of Lambda?

This project intentionally uses ECS Fargate instead of Lambda to:

- Demonstrate containerized batch workloads
- Keep execution environment fully portable
- Avoid Lambda packaging/runtime limitations
- Simulate production-style ingestion pipelines

The scraper is packaged as a Docker image and executed as a short-lived stateless task.

---

## Scheduling Strategy

EventBridge triggers the task every minute:

```text
rate(1 minute)
```

Instead of encoding business-hour complexity into AWS cron expressions, the scraper itself decides whether to scrape or skip.

This keeps:

- Infrastructure simple
- DST handling correct
- Schedule logic versioned in code

The scraper uses:

```python
ZoneInfo("Europe/Prague")
```

for automatic daylight-saving handling.

### Current scraping schedule

- Monday–Saturday: `05:55–21:05`
- Sunday: `10:55–21:05`

Outside these hours the task exits immediately with:

```json
{"event":"skipped","reason":"outside_operating_hours"}
```

During allowed hours, the scraper collects occupancy measurements every minute.

---

## Data Format

Each scrape produces exactly one immutable CSV object in S3.

### Example object key

```text
raw/year=2026/month=04/day=23/08-59-13-403435.csv
```

### Example file contents

```csv
timestamp,value
2026-04-23T08:59:13.403435+00:00,148
```

### Important details

- One file per scrape
- Append-only immutable pattern
- UTC timestamps (`ISO8601`)
- Partitioned S3 layout for Athena
- One measurement per minute during opening hours

---

## Why One File Per Minute?

Amazon S3 does not support append operations.

Instead of:

```text
read -> append -> rewrite
```

this project uses:

```text
write-once immutable objects
```

### Benefits

- Avoids race conditions
- Highly reliable
- Naturally time-series oriented
- Aligns with modern data lake ingestion patterns

---

## Observability

The scraper emits structured JSON logs into CloudWatch.

### Example successful scrape

```json
{"event":"scrape_success","value":148,"duration_ms":585}
```

### Example successful upload

```json
{"event":"s3_success","bucket":"pool-scraper-data-znojmo"}
```

### Example skipped execution

```json
{"event":"skipped","reason":"outside_operating_hours"}
```

---

## Athena Analytics

Athena is used to query CSV data directly from S3.

### Example query

```sql
SELECT
  hour(from_iso8601_timestamp(timestamp)) AS hour,
  avg(value) AS avg_people
FROM pool_data
GROUP BY 1
ORDER BY 1;
```

This allows analysis such as:

- Busiest hours
- Quietest hours
- Weekday vs weekend comparison
- Occupancy trends over time

---

## Cost Considerations

The project was intentionally designed to stay inexpensive.

### Key design choices

- Fargate tasks are short-lived
- No always-on servers
- Immutable S3 ingestion
- Simple EventBridge scheduling
- No NAT Gateway

The project currently uses:

```text
AssignPublicIp = ENABLED
```

for simplicity and lower cost.

---

## Repository Structure

```text
.
├── Dockerfile
├── README.md
├── requirements.txt
├── scraper.py
├── task-def.template.json
├── targets.template.json
├── ecs-task-trust.template.json
├── eventbridge-trust.template.json
├── .dockerignore
└── .gitignore
```

Template JSON files are sanitized versions of the deployed infrastructure configuration.

---

## Running Locally

### Python

```bash
python scraper.py
```

### Docker

```bash
docker build -t pool-scraper .
docker run --rm pool-scraper
```

---

## Future Improvements

Potential future work:

- Athena dashboards
- Occupancy heatmaps
- File compaction (hourly/daily)
- Anomaly detection
- Automated deployment pipeline
- Historical trend analysis

---

## Technologies Used

- Python
- Docker
- AWS ECS
- AWS Fargate
- AWS EventBridge
- Amazon S3
- Amazon CloudWatch Logs
- Amazon Athena

---

## Key Engineering Concepts Demonstrated

- Event-driven architecture
- Stateless compute
- Immutable data ingestion
- Cloud-native observability
- Partitioned time-series storage
- Cost-aware infrastructure design
- Serverless container workloads