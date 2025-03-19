from cat.mad_hatter.decorators import hook
import json
import re
from cat.log import log
from typing import Dict, List, Any, Optional

# Constants
LEARNING_LABELS = {
    "Learning": [
        "I want to learn python",
        "How can I approach fishing",
        "explain me how to became a software engineer",
        "how could organise the garden"
    ],
    "Not Learning": [
        "Write a poetry",
        "What is the weather in London",
        "What is your name?"
    ]
}

JSON_TEMPLATE = """{
    "tasks":[ 
        {
        "name_of_the_task": "task_name1"
        },
        {
        "name_of_the_task": "task_name2"
        }
    ]  
}"""

JSON_TEMPLATE_OUTPUT = """
{
    "tasks":[ 
        {
        "id": int id,
        "name_of_the_task": "task_name1",
        "description": "description1",
        "dependencies": "dependency1",
        "estimation": int in hours
        },
        {
        "id": int id,
        "name_of_the_task": "task_name2",
        "description": "description2",
        "dependencies": task_id,
        "estimation": int in hours
        }
    ]
}
        """
class TaskBreakdownPlugin:
    def __init__(self):
        self.tasks_dict: Dict[str, Any] = {}
        self.output_dict: Dict[str, Any] = {}

    def clear_output(self, output: str) -> Dict[str, Any]:
        """
        Process and clear JSON output from LLM response.
        
        Args:
            output (str): Raw JSON output from LLM
            
        Returns:
            Dict[str, Any]: Processed task dictionary
        """
        try:
            if not output or len(output) < 10:
                log.error("Invalid output received")
                return {}
                
            json_data = output
            clear_json = json_data[7:-3].strip()
            tasks_list = json.loads(clear_json)
            return {f"tasks-{i}": task for i, task in enumerate(tasks_list)}
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse JSON: {e}")
            return {}
        except Exception as e:
            log.error(f"Unexpected error in clear_output: {e}")
            return {}

    def clean_output(self, output: str) -> List[Dict[str, str]]:
        """
        Clean and validate task list from LLM response.
        
        Args:
            output (str): Raw JSON output from LLM
            
        Returns:
            List[Dict[str, str]]: List of cleaned tasks
        """
        try:
            if not output:
                log.error("Empty output received")
                return []
                
            tasks_json_list = json.loads(output)
            return tasks_json_list.get("tasks", [])
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse JSON: {e}")
            return []
        except Exception as e:
            log.error(f"Unexpected error in clean_output: {e}")
            return []

    def validate_task(self, task: Dict[str, Any]) -> bool:
        """
        Validate if a task has the required structure.
        
        Args:
            task (Dict[str, Any]): Task to validate
            
        Returns:
            bool: True if task is valid, False otherwise
        """
        return isinstance(task, dict) and "name_of_the_task" in task

@hook(priority=2)
def before_cat_recalls_episodic_memories(episodic_recall_config: Dict[str, Any], cat) -> Dict[str, Any]:
    """
    Hook to modify episodic memory recall configuration.
    
    Args:
        episodic_recall_config (Dict[str, Any]): Configuration for episodic memory recall
        cat: Cat instance
        
    Returns:
        Dict[str, Any]: Modified configuration
    """
    episodic_recall_config["k"] = 1
    return episodic_recall_config

@hook
def before_cat_reads_message(user_message_json: Dict[str, Any], cat) -> Dict[str, Any]:
    """
    Hook to process and classify user messages before processing.
    
    Args:
        user_message_json (Dict[str, Any]): User message data
        cat: Cat instance
        
    Returns:
        Dict[str, Any]: Modified message data
    """
    try:
        if not user_message_json.get('text'):
            log.error("Empty message received")
            return user_message_json

        prompt = f"""Given the following input: {user_message_json['text']}, analyze whether it can be broken down into smaller, achievable tasks. Consider the following criteria:
        Is the goal releated to organise or learn something?
        Is the goal well-defined, or is it too broad/vague?
        Can it be broken into clear, sequential steps?
        Are the steps independently actionable?
        Does it require external dependencies that make it unachievable?
        If it's possible, suggest a structured breakdown. If not, explain why and how it could be refined."""
        
        check = cat.llm(prompt)
        classification = cat.classify(check, labels=LEARNING_LABELS)
        
        if classification == "Learning":
            user_message_json["text"] = f"""Analyze the following high-level task: {user_message_json['text']}. Break it down into smaller, achievable tasks. Each sub-task should be structured as a JSON object with the following fields: "name_of_the_task". Return the result in a JSON format and only a JSON format."""
            cat.working_memory.hacked = True
        else:
            cat.working_memory.hacked = True
            user_message_json["text"] = "To this message answer: I cannot assist you with this request"
            
        return user_message_json
        
    except Exception as e:
        log.error(f"Error in before_cat_reads_message: {e}")
        return user_message_json

@hook
def before_cat_sends_message(message: Dict[str, Any], cat) -> Dict[str, Any]:
    """
    Hook to process and format messages before sending.
    
    Args:
        message (Dict[str, Any]): Message to be sent
        cat: Cat instance
        
    Returns:
        Dict[str, Any]: Processed message
    """
    try:
        if not message.text or not message.text.startswith("```json"):
            return message

        plugin = TaskBreakdownPlugin()
        dictionary_of_tasks = plugin.clear_output(message.text)
        
        if not dictionary_of_tasks:
            log.error("Failed to process tasks")
            return message

        output_dict: Dict[str, Any] = {}
        for task_id, task in dictionary_of_tasks.items():
            if not plugin.validate_task(task):
                log.error(f"Invalid task format: {task}")
                continue

            prompt = f"""Given the following task: {task}.
            Analyze whether it can be broken down into smaller, achievable subtasks by considering:
            - Is the goal well-defined, or is it too broad or vague?
            - Can it be segmented into clear, sequential steps?

            Return the final output strictly in the following JSON format (without any additional text):{JSON_TEMPLATE}"""
            
            further_break_down = cat.llm(prompt)
            # Clean any markdown formatting
            further_break_down = further_break_down.replace("```json", "").replace("```", "").strip()
            further_break_down_clean = plugin.clean_output(further_break_down)
            
            for i, subtask in enumerate(further_break_down_clean):
                if plugin.validate_task(subtask):
                    output_dict[f"{task_id}-subtasks-{i}"] = subtask["name_of_the_task"]
            
        final_prompt = f"""Given the following tasks: {output_dict}.
        For each task, create a detailed task breakdown that includes:
        1. name_of_the_task: A clear, specific task name
        2. description: A detailed explanation of what needs to be done
        3. dependencies: List the task IDs that must be completed before this task (use [] if none)
        4. estimation: Estimated time in hours

        Consider for dependencies:
        - Which tasks must be completed first?
        - What knowledge from previous tasks is needed?
        - What is the logical sequence?

        Return the final output strictly in the following JSON format (without any additional text):{JSON_TEMPLATE_OUTPUT}"""
        
        final_output = cat.llm(final_prompt)
        
        # Clean the output of any markdown or whitespace
        final_output = final_output.replace("```json", "").replace("```", "").strip()
        
        try:
            # Clean and validate the final output
            final_json = json.loads(final_output)
            if "tasks" in final_json:
                message.text = json.dumps(final_json, indent=4)
                log.info(f"Successfully processed tasks: {message.text}")
            else:
                log.error("Invalid final output format - missing tasks key")
                return message
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse final output: {e}\nOutput was: {final_output}")
            return message
            
        return message
        
    except Exception as e:
        log.error(f"Error in before_cat_sends_message: {e}")
        return message