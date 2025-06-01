import streamlit as st
import yaml
from model.Agent import Agent


@st.cache_resource(show_spinner=False)
def get_agent(agent_config_path="model/agent_config.yaml", prompts_dir="model/prompts"):
    # Loads the agent only once, even if called in multiple places.
    with open(agent_config_path, "r") as f:
        _ = yaml.safe_load(f)  # You can log or validate the config here if desired.
    return Agent(agent_config_path, prompts_dir)


# Global variable used across all modules
agent = get_agent()
