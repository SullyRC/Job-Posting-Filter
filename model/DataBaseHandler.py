import mysql.connector
import pandas as pd


class DataBaseHandler:
    def __init__(self, sql_auth):
        """Initialize database connection."""
        self.conn = mysql.connector.connect(
            **sql_auth
        )
        # Enables returning dict-based query results
        self.cursor = self.conn.cursor(dictionary=True)
        self.create_tables()

    def create_tables(self):
        """Creates the job postings table with an insert timestamp."""
        self.cursor.execute("""
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
        self.conn.commit()

    def insert_jobs(self, job_list):
        """Bulk inserts multiple job postings into the database."""
        query = """INSERT INTO job_postings (posting_url, posting_id, job_title, description,
                                    experience, employment_type, industries)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE
           job_title=VALUES(job_title), description=VALUES(description),
           experience=VALUES(experience), employment_type=VALUES(employment_type),
           industries=VALUES(industries)"""
        values = [
            (job["posting_url"], job["posting_id"], job["job_title"], job["description"],
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

    def fetch_unprocessed_jobs(self):
        """Fetches job postings where description exists but agent_response is NULL."""
        query = """
        SELECT id, description FROM job_postings
        WHERE description IS NOT NULL AND agent_response IS NULL
        """
        self.cursor.execute(query)
        return pd.DataFrame(self.cursor.fetchall())

    def update_agent_responses(self, response_dict):
        """
        Updates agent_response for given job_posting IDs.

        :param response_dict: Dictionary containing lists of 'id' and 'agent_response'.
        """
        query = """
            UPDATE job_postings
            SET agent_response = %s
            WHERE id = %s
            """

        values = list(zip(response_dict["agent_response"], response_dict["id"]))

        try:
            self.cursor.executemany(query, values)
            self.conn.commit()
        except mysql.connector.Error as e:
            print("Error updating agent responses:", e)

        return

    def update_applied_status(self, applied_updates):
        """
        Updates the 'applied' status for given job postings.

        :param applied_updates: List of tuples [(id, applied_status)] where 'id' is the job ID.
        """
        query = """
            UPDATE job_postings 
            SET applied = %s 
            WHERE id = %s
            """

        # Convert True/False to 1/0 for MySQL
        formatted_updates = [(int(applied), job_id) for job_id, applied in applied_updates]

        try:
            self.cursor.executemany(query, formatted_updates)  # Batch update multiple rows
            self.conn.commit()
        except mysql.connector.Error as e:
            print(f"❌ Error updating applied status: {e}")
