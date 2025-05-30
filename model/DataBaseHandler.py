import mysql.connector
import pandas as pd
from mysql.connector import pooling


class DataBaseHandler:
    def __init__(self, sql_auth, pool_size=5):
        """Initialize connection pool for multi-process usage."""
        self.pool = pooling.MySQLConnectionPool(
            pool_name="job_pool",
            pool_size=pool_size,
            **sql_auth
        )
        self.create_tables()

    def get_connection(self):
        """Retrieve a fresh connection from the pool."""
        return self.pool.get_connection()

    def create_tables(self):
        """Creates the job postings table."""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_postings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                posting_id VARCHAR(100) UNIQUE,
                posting_url VARCHAR(512) UNIQUE,
                job_title TEXT,
                description TEXT,
                experience TEXT,
                employment_type TEXT,
                industries TEXT,
                agent_response JSON,
                applied BOOLEAN DEFAULT FALSE,
                insert_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

    def insert_jobs(self, job_list):
        """Bulk inserts job postings using pooled connections."""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            INSERT INTO job_postings (posting_url, posting_id, job_title, description,
                                      experience, employment_type, industries)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            job_title=VALUES(job_title), description=VALUES(description),
            experience=VALUES(experience), employment_type=VALUES(employment_type),
            industries=VALUES(industries)
        """

        values = [(job["posting_url"], job["posting_id"], job["job_title"], job["description"],
                   job["experience"], job["employment_type"], job["industries"]) for job in job_list]

        try:
            cursor.executemany(query, values)
            conn.commit()
        except mysql.connector.IntegrityError:
            print("Skipping duplicate entries.")

        cursor.close()
        conn.close()

    def fetch_all_jobs(self):
        """Fetches all job postings using pooled connections."""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM job_postings")
        data = pd.DataFrame(cursor.fetchall())
        cursor.close()
        conn.close()
        return data

    def fetch_recent_jobs(self, days=1):
        """Fetches job postings from the last 'days' days."""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT * FROM job_postings WHERE insert_timestamp >= NOW() - INTERVAL {days} DAY"
        cursor.execute(query)
        data = pd.DataFrame(cursor.fetchall())
        cursor.close()
        conn.close()
        return data

    def fetch_unprocessed_jobs(self):
        """Fetches job postings that need processing."""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT id, description FROM job_postings
            WHERE description IS NOT NULL AND agent_response IS NULL
        """
        cursor.execute(query)
        data = pd.DataFrame(cursor.fetchall())
        cursor.close()
        conn.close()
        return data

    def update_agent_responses(self, response_dict):
        """Updates agent_response for job postings."""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """UPDATE job_postings SET agent_response = %s WHERE id = %s"""
        values = list(zip(response_dict["agent_response"], response_dict["id"]))

        try:
            cursor.executemany(query, values)
            conn.commit()
        except mysql.connector.Error as e:
            print("Error updating agent responses:", e)

        cursor.close()
        conn.close()

    def update_applied_status(self, applied_updates):
        """Updates the 'applied' status for job postings."""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """UPDATE job_postings SET applied = %s WHERE id = %s"""
        formatted_updates = [(int(applied), job_id) for job_id, applied in applied_updates]

        try:
            cursor.executemany(query, formatted_updates)  # Batch update multiple rows
            conn.commit()
        except mysql.connector.Error as e:
            print(f"❌ Error updating applied status: {e}")

        cursor.close()
        conn.close()
