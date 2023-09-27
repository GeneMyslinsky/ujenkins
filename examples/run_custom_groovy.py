from ujenkins import AsyncJenkinsClient 
import os
import asyncio
import dotenv
from rich import print, traceback
from rich.console import Console
import xml.etree.ElementTree as ET
import re
import sys
import json

def str2bool(v):
    """Convert string values to Boolean."""
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise ValueError('Boolean value expected.')

def parse_arguments(args):
    params = {}
    for arg in args:
        key, value = arg.split('=')
        if value.lower() in ('yes', 'true', 't', 'y', '1', 'no', 'false', 'f', 'n', '0'):
            value = str2bool(value)
        params[key] = value
    return params




console=Console()
traceback.install()


def read_groovy_script_from_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()
    
def xml_params_to_dict(xml_config):
    tree = ET.ElementTree(ET.fromstring(xml_config))
    params_element = tree.find(".//hudson.model.ParametersDefinitionProperty")
    
    if params_element is None:
        raise Exception("Parameters definition not found in XML")

    param_dict = {}

    # Iterating through all child elements of params_element
    for param in params_element:
        param_type = param.tag.split('}')[-1]  # Extracting the local tag name
        name_element = param.find('./name')
        
        # If the <name> element doesn't exist for this parameter, skip it
        if name_element is None:
            continue
        
        param_name = name_element.text

        details = {
            'type': param_type
        }
        
        # Common fields to extract
        for field in ['defaultValue', 'description']:
            elem = param.find(f"./{field}")
            if elem is not None:
                details[field] = elem.text

        # For choice parameters, extract the choices list
        if param_type == "ChoiceParameterDefinition":
            choices = [choice.text for choice in param.findall('./choices/a/string')]
            details['choices'] = choices

        param_dict[param_name] = details

    return param_dict
def xml_to_json(xml_config):
    tree = ET.ElementTree(ET.fromstring(xml_config))

    root = tree.find(".//properties/hudson.model.ParametersDefinitionProperty/parameterDefinitions")
    parameters = []

    for param in root:
        param_data = {}
        param_type = param.tag.split('.')[-1]  # Extracting only the class name (e.g., StringParameterDefinition)
        param_data['type'] = param_type

        for child in param:
            if child.tag == 'choices':
                choices_list = [c.text for c in child.find('.//a/string')]
                param_data[child.tag] = choices_list
            else:
                param_data[child.tag] = child.text if child.text else (True if child.text == "true" else False)

        parameters.append(param_data)

    return parameters

def update_script_in_xml(xml_config, new_script):
    tree = ET.ElementTree(ET.fromstring(xml_config))
    script_element = tree.find(".//definition/script")
    
    # for elem in tree.find(".//properties/hudson.model.ParametersDefinitionProperty/parameterDefinitions").iter():
    #     print("one")
    #     print(elem.tag)
    if script_element is not None:
        script_element.text = new_script  # Replace the script content
        new_xml_config = ET.tostring(tree.getroot(), encoding="UTF-8").decode()
        return new_xml_config
    else:
        raise Exception("Script tag not found in XML")
    
def parse_output_to_lod(strout):
    regex_pattern = re.compile(r'\[(.*?)\]\s+(\[Pipeline\]\s+)?(.*)')
    lines = strout.split("\r\n")
    if lines[-1]  == "": del lines[-1] 
    output = []
    for line in lines:
        match = regex_pattern.match(line)
        if match:
            timestamp, pipeline, log_line = match.groups()
            
            parsed_line = {
                "ts": timestamp,
                "line": log_line,
                "line_type": "pipeline" if pipeline else "normal"
            }
            output.append(parsed_line)
    return output

async def start_job(job_location, parameters=None, groovy_script=None):
    jenkins = AsyncJenkinsClient(
        os.environ.get("JENKINS_URL"),
        os.environ.get("JENKINS_USER"),
        os.environ.get("JENKINS_PASSWORD")
    )
    job_config = await jenkins.jobs.get_config(job_location)
    new_config = update_script_in_xml(job_config, groovy_script)
    await jenkins.jobs.reconfigure(job_location, new_config)
    params = xml_to_json(job_config)
    print("\n==========\n")
    for param in params:
        for k,v in param.items():
            print(f"{k}: {v}")
        print("\n==========\n")
    args = {}
    if parameters: args = parameters
    print(json.dumps(args))

    queue = await jenkins.builds.start(job_location, parameters=args)
    qinfo = await jenkins.queue.get_info(queue)
    print("\n[bold dark_olive_green3]===== JOB QUEUED =====[/bold dark_olive_green3]\n")
    if qinfo['executable'] and qinfo['executable']['number']:
        number, url = qinfo['executable']['number'], qinfo['executable']['url']
    else:
        raise Exception("Job did not start")
    
    tries = 0
    while (tries := tries + 1) < 10:
        job = await jenkins.builds.get_info(job_location, number)
        if job['building'] or job['result'] != None:
            break
        else:
            print(f"Waiting for job to start... ({tries}/10)")
            await asyncio.sleep(.5)

    print("\n[bold green]===== JOB STARTED =====[/bold green]\n")
    async for output in jenkins.builds.stream(job_location, number):
        lines = parse_output_to_lod(output)
        [print(line['line']) if line['line_type'] == "normal" else console.print(f"{line['line']}",style="grey3") for line in lines]
    
    await jenkins.close()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: script_name.py env_path script_path [key=value ...]")
        sys.exit(1)

    env_path = sys.argv[1]
    job_path = sys.argv[2]
    script_path = sys.argv[3]
    # Exclude the script name, env_path, and script_path from the args
    raw_args = sys.argv[4:]
    params = parse_arguments(raw_args)

    print(f"env_path: {env_path}")
    print(f"job_path: {job_path}")
    print(f"script_path: {script_path}")
    print("")
    
    # for key, value in params.items():
    #     print(f"{key}: {value}")

    dotenv.load_dotenv(env_path, override=True)
    job_location = job_path
    groovy_script_path = script_path # Replace with the actual path
    groovy_script_content = read_groovy_script_from_file(groovy_script_path)
    asyncio.run(start_job(job_location, parameters=params, groovy_script=groovy_script_content))
