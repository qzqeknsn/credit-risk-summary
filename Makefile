DB_URL=postgresql://user:password@localhost:5432/risk_db

.PHONY: up load views check verify export all schema shot

up:
	docker-compose up -d

load:
	make schema
	docker exec risk_summary_db psql -U user -d risk_db -f /app/sql/02_load_raw.sql

schema:
	docker exec risk_summary_db psql -U user -d risk_db -f /app/sql/01_schema.sql

views:
	docker exec risk_summary_db psql -U user -d risk_db -f /app/sql/03_v_loans_clean.sql
	docker exec risk_summary_db psql -U user -d risk_db -f /app/sql/04_v_metrics.sql
	docker exec risk_summary_db psql -U user -d risk_db -f /app/sql/05_v_segments.sql
	docker exec risk_summary_db psql -U user -d risk_db -f /app/sql/07_dashboard_views.sql

check:
	docker exec risk_summary_db psql -U user -d risk_db -f /app/sql/06_checks.sql
	docker run --rm --network credit-risk-summary_default -v /Users/qzqekensn/credit-risk-summary:/app -w /app python:3.10-slim sh -c "pip install PyYAML psycopg2-binary && python scripts/check_yaml_cols.py"

verify:
	docker run --rm --network credit-risk-summary_default -v /Users/qzqekensn/credit-risk-summary:/app -w /app python:3.10-slim sh -c "pip install pandas numpy psycopg2-binary && python scripts/verify.py"

export:
	python3 scripts/export.py
	python3 scripts/export_kpi.py

all: up load views check verify export
shot:
	pip install playwright && playwright install chromium
	python3 scripts/screenshot.py
