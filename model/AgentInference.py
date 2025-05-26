import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import os
import time


class AgentInference:
    def __init__(self, model_name="meta-llama/Llama-3.2-2B-Instruct", model_dir="llms"):
        """
        Initializes the LLM inference model.
        :param model_name: Hugging Face model identifier.
        :param model_dir: Directory where models should be stored.
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_dir = model_dir

        # Ensure the local model directory exists
        os.makedirs(self.model_dir, exist_ok=True)

        # Load tokenizer and model, ensuring they are stored locally
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=self.model_dir)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            cache_dir=self.model_dir
        )

        self.model = torch.compile(self.model)

    def generate_response(self, prompt, max_tokens=200):
        """
        Generates a response from the model.
        :param prompt: Input text prompt.
        :param max_tokens: Maximum token length for response.
        :return: Decoded response string.
        """
        inputs = self.tokenizer(prompt, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        outputs = self.model.generate(**inputs, max_new_tokens=max_tokens,
                                      do_sample=False, use_cache=True)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def format_prompt(self, system_prompt, user_prompt):
        """
        Formats system prompt and user prompt to match the format expected of llama model.
        """
        system_prompt_fmt = "<|begin_of_text|><|start_header_id|>system<|end_header_id|>" \
            + system_prompt + "<|eot_id|>"

        user_prompt_fmt = "<|start_header_id|>user<|end_header_id|>[Description]" + user_prompt \
            + "[EndDescription]<|eot_id|><|start_header_id|>assistant<|end_header_id|>"

        combined_prompt = system_prompt_fmt + user_prompt_fmt

        return combined_prompt

    def generate_with_instructions(self, system_prompt, user_prompt, max_tokens=200):
        """Generate response based off sytem prompt instructions and user data"""
        combined_prompt = self.format_prompt(system_prompt, user_prompt)
        response = self.generate_response(combined_prompt, max_tokens)
        return response


if __name__ == "__main__":
    system_prompt = """
        You are an expert in analyzing resumes. Your job is to determine the the required years of experience from a job description.
        Return only the minimum years of required experience. If there is no mention of years of experience in the description, response "Unsure".
        Below are several examples of what you should do. You are to respond in the format given.

        [Example]
        [Description] As a software engineer with 3-5 years of development experience[EndDescription]
        [Response] 3 years [EndResponse]
        [Explanation] It is mentioned in the descriptiont that the software engineer is expected to have 3 years of experience.[EndExplanation]
        [EndExample]

        [Example]
        [Description] As a someone with 2 years of SQL and 5 years of software engineering experience[EndDescription]
        [Response] 2 years [EndResponse]
        [Explanation] It is mentioned that the candidate has 2 years of SQL experience and 5 years of software engineering experience. 2 is the minimum required experience.[EndExplanation]
        [EndExample]

        [Example]
        [Description]As a historian your job is to keep the books[EndDescription]
        [Response] Unsure [EndResponse]
        [Explanation] There is no mention of years in this description, therefore I am unsure.
        [EndExample]

        Using the description from the user input, return how many years of experience are required. In the format of [Response] years of experience [EndResponse]
        """

    user_prompt = """'Are you looking for more? Find it here. At Wells Fargo, we believe that a meaningful career is much more than just a job. It''s about finding all the elements that help you thrive, in one place. means you''re supported in life, not just work. It means having a competitive salary, a robust benefits package, and programs to support your work-life balance and well-being. It means being rewarded for investing in your community, celebrated for being your authentic self, and empowered to grow. And we''re recognized for it! Wells Fargo ranked in the top three on the 2024 LinkedIn Top Companies List of best workplaces "to grow your career" in the U.S.

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
See who you know'
        """
    inference = AgentInference()

    start = time.time()
    response = inference.generate_with_instructions(system_prompt, user_prompt)
    end = time.time()
    print(response)

    print(f'\n\nTotal inference time: {end-start:.3f} seconds')
