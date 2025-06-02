import re
import time
import os
import gc
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from mistralai import Mistral

torch.classes.__path__ = [os.path.join(torch.__path__[0], torch.classes.__file__)]


class AgentInference:
    def __init__(self, mistral_api=True, model_name="google/gemma-2-2b-it", model_dir="llms"):
        """
        Initializes LLM inference model (either API-based or local).
        :param mistral_api: Whether to use Mistral API instead of local model.
        :param model_name: Hugging Face model identifier.
        :param model_dir: Directory for local models.
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_dir = model_dir
        self.model_name = model_name
        self.mistral_api = mistral_api
        self.mistral_model = "ministral-3b-latest"

        if mistral_api:
            # 🔹 Initialize API client
            self.api_key = os.environ.get("mistral_token", None)
            if not self.api_key:
                raise ValueError(
                    "Mistral API key missing! Set 'mistral_token' in environment variables.")
            self.client = Mistral(api_key=self.api_key)
        else:
            # 🔹 Load local model
            os.makedirs(self.model_dir, exist_ok=True)
            model_kwargs = {'device_map': 'auto', 'cache_dir': self.model_dir}
            if "gemma" in model_name.lower():
                model_kwargs['quantization_config'] = BitsAndBytesConfig(load_in_8bit=True)

            self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=self.model_dir)
            self.model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)

    def generate_on_device(self, instructions_prompt, data_prompt, max_tokens=200):
        """
        Generates a response locally using the on-device model.
        :param prompt: Input prompt text.
        :param max_tokens: Maximum token length for response.
        :return: Decoded response string.
        """
        prompt = self.format_prompt(instructions_prompt, data_prompt)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        outputs = self.model.generate(
            **inputs, max_new_tokens=max_tokens, do_sample=False, temperature=0, top_p=1, top_k=0, use_cache=True
        )
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Free memory
        del inputs, outputs
        torch.cuda.empty_cache()
        gc.collect()

        return response

    def generate_via_api(self, instructions_prompt, data_prompt, max_tokens=200):
        """
        Generates a response via Mistral API.
        :param prompt: Input text prompt.
        :param max_tokens: Max tokens for response.
        :return: API response string.
        """
        data_prompt_enriched = f"[Description]{data_prompt}[EndDescription][Response]"
        messages = [
            {
                "role": "system",
                "content": instructions_prompt, },
            {
                "role": "user",
                "content": data_prompt_enriched,
            }
        ]
        response = self.client.chat.complete(
            model=self.mistral_model, messages=messages, max_tokens=max_tokens,
            temperature=.01, n=1)
        return response.choices[0].message.content.strip()  # Extract response text

    def generate_response(self, instructions_prompt, data_prompt, max_tokens=200):
        """
        Generates response using API if enabled, else on-device model.
        """
        if self.mistral_api:
            return self.generate_via_api(instructions_prompt, data_prompt, max_tokens)
        return self.generate_on_device(instructions_prompt, data_prompt, max_tokens)

    def format_prompt(self, instructions_prompt, data_prompt):
        """
        Formats system prompt and user prompt based on model type.
        """
        if "gemma" in self.model_name.lower():
            return f"<system>{instructions_prompt}</system><user>[Description]{data_prompt}[EndDescription]</user><assistant>[Response]"
        elif "llama" in self.model_name.lower():
            return f"<bos><start_of_turn>user{instructions_prompt}[Description]{data_prompt}[EndDescription]<end_of_turn>\n<start_of_turn>model"
        else:
            raise ValueError("Unsupported model type. Use Gemma or Llama.")

    def generate_with_instructions(self, instructions_prompt, data_prompt, max_tokens=200):
        """
        Generates response based on system prompt instructions and user data.
        """
        response = self.generate_response(instructions_prompt, data_prompt, max_tokens)

        # Return early if we used the mistral api. No need to process it.
        if self.mistral_api:
            return response

        # Regex filtering based on model type
        regex_map = {
            "llama": r"\[EndDescription\]assistant([\s\S]*)",
            "gemma": r"</user><assistant>([\s\S]*)"
        }

        model_type = "llama" if "llama" in self.model_name.lower() else "gemma"
        match = re.search(regex_map[model_type], response)

        return match.group(1).replace("/n", '') if match else "Error. Could not properly regex prompt."


if __name__ == "__main__":
    instructions_prompt = """
        You are an expert in analyzing resumes. Your job is to determine the the required years of experience from a job description.
        If there is no mention of years of experience in the description, response "Unsure". Do not use the examples as indication of the years of experience, only as how to find the mentioned years of experience in the description.
        Below are several examples of what you should do. You are to respond in the format given.

        [Example]
        [Description] As someone with 3-5 years of development experience[EndDescription]
        [Response] 3 years [EndResponse]
        [Explanation] It is mentioned in the description that the candiate is expected to have 3 years of experience.[EndExplanation]
        [EndExample]

        [Example]
        [Description] As a someone with 2 years of SQL and 5 years of software engineering experience[EndDescription]
        [Response] 2 years [EndResponse]
        [Explanation] It is mentioned that the candidate has 2 years of SQL experience and 5 years of software engineering experience. 2 is the minimum required experience.[EndExplanation]
        [EndExample]

        [Example]
        [Description]As a historian your job is to keep the books[EndDescription]
        [Response] Unsure [EndResponse]
        [Explanation] There is no mention of years in this description, therefore I am unsure.[EndExplanation]
        [EndExample]

        Using the description from the user input, return how many years of experience are required. In the format of [Response] years of experience [EndResponse] [Explanation] explanation [EndExplanation]
        """

    data_prompt = """'Are you looking for more? Find it here. At Wells Fargo, we believe that a meaningful career is much more than just a job. It''s about finding all the elements that help you thrive, in one place. means you''re supported in life, not just work. It means having a competitive salary, a robust benefits package, and programs to support your work-life balance and well-being. It means being rewarded for investing in your community, celebrated for being your authentic self, and empowered to grow. And we''re recognized for it! Wells Fargo ranked in the top three on the 2024 LinkedIn Top Companies List of best workplaces "to grow your career" in the U.S.

