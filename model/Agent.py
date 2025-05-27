import yaml
import os
import re
from model.AgentInference import AgentInference  # Assuming AgentInference is defined separately


class Agent:
    def __init__(self, config_path="agent_config.yaml", prompt_dir="model/prompts"):
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
        self.root_node = self.config["root_node"]

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

    def check_black_list(self, current_question: str, question_data: dict, results: dict, description: str):
        """
        Function to check if the company is on the blacklist.
        :param current_question: Current question being evaluated.
        :param question_data: Config details for this question.
        :param results: Dictionary storing responses.
        :param description: The job description being analyzed.
        :return: 'Yes' if blacklisted, 'No' otherwise.
        """
        blacklist = question_data.get("blacklist", [])

        # Loop through blacklist to find a match in the job description
        response_text = "No"
        matched_company = None

        for company in blacklist:
            if company.lower() in description.lower():  # Case-insensitive match
                response_text = "Yes"
                matched_company = company
                break  # Stop looping as soon as we find a match

        # Store results
        results[current_question] = {
            "response": response_text,
            "explanation": f"The company '{matched_company}' is on the blacklist."
            if matched_company else
            "No blacklisted companies found in the description."
        }

        return response_text

    def query_llm(self, current_question: str, question_data: dict,
                  results: dict, description: str):
        """Function for querying the llm for response"""
        prompt_id = question_data.get("prompt", question_data.get("prompt_id"))
        instruction_text = self._load_prompt(prompt_id)

        llm_response = self.agent_inference.generate_with_instructions(
            instruction_text, description)
        parsed_data = self._extract_data(llm_response, question_data["return_payload"])

        # Store results
        results[current_question] = parsed_data

        # Determine next question based on response
        response_text = parsed_data.get("response", "")

        # Strip the response text if we got it
        if response_text:
            response_text = response_text.strip()

        # Otherwise return an empty string
        else:
            response_text = ""

        return response_text

    def ask_questions(self, description: str):
        """Traverses the decision tree, asking structured questions based on responses."""
        results = {}
        current_question = self.root_node  # Start from root node

        try:

            while current_question:
                print(current_question)
                question_data = self.config["Agent_questions"].get(current_question)

                if not question_data:
                    print(f"Error: Question '{current_question}' is missing in config.")
                    break

                method_name = question_data['function']
                function_ref = getattr(self, method_name, None)  # Get method reference

                if function_ref and callable(function_ref):  # Ensure it's a valid method
                    response_text = function_ref(
                        current_question, question_data, results, description)
                else:
                    raise ValueError(f"Error: Function '{method_name}' not found or not callable.")

                # output our response
                print(response_text)

                # Get our next question if we have one
                next_question = question_data.get("children", {}).get(response_text)

                if not next_question:
                    break  # Stop traversing if there's no child for the given response

                current_question = next_question  # Move to next node in the tree

        # Catch any error so that we can return the results
        except Exception as e:
            print("Unexpected outcome when evaluating question {}: {}".format(current_question,
                                                                              e))

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

    agent.prompt_dir = 'prompts'
    agent.config = agent._load_agent_config()
