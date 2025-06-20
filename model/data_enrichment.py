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
import threading


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
    """Executes scrapers in parallel using multithreading."""
    threads = []
    for scraper_name in config['scraper_config']['classes'].keys():
        thread = threading.Thread(target=run_individual_scraper, args=(scraper_name,
                                                                       config,
                                                                       db_handler))
        thread.start()
        threads.append(thread)

    # ✅ Wait for all threads to complete
    for thread in threads:
        thread.join()

    print("All scrapers completed.")


def run_individual_scraper(scraper_name, config, db_handler):
    """Execute a single scraper instance in a separate process."""
    print(f"Starting scraper: {scraper_name}")
    scraper_class = eval(scraper_name)  # Convert string to class reference
    scraper = scraper_class(db_handler, config['scraper_config']['classes'][scraper_name])

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


def eval_on_loop(config: dict = None,
                 description_eval: Agent = None, db_handler: DataBaseHandler = None):

    if not config:
        config = load_config()

    if not db_handler:
        # Initialize components with config if necessary
        db_handler = DataBaseHandler()

    if not description_eval:
        description_eval = Agent('model/agent_config.yaml',
                                 'model/prompts')
    current_vars = {
        'config': config,
        'db_handler': db_handler,
        'agent': description_eval
    }
    schedule_functions(config, current_vars)

    return


if __name__ == "__main__":
    config = load_config('../config.yaml')
    db_handler = DataBaseHandler('../database.db')
    # eval_on_loop(config=config, db_handler=db_handler)
