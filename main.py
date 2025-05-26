import yaml
from model.scraper import LinkedInScraper
from model.DataBaseHandler import DataBaseHandler
from model.Agent import Agent
import json
import pandas as pd
import numpy as np
import datetime
import os
import time


def load_config(config_path="config.yaml"):
    """Loads configuration file."""
    try:
        with open(config_path, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print("Error: config.yaml not found!")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing config.yaml: {e}")
        return None


def schedule_functions(config, current_vars: dict):
    """Executes scheduled functions dynamically based on config.yaml."""
    current_minute = datetime.datetime.now().minute

    for scheduled_minute, functions in config.get("schedule", {}).items():
        if current_minute == int(scheduled_minute):
            for function in functions:
                if function in config.get("functions", {}):
                    try:
                        # Retrieve function parameters dynamically
                        params = [current_vars[param] for param in config["functions"][function]]
                        print(f"Running function: {function}")
                        eval(function)(*params)
                    except KeyError as e:
                        print(f"Error: Missing parameter '{e}' for function '{function}'")
                    except Exception as e:
                        print(f"Unexpected error running '{function}': {e}")
                else:
                    print(f"Warning: Function '{function}' not defined in config['functions']")


def run_scrapers(config: dict, db_handler: DataBaseHandler):
    """Executes scrapers based on config settings."""
    for scraper_name, data in config['scraper_config']['classes'].items():
        print(f"Scraping using {scraper_name}")
        scraper = eval(scraper_name)(db_handler, data)
        scraper.parse_all_searches()
        scraper.close()


def process_unprocessed_jobs(agent: Agent, db_handler: DataBaseHandler):
    """
    Fetches all unprocessed job descriptions and evaluates them using the agent.
    Updates agent_response in the database.
    """
    # Fetch job postings where description exists but agent_response is NULL
    jobs_df = db_handler.fetch_unprocessed_jobs()

    if jobs_df.empty:
        print("No unprocessed jobs found.")
        return

    # Process each job description using the agent
    response_dict = {"id": [], "agent_response": []}

    for _, row in jobs_df.iterrows():
        job_id = row["id"]
        description = row["description"]

        print(f"Processing Job ID: {job_id}")
        response = agent.ask_questions(description)

        response_dict["id"].append(job_id)
        response_dict["agent_response"].append(json.dumps(response))  # Store as JSON

    # Update database with processed agent responses
    db_handler.update_agent_responses(response_dict)
    print("Successfully updated agent responses in the database.")


def main():
    config = load_config()
    if not config:
        return

    # Initialize components with config if necessary
    db_handler = DataBaseHandler(json.loads(
        os.environ['DataBaseAuth']))

    description_eval = Agent('model/agent_config.yaml',
                             'model/prompts')
    current_vars = {
        'config': config,
        'db_handler': db_handler,
        'agent': description_eval
    }
    while True:
        schedule_functions(config, current_vars)
        time.sleep(30)

    # Initialize components with config if necessary
    # agent = Agent(config_path=config["agent_config"])

    # Example usage (modify as needed)
    jobs_to_process = db_handler.fetch_unprocessed_jobs()
    print("Unprocessed Jobs:", jobs_to_process)


if __name__ == "__main__":
    main()
