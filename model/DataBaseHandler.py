import sqlite3
import threading
import time
import random
import pandas as pd
import json


class DataBaseHandler:
    def __init__(self, db_path="database.db"):
        """Initialize SQLite database with threading lock for safe inserts."""
        self.db_path = db_path
        self.lock = threading.Lock()
        self.create_tables()

    def get_connection(self):
        """Retrieve a new database connection."""
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def create_tables(self):
        """Creates job postings table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_postings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                posting_id TEXT UNIQUE,
                posting_url TEXT UNIQUE,
                job_title TEXT,
                description TEXT,
                experience TEXT,
                employment_type TEXT,
                industries TEXT,
                agent_response TEXT,
                applied BOOLEAN DEFAULT 0,
                insert_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

    def execute_query_safe(self, query: str, values: list,
                           retries: int = 5, delay: float = .5) -> None:
        """Safely run query using locks and retry logic to prevent concurrency issues."""
        attempt = 0
        while attempt < retries:

            # Try with our threading lock
            try:
                with self.lock:
                    conn = self.get_connection()
                    cursor = conn.cursor()

                    # Execute the query
                    cursor.executemany(query, values)
                    conn.commit()
                    cursor.close()
                    conn.close()

                return

            # If we have problems with our threading lock, fallback to retry logic
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    attempt += 1

                    # Add jitter in the delay to prevent potential conention issues
                    time.sleep(delay * random.uniform(.8, 1.2))
                else:
                    raise

        print("Query failed after {} attempts".format(retries))

    def insert_jobs(self, job_list, retries=5, delay=0.5):
        """Insert new jobs into job table"""

        query = """
                    INSERT INTO job_postings (posting_url, posting_id, job_title, description,
                                              experience, employment_type, industries)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(posting_id) DO UPDATE SET
                        job_title=excluded.job_title, description=excluded.description,
                        experience=excluded.experience, employment_type=excluded.employment_type,
                        industries=excluded.industries
                """

        values = [(job["posting_url"], job["posting_id"], job["job_title"],
                   job["description"], job["experience"], job["employment_type"],
                   job["industries"]) for job in job_list]

        self.execute_query_safe(query, values)

        return

    def fetch_all_jobs(self):
        """Fetches all job postings."""
        conn = self.get_connection()
        data = pd.read_sql("SELECT * FROM job_postings", conn)
        conn.close()
        return data

    def fetch_recent_jobs(self, days=1):
        """Fetches job postings from the last 'days' days."""
        conn = self.get_connection()
        query = """
                    SELECT *
                    FROM job_postings
                    WHERE insert_timestamp >= datetime('now', '-{} days')
                """.format(
            days)
        data = pd.read_sql(query, conn)
        conn.close()
        return data

    def fetch_unprocessed_jobs(self):
        """Fetches job postings that need processing."""
        conn = self.get_connection()
        query = """
                    SELECT id, description
                    FROM job_postings
                    WHERE description IS NOT NULL AND agent_response IS NULL
                    AND description != ''
                """
        data = pd.read_sql(query, conn)
        conn.close()
        return data

    def update_agent_responses(self, response_dict):
        """Updates agent_response for job postings."""
        query = """
                    UPDATE job_postings
                    SET agent_response = ?
                    WHERE id = ?
                """

        # The agent response will be a python dict, so we need to convert it to a string
        values = [(response, job_id) for response, job_id in
                  zip(response_dict["agent_response"], response_dict["id"])]

        self.execute_query_safe(query, values)

        return

    def update_applied_status(self, applied_updates):
        """Updates the 'applied' status for job postings."""
        query = """
                    UPDATE job_postings
                    SET applied = ?
                    WHERE id = ?
                """
        values = [(int(applied), job_id) for job_id, applied in applied_updates]

        self.execute_query_safe(query, values)

        return
