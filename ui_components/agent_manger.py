import streamlit as st
import yaml
from model.Agent import Agent


@st.cache_resource(show_spinner=False)
def load_agent(agent_config_path="model/agent_config.yaml", prompts_dir="model/prompts"):
    # Simulate a heavy load (if needed) and then load the agent.
    with open(agent_config_path, "r") as f:
        _ = yaml.safe_load(f)
    return Agent(agent_config_path, prompts_dir)


def get_agent_with_warning():
    # Create an empty placeholder for the warning
    warning_placeholder = st.empty()
    # Display a warning or information message that the agent is loading.
    warning_placeholder.warning("Loading Agent... This may take up to 5 minutes.")

    # Alternatively, you can use a spinner context which displays temporary text.
    # with st.spinner("Loading Agent... This may take a while."):
    #     agent = load_agent()

    # Here, we just load the agent using our cached function.
    agent = load_agent()

    # Once the agent is loaded, clear the placeholder
    warning_placeholder.empty()
    st.success("Agent loaded!")
    return agent


# Global agent can be loaded once:
agent = get_agent_with_warning()
