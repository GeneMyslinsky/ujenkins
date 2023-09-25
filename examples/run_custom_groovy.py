from ujenkins import AsyncJenkinsClient 
import os
import asyncio
import dotenv
from rich import print, traceback
import xml.etree.ElementTree as ET
import re

traceback.install()
dotenv.load_dotenv()

def read_groovy_script_from_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def update_script_in_xml(xml_config, new_script):
    tree = ET.ElementTree(ET.fromstring(xml_config))
    script_element = tree.find(".//definition/script")
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
    
    args = {}
    if parameters: args = parameters

    queue = await jenkins.builds.start(job_location, parameters=args)
    qinfo = await jenkins.queue.get_info(queue)

    if qinfo['executable'] and qinfo['executable']['number']:
        number, url = qinfo['executable']['number'], qinfo['executable']['url']
    else:
        raise Exception("Job did not start")

    tries = 0
    while (tries := tries + 1) < 10:
        job = await jenkins.builds.get_info(job_location, number)
        if job['building']:
            break
        else:
            await asyncio.sleep(.5)

    async for output in jenkins.builds.stream(job_location, number):
        lines = parse_output_to_lod(output)
        [print(line['line']) if line['line_type'] == "normal" else print(f"[bold blue]{line['line']}[/bold blue]") for line in lines]
    
    await jenkins.close()

if __name__ == '__main__':
    job_location = "dev/testgene"
    groovy_script_path = "./examples/example.groovy"  # Replace with the actual path
    groovy_script_content = read_groovy_script_from_file(groovy_script_path)
    asyncio.run(start_job(job_location, groovy_script=groovy_script_content))
