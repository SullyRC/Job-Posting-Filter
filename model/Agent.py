import yaml
import os
import re
import fitz
import docx

from model.AgentInference import ApiAgentInference, DeviceAgentInference


class Agent:
    def __init__(self, config_path="agent_config.yaml", prompt_dir="model/prompts"):
        """
        Initializes the Agent by loading configurations and preparing inference.
        :param config_path: Path to the YAML configuration file.
        :param prompt_dir: Directory containing text prompts.
        """
        self.config_path = config_path
        self.prompt_dir = prompt_dir

        # Load YAML configuration
        self.config = self._load_agent_config()
        self.root_node = self.config["root_node"]
        self.load_additional_context()

        inference_method = self.config['InferenceMethod']

        print(self.config[inference_method])
        # This can take a while to load if in device mode
        self.agent_inference = eval(inference_method)(**self.config[inference_method])

    def load_additional_context(self):
        """Loads additional context specified in the configuration file."""
        additional_context = {}

        if 'additional_context' in self.config.keys():
            for key, value in self.config['additional_context'].items():
                file_extension = os.path.splitext(value)[1].lower()

                file = os.path.join(self.prompt_dir, value)

                # 🔹 Handle PDF resumes
                if file_extension == ".pdf":
                    try:
                        doc = fitz.open(file)  # Load PDF
                        extracted_text = ""
                        for page in doc:
                            extracted_text += page.get_text("text") + "\n"

                        additional_context[key] = extracted_text.strip()
                    except Exception as e:
                        print(f"Error loading PDF ({value}): {e}")
                        additional_context[key] = None

                elif file_extension == ".txt":
                    with open(file, "r", encoding="utf-8") as f:
                        additional_context[key] = f.read().strip()

                elif file_extension == ".docx":
                    try:
                        doc = docx.Document(file)
                        extracted_text = "\n".join([para.text for para in doc.paragraphs])
                        additional_context[key] = extracted_text.strip()
                    except Exception as e:
                        print(f"Error loading DOCX ({value}): {e}")
                        additional_context[key] = None

                # 🔹 Handle other formats (future expansion)
                else:
                    print(f"Unsupported file type for {key}: {file_extension}")

        self.additional_context = additional_context  # Store extracted data

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
            if key == 'Response':
                patterns = [
                    '(.*?)\s*\[EndResponse\]',
                    '(.*?)\s*\[EndAssistant\]',
                    '(.*?)\s*\[Explanation]',
                    pattern
                ]
                extracted_data[key] = None
                for pat in patterns:
                    match = re.search(pat, text)
                    if match:
                        extracted_data[key] = match.group(1)
            else:
                match = re.search(pattern, text)
                extracted_data[key] = match.group(1) if match else None
        return extracted_data

    def check_text_list(self, current_question: str, question_data: dict, results: dict, description: str):
        """
        Function to check if the description contains text from a predefined list or additional context file.
        :param current_question: Current question being evaluated.
        :param question_data: Config details for this question.
        :param results: Dictionary storing responses.
        :param description: The job description being analyzed.
        :return: 'Yes' if a match is found, 'No' otherwise.
        """
        textlist = question_data.get("textlist", [])

        # 🔹 Check if additional context specifies a text file
        additional_context = question_data.get("additional_context")
        for additional_context_key in additional_context:
            if additional_context_key and additional_context_key in self.additional_context:
                textlist.extend(self.additional_context[additional_context_key].split(','))

        response_text = "No"
        matched_text = None

        print(textlist)
        # 🔹 Case-insensitive matching against description
        for term in textlist:
            if term.lower().strip() in description.lower():
                response_text = "Yes"
                matched_text = term
                break  # Stop looping once a match is found

        # 🔹 Store results with a neutral explanation format
        results[current_question] = {
            "response": response_text,
            "explanation": f"The term '{matched_text}' was found in the description."
            if matched_text else
            "No matches found from the provided text list."
        }

        return response_text

    def query_llm(self, current_question: str, question_data: dict,
                  results: dict, description: str):
        """Function for querying the llm for response"""
        prompt_id = question_data.get("prompt", question_data.get("prompt_id"))
        instruction_text = self._load_prompt(prompt_id)

        # get a copy of our description to inject context into
        enriched_description = description

        if 'additional_context' in question_data.keys():
            context_block = "\n".join([
                value.format(self.additional_context[key])
                for key, value in question_data['additional_context'].items()
                if key in self.additional_context and self.additional_context[key]
            ])
            enriched_description = context_block + "\n" + enriched_description

        llm_response = self.agent_inference.generate(
            instruction_text, enriched_description)

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
            response_text = "Error"

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

                    # Check if we have a continue key
                    next_question = question_data.get("children", {}).get("Continue")

                    # We stop processing
                    if not next_question:
                        break

                # Move to next node in the tree
                current_question = next_question

        # Catch any error so that we can return the results
        except Exception as e:
            print("Unexpected outcome when evaluating question {}: {}".format(current_question,
                                                                              e))

        return results


