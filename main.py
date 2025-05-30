import yaml
from model.scraper import LinkedInScraper, DiceScraper
from model.DataBaseHandler import DataBaseHandler
from model.Agent import Agent
import json
import pandas as pd
import numpy as np
import datetime
import os
import time
import sys
import multiprocessing


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
    """Executes scrapers in parallel using multiprocessing."""
    processes = []

    for scraper_name, data in config['scraper_config']['classes'].items():
        process = multiprocessing.Process(target=run_individual_scraper,
                                          args=(scraper_name, data, db_handler))
        processes.append(process)
        process.start()

    # Wait for all processes to complete
    for process in processes:
        process.join()

    print("All scrapers completed.")


def run_individual_scraper(scraper_name, config, db_handler):
    """Execute a single scraper instance in a separate process."""
    print(f"Starting scraper: {scraper_name}")

    scraper_class = eval(scraper_name)  # Convert string to class reference
    scraper = scraper_class(db_handler, config)

    scraper.parse_all_searches()
    scraper.close()


def process_unprocessed_jobs(agent: Agent, db_handler: DataBaseHandler):
    """
    Fetches all unprocessed job descriptions and evaluates them using the agent.
    Updates agent_response in the database.
    """
    jobs_df = db_handler.fetch_unprocessed_jobs()
    if jobs_df.empty:
        print("No unprocessed jobs found.")
        return

    response_dict = {"id": [], "agent_response": []}

    # Get unique descriptions to avoid redundant processing
    unique_descriptions = jobs_df['description'].unique()
    agent_responses = {}

    for idx, description in enumerate(unique_descriptions):
        # Live progress update using `sys.stdout.write()`
        progress = f"\rProcessing {idx + 1}/{len(unique_descriptions)} descriptions..."
        sys.stdout.write(progress)
        sys.stdout.flush()

        response = agent.ask_questions(description)
        agent_responses[description] = json.dumps(response)

    print("\nProcessing complete!")

    # Merge responses back with job postings
    jobs_df["agent_response"] = jobs_df["description"].map(agent_responses)

    # Prepare data for database update
    response_dict["id"] = jobs_df["id"].tolist()
    response_dict["agent_response"] = jobs_df["agent_response"].tolist()

    db_handler.update_agent_responses(response_dict)
    print("Successfully updated agent responses in the database.")


def main():
    config = load_config()
    if not config:
        return

    # Initialize components with config if necessary
    db_handler = DataBaseHandler(json.loads(os.environ.get('DataBaseAuth', '{}')),
                                 pool_size=len(config['scraper_config']['classes'].keys()))

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
    # main()
    config = load_config()

    # Initialize components with config if necessary
    db_handler = DataBaseHandler(json.loads(os.environ.get('DataBaseAuth', '{}')),
                                 pool_size=2)
    run_scrapers(config, db_handler)
