import mysql.connector
import pandas as pd

class DataBaseHandler:
    def __init__(self, sql_auth):
        """Initialize database connection."""
        self.conn = mysql.connector.connect(
            **sql_auth
        )
        self.cursor = self.conn.cursor(dictionary=True)  # Enables returning dict-based query results
        self.create_table()

    def create_table(self):
        """Creates the job postings table with an insert timestamp."""
        self.cursor.execute("""
                            CREATE TABLE IF NOT EXISTS job_postings (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                posting_url VARCHAR(512) UNIQUE,
                                job_title TEXT,
                                description TEXT,
                                experience TEXT,
                                employment_type TEXT,
                                industries TEXT,
                                insert_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                )
                            """)
        self.conn.commit()

    def insert_jobs(self, job_list):
        """Bulk inserts multiple job postings into the database."""
        query = """
            INSERT INTO job_postings (posting_url, job_title, description,
                                      experience, employment_type, industries)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
        values = [
            (job["posting_url"], job["job_title"], job["description"], 
             job["experience"], job["employment_type"], job["industries"])
            for job in job_list
            ]

        try:
            self.cursor.executemany(query, values)
            self.conn.commit()
        except mysql.connector.IntegrityError:
            print("Skipping duplicate entries.")

    def fetch_all_jobs(self):
        """Fetches all job postings from the database."""
        self.cursor.execute("SELECT * FROM job_postings")
        return pd.DataFrame(self.cursor.fetchall())

    def close(self):
        """Closes database connection."""
        self.cursor.close()
        self.conn.close()

    def fetch_recent_jobs(self, days=1):
        """Fetches job postings added in the last 'days' days."""
        query = f"SELECT * FROM job_postings WHERE insert_timestamp >= NOW() - INTERVAL {days} DAY"
        self.cursor.execute(query)
        return pd.DataFrame(self.cursor.fetchall())