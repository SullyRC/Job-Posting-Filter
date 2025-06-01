import streamlit as st
import json
import os
import multiprocessing
import time
from model.DataBaseHandler import DataBaseHandler
from model.data_enrichment import load_config, eval_on_loop, run_scrapers, process_unprocessed_jobs
from ui_components.agent_manger import agent
import torch

torch.classes.__path__ = []


def get_db_handler_and_config():
    """Helper function to initialize and return a DB handler and configuration."""
    db_auth = json.loads(os.environ.get('DataBaseAuth', '{}'))
    config = load_config()  # load_config is defined in your main module.
    # Set pool size to the number of scraper classes or another appropriate value.
    pool_size = len(config.get('scraper_config', {}).get('classes', {}).keys())
    db_handler = DataBaseHandler(db_auth, pool_size=pool_size)
    return db_handler, config


def run_background_controller():
    """Build and display the Streamlit UI for background processing controls."""
    st.title("Background Process Controller")
    st.write("Use the buttons below to control background tasks for evaluation and enrichment.")

    # --- Allow user to edit the Agent config YAML
    st.sidebar.subheader("Agent Configuration")

    # --- Background Process Session State ---
    if "eval_process" not in st.session_state:
        st.session_state.eval_process = None

    # --- Evaluation Loop Controls ---
    if st.button("Start Evaluation Loop"):
        if (st.session_state.eval_process is None) or (not st.session_state.eval_process.is_alive()):
            db_handler, config = get_db_handler_and_config()
            # Launch eval_on_loop => note that this function is long-running.
            p = multiprocessing.Process(target=eval_on_loop, args=(agent, db_handler))
            p.start()
            st.session_state.eval_process = p
            st.success("Evaluation loop started in the background.")
        else:
            st.info("Evaluation loop is already running.")

    if st.button("Stop Evaluation Loop"):
        if st.session_state.eval_process is not None and st.session_state.eval_process.is_alive():
            st.session_state.eval_process.terminate()
            st.session_state.eval_process.join()  # Ensure the process terminates
            st.session_state.eval_process = None
            st.success("Evaluation loop stopped.")
        else:
            st.info("No evaluation loop is currently running.")

    # --- One-Time Actions ---
    if st.button("Run Scrapers"):
        db_handler, config = get_db_handler_and_config()
        p = multiprocessing.Process(target=run_scrapers, args=(config, db_handler))
        p.start()
        p.join()  # Wait for completion
        st.success("Scrapers executed successfully.")

    if st.button("Process Unprocessed Jobs"):
        db_handler, config = get_db_handler_and_config()
        p = multiprocessing.Process(target=process_unprocessed_jobs, args=(agent, db_handler))
        p.start()
        p.join()
        st.success("Processing of unprocessed jobs completed.")

    # --- Optional: Display Status ---
    st.write("### Background Process Status")
    if st.session_state.eval_process is not None:
        st.write("Evaluation Loop running:", st.session_state.eval_process.is_alive())
    else:
        st.write("Evaluation Loop is not running.")


def background_controller():
    """Exported function that builds the background-control UI.
    This function can be imported and called from a main file."""
    run_background_controller()


if __name__ == "__main__":
    background_controller()
