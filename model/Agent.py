import yaml
import os
import re
from model.AgentInference import AgentInference  # Assuming AgentInference is defined separately


class Agent:
    def __init__(self, config_path="agent_config.yaml", prompt_dir="prompts"):
        """
        Initializes the Agent by loading configurations and preparing inference.
        :param config_path: Path to the YAML configuration file.
        :param prompt_dir: Directory containing text prompts.
        """
        self.config_path = config_path
        self.prompt_dir = prompt_dir
        self.agent_inference = AgentInference()  # Initialize LLM inference

        # Load YAML configuration
        self.config = self._load_agent_config()

    def _load_agent_config(self):
        """Loads the agent's YAML configuration file."""
        with open(self.config_path, "r") as file:
            return yaml.safe_load(file)

    def _load_prompt(self, prompt_id):
        """Fetches the prompt file based on prompt_id."""
        prompt_path = os.path.join(self.prompt_dir, f"{prompt_id}.txt")
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        with open(prompt_path, "r") as file:
            return file.read().strip()

    def _extract_data(self, text, regex_patterns):
        """Extracts response and explanation using regex."""
        extracted_data = {}
        for key, pattern in regex_patterns.items():
            match = re.search(pattern, text)
            extracted_data[key] = match.group(1) if match else None
        return extracted_data

    def ask_questions(self, description: str):
        """Processes configured questions and extracts LLM responses."""
        results = {}

        for question, question_data in self.config["Agent_questions"].items():
            instruction_text = self._load_prompt(question_data["prompt_id"])
            llm_response = self.agent_inference.generate_with_instructions(instruction_text,
                                                                           description)

            parsed_data = self._extract_data(llm_response, question_data["return_payload"])
            results[question] = parsed_data

        return results


# Example usage
if __name__ == "__main__":
    agent = Agent()
    parsed_results = agent.ask_questions(
        'Dice is the leading career destination for tech experts at every stage of their careers. Our client, Zensark Inc, is seeking the following. Apply via Dice today!\n\nJob Summary:\n\nJoin a dynamic team to drive end-to-end machine learning (ML) projects from design to deployment and continuous improvement.\n\n\n\n\n\n\n\nShow more\nSeniority level\nMid-Senior level\nEmployment type\nFull-time\nJob function\nEngineering and Information Technology\nIndustries\nHospitals and Health Care, Non-profit Organizations, and Government Administration\nReferrals increase your chances of interviewing at Jobs via Dice by 2x\nSee who you know'
    )

    for question, data in parsed_results.items():
        print(f"🔹 {question}")
        print(f"  - Response: {data['response']}")
        print(f"  - Explanation: {data['explanation']}")
