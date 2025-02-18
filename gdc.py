from cat.mad_hatter.decorators import hook
import json
import re
from cat.log import log
import requests

json_data = ""
dictionary_of_tasks = []

# Base URL of your running FastAPI server
BASE_URL = "http://host.docker.internal:8000/items/"

# Create an item (POST request)
def create_item(name_of_the_task, task_id, dependencies, estimated_duration):
    data = {
        "name_of_the_task": name_of_the_task,
        "task_id": task_id,
        "dependencies": dependencies,
        "estimated_duration": estimated_duration
    }
    response = requests.post(BASE_URL, json=data)
    if response.status_code == 200:
        print("Item created:", response.json())
    else:
        print("Failed to create item:", response.status_code, response.text)

def clearing_input(output):
    json_data = output
    clear_json = json_data[7:-3].strip()
    tasks_list = json.loads(clear_json)
    tasks_dict = {f"tasks-{i}" : task for i, task in enumerate(tasks_list)}
    for task in tasks_list:
        create_item(task["name_of_the_task"], task["id"], task["dependencies"], task["estimated_duration"])
    return tasks_dict

@hook (priority = 2)
def before_cat_recalls_episodic_memories(episodic_recall_config, cat):
    episodic_recall_config["k"] = 0

    return episodic_recall_config

@hook 
def before_cat_reads_message(user_message_json, cat):
    # TODO: Checks here for irrelevant steps
    prompt = f"""Given the following input: {user_message_json['text']}, analyze whether it can be broken down into smaller, achievable tasks. Consider the following criteria:
    Is the goal releated to organise or learn something?
    Is the goal well-defined, or is it too broad/vague?
    Can it be broken into clear, sequential steps?
    Are the steps independently actionable?
    Does it require external dependencies that make it unachievable?
    If it's possible, suggest a structured breakdown. If not, explain why and how it could be refined."""
    check = cat.llm(prompt)
    example_labels = {
        "Learning" : ["I want to learn python", "How can I approach fishing", "explain me how to became a software engineer"],
        "Not Learning": ["Write a poetry", "What is the weather in London", "What is your"]
    }
    classification1 = cat.classify(check, labels=example_labels)
    print("£££££££££££££££££££££ THIS IS THE RESULT OF THE CALSSIFICATION £££££££££££££££££££££")
    log.info(classification1)
    
    if classification1 == "Learning":
        print("----------------------------------------------------This is just a check ----------------------------------------------------")

        # user_message_json["text"] = f"""You can only assist the user on goal breaking and based on the analysis of the input: {check}, explain why the selected goal cannot be broken down into smaller, achievable tasks. Consider the following:
        # Is the goal too vague or lacks a clear definition?
        # Does it require unknown or undefined steps?
        # Are there dependencies or constraints that prevent it from being actionable?
        # If possible, suggest how the goal could be redefined or clarified to make it achievable"""
        user_message_json["text"] = user_message_json["text"] + """. Given this high-level task, break it down into smaller, achievable tasks. Each sub-task should be structured as a JSON object with the following fields: "name_of_the_task" (a descriptive name), "id" (a unique integer identifier), "dependencies" (a list of IDs that the task depends on), and "estimated_duration" (an estimate in hours). Ensure that dependencies are properly linked and that tasks follow a logical order. Return the result in a JSON format. Return only the json format"""
        cat.working_memory.hacked = True
        return user_message_json
    else:
        cat.working_memory.hacked = True
        return user_message_json

@hook
def before_cat_sends_message(message, cat):
    if message.text[:7] == "```json":
        # TODO: Check if the implemented function works and then delete the other comments
    
        # json_data = message.text
        # clear_json = json_data[7:-3].strip()
        # tasks_list = json.loads(clear_json)
        # tasks_dict = {"tasks" : tasks_list}
        print("----------------------------------------------------This is just a check ----------------------------------------------------")
        # print(json.dumps(tasks_dict, indent=4))
        dictionary_of_tasks = clearing_input(message.text)
        print(dictionary_of_tasks)
        message.text = f"{json.dumps(dictionary_of_tasks, indent=4)}"
        log.info(message.text)
        return message
    else:
        return message