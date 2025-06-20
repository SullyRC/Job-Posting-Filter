import streamlit as st
import json
import os
import time
from model.DataBaseHandler import DataBaseHandler
from model.data_enrichment import load_config, eval_on_loop, run_scrapers, process_unprocessed_jobs
from ui_components.agent_manger import agent
import threading
import queue

message_queue = queue.Queue()

for key in ["eval_running", "scrapers_running", "process_jobs_running",
            "eval_thread", "scrapers_thread", "process_jobs_thread"]:
    if key not in st.session_state:
        st.session_state[key] = False if "running" in key else None
eval_running_flag = False


def get_db_handler_and_config():
    """Helper function to initialize and return a DB handler and configuration."""
    config = load_config()
    db_handler = DataBaseHandler()
    return db_handler, config


def start_evaluation_loop():
    """Start the evaluation loop in a background thread."""
    if "eval_running" not in st.session_state:
        st.session_state.eval_running = False  # ✅ Ensure initialization before accessing

    if not st.session_state.eval_running:
        db_handler, config = get_db_handler_and_config()
        st.session_state.eval_running = True

        def loop_wrapper():
            global eval_running_flag
            eval_running_flag = True
            while eval_running_flag:
                eval_on_loop(config, agent, db_handler)
                time.sleep(30)  # Sleep between iterations

            print("✅ Evaluation loop gracefully exited.")

        thread = threading.Thread(target=loop_wrapper, daemon=True)
        thread.start()
        st.session_state.eval_thread = thread
        st.success("Evaluation loop started!")


def stop_evaluation_loop():
    """Stop the evaluation loop."""
    global eval_running_flag
    eval_running_flag = False
    st.session_state.eval_running = False
    if st.session_state.eval_thread is not None:
        st.session_state.eval_thread.join()
        st.session_state.eval_thread = None
        st.success("Evaluation loop stopped!")
    else:
        st.info("No evaluation loop is currently running.")


def start_scrapers():
    """Run scrapers once in a background thread."""
    if not st.session_state.scrapers_running:
        db_handler, config = get_db_handler_and_config()
        st.session_state.scrapers_running = True

        def scrapers_wrapper():
            run_scrapers(config, db_handler)  # 🔹 Runs once, no loop
            message_queue.put("Scrapers completed.")
            # st.session_state.scrapers_running = False  # Mark as stopped

        thread = threading.Thread(target=scrapers_wrapper, daemon=True)
        thread.start()
        st.session_state.scrapers_thread = thread
        st.info("Scrapers started!")


def start_process_jobs():
    """Process unprocessed jobs once in a background thread."""
    if not st.session_state.process_jobs_running:
        db_handler, config = get_db_handler_and_config()
        st.session_state.process_jobs_running = True

        def process_jobs_wrapper():
            process_unprocessed_jobs(agent, db_handler)  # 🔹 Runs once, no loop
            message_queue.put("Processing jobs completed.")
            # st.session_state.process_jobs_running = False  # Mark as stopped

        thread = threading.Thread(target=process_jobs_wrapper, daemon=True)
        thread.start()
        st.session_state.process_jobs_thread = thread
        st.info("Processing jobs started!")


def run_background_controller():
    """Build and display the Streamlit UI for background processing controls."""
    st.title("Background Process Controller")
    st.write("Use the buttons below to control background tasks for evaluation and enrichment.")

    # --- Allow user to edit the Agent config YAML
    st.sidebar.subheader("Agent Configuration")

    if not message_queue.empty():
        st.success(message_queue.get())

    # --- Background Process Session State ---
    if "eval_process" not in st.session_state:
        st.session_state.eval_process = None

    # --- Evaluation Loop Controls ---
    if st.button("Start Evaluation Loop"):
        start_evaluation_loop()

    if st.button("Stop Evaluation Loop"):
        stop_evaluation_loop()

    # --- One-Time Actions ---
    if st.button("Run Scrapers"):
        start_scrapers()

    if st.button("Process Unprocessed Jobs"):
        start_process_jobs()

    # --- Optional: Display Status ---
    st.write("### Background Process Status")
    if eval_running_flag:
        st.write("Evaluation Loop running:", eval_running_flag)
    else:
        st.write("Evaluation Loop is not running.")


def background_controller():
    """Exported function that builds the background-control UI.
    This function can be imported and called from a main file."""
    run_background_controller()


if __name__ == "__main__":
    background_controller()