Learn more about the career areas and business divisions at wellsfargojobs.com.


Wells Fargo is seeking a Senior Software Engineer in Technology as part of Commercial and Corporate & Investment Banking Technology(CCIBT). This position will be responsible for the full stack design, development, testing, documentation, and analysis of general modules or features of new or upgraded software systems and products.


Reflected is the base pay range offered for this position. Pay may vary depending on factors including but not limited to achievements, skills, experience, or work location. The range listed is just one component of the compensation package offered to candidates.

$84, 000.00 - $179, 200.00


Wells Fargo provides eligible employees with a comprehensive set of benefits, many of which are listed below. Visit Benefits - Wells Fargo Jobs for an overview of the following benefit plans and programs offered to employees.


29 Jun 2025


Wells Fargo is an equal opportunity employer. All qualified applicants will receive consideration for employment without regard to race, color, religion, sex, sexual orientation, gender identity, national origin, disability, status as a protected veteran, or any other legally protected characteristic.

Employees support our focus on building strong customer relationships balanced with a strong risk mitigating and compliance-driven culture which firmly establishes those disciplines as critical to the success of our customers and company. They are accountable for execution of all applicable risk programs(Credit, Market, Financial Crimes, Operational, Regulatory Compliance), which includes effectively following and adhering to applicable Wells Fargo policies and procedures, appropriately fulfilling risk and compliance obligations, timely and effective escalation and remediation of issues, and making sound risk decisions. There is emphasis on proactive monitoring, governance, risk identification and escalation, as well as making sound risk decisions commensurate with the business unit''s risk appetite and all risk and compliance program requirements.


To request a medical accommodation during the application or interview process, visit Disability Inclusion at Wells Fargo .


Wells Fargo maintains a drug free workplace. Please see our Drug and Alcohol Policy to learn more.


R-437226-2
Show more
Seniority level
Mid-Senior level
Employment type
Full-time
Job function
Information Technology and Engineering
Industries
Financial Services, Investment Management, and Banking
Referrals increase your chances of interviewing at Wells Fargo by 2x
See who you know'"""
    inference = AgentInference()
    resp = inference.generate_with_instructions(instructions_prompt, data_prompt)
