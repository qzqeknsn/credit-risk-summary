import yaml
import psycopg2
import sys
import os

def main():
    yaml_path = 'semantic/portfolio.yml'
    conn_str = os.environ.get("DB_URL", "postgresql://user:password@risk_summary_db:5432/risk_db")

    try:
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading YAML: {e}")
        sys.exit(1)

    # Extract column names from YAML
    columns_in_yaml = []

    # Extract from dimensions
    if 'dimensions' in config:
        for dim in config['dimensions']:
            if 'column' in dim:
                columns_in_yaml.append(dim['column'])

    # Extract from measures
    if 'measures' in config:
        for meas in config['measures']:
            if 'column' in meas:
                columns_in_yaml.append(meas['column'])

    if not columns_in_yaml:
        print("No columns found in YAML dimensions or measures")
        sys.exit(1)

    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'reporting'
              AND table_name = 'v_loans_clean'
        """)
        db_cols = {row[0] for row in cur.fetchall()}
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")
        sys.exit(1)

    missing = [col for col in columns_in_yaml if col not in db_cols]
    if missing:
        print(f"Missing columns in v_loans_clean: {', '.join(missing)}")
        sys.exit(1)

    print("All YAML columns found in v_loans_clean")
    sys.exit(0)

if __name__ == "__main__":
    main()