# Example usage
if __name__ == "__main__":
    agent = Agent(prompt_dir='prompts')
    parsed_results = agent.ask_questions(
        """
        About the job
You could be a anywhere. Why us?

Join a pre-IPO startup with capital, traction and runway ($240M funded | 60X revenue growth in 5 years | $2T market size)
Report directly to our Director of BizOps & Analytics, Qingdi Huang (Ex-Bain)
Disrupt a massive market and take us to a $10B business in the next few years
Be immersed in a talent-dense environment and greatly accelerate your career growth

About The Opportunity

Jerry is looking for a Data scientist to join our growing team! We hit a huge milestone in early 2024 by achieving profitability and have ambitious goals for the next few years — scale from 5M to 50M customers and become a $10B business. As a data scientist, you will play a key role in championing data-driven decisions across the company, with a focus on optimizing growth channels such as partnerships, marketing, and automation. Reporting directly to the Director BizOps/Analytics, you will leverage advanced machine learning models to conduct in-depth analyses and extract insights that will shape our growth strategies.

Jerry is building the first super app to make car ownership affordable and accessible – insurance, buy/sell, registration, loans, safety, repairs, parking, etc – a $2T market in the U.S. We started with insurance in 2019, and since then we’ve launched loan refinancing, driving insights, repair marketplace, car diagnostics, and a GenAI-powered chatbot & voicebot. We have amassed over 5M customers, raised $240MM in funding, scaled our revenue 60X and our team to 225 across 6 countries.

How You Will Make An Impact

Partner with marketing, product, and business development teams to integrate customer performance insights into user and partner acquisition strategies
Lead the design, execution, and analysis of A/B experiments on new and existing features, extracting key insights to inform product and business strategies
Define, understand, and test levers to drive profitable and scalable user acquisition and partnership growth
Identify opportunities to automate manual processes and optimize operational efficiency 

Preferred Experience

Bachelor’s degree in a quantitatively or intellectually rigorous discipline
1-3 years of management consulting experience from a top firm (McKinsey, Bain, and Boston Consulting Group preferred) OR relevant experience in data science/business analysis
High level of comfort with SQL or Python

Who You Are

You have a framework for problem solving and live by first principles
You are comfortable communicating with audiences varying from front-line employees to the company’s C-suite
You set a very high bar for yourself and for your team, and you are constantly pushing that bar higher in the pursuit of excellence

While we appreciate your interest and application, only applicants under consideration will be contacted.

Jerry.ai is proud to be an Equal Employment Opportunity employer. We prohibit discrimination based on race, religion, color, national origin, sex, pregnancy, reproductive health decisions or related medical conditions, sexual orientation, gender identity, gender expression, age, veteran status, disability, genetic information, or other characteristics protected by applicable local, state or federal laws. 

Jerry.ai is committed to providing reasonable accommodations for individuals with disabilities in our job application process. If you need assistance or an accommodation due to a disability, please contact us at recruiting@jerry.ai

About Jerry.ai

Jerry.ai is America’s first and only super app to radically simplify car ownership. We are redefining how people manage owning a car, one of their most expensive and time-consuming assets.

Backed by artificial intelligence and machine learning, Jerry.ai simplifies and automates owning and maintaining a car while providing personalized services for all car owners' needs. We spend every day innovating and improving our AI-powered app to provide the best possible experience for our customers. From car insurance and financing to maintenance and safety, Jerry.ai does it all.

We are the #1 rated and most downloaded app in our category with a 4.7 star rating in the App Store. We have more than 5 million customers — and we’re just getting started.

Jerry.ai was founded in 2017 by serial entrepreneurs and has raised more than $240 million in financing.

Join our team and work with passionate, curious and egoless people who love solving real-world problems. Help us build a revolutionary product that’s disrupting a massive market.
        """)

    for question, data in parsed_results.items():
        print(f"🔹 {question}")
        print(f"  - Response: {data['response']}")
        print(f"  - Explanation: {data['explanation']}")

    agent.config = agent._load_agent_config()
