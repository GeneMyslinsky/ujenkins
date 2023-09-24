from ujenkins import JenkinsClient #this is GeneMyslinsky/ujenkins/streaming_batteries

import os, time, dotenv


dotenv.load_dotenv()

def start_job(job_location, parameters=None):
    jenkins = JenkinsClient(
        os.environ.get("JENKINS_URL"), 
        os.environ.get("JENKINS_USER"), 
        os.environ.get("JENKINS_PASSWORD")
        )
    
    print(os.environ.get("URL"), os.environ.get("JENKINS_USER"))
    args = {}
    if parameters: args = parameters

    queue = jenkins.builds.start(job_location, parameters=args)
    qinfo = jenkins.queue.get_info(queue)


    if qinfo['executable'] and qinfo['executable']['number']:
        number, url = qinfo['executable']['number'], qinfo['executable']['url']
    else:
        raise Exception("Job did not start")

    tries = 0
    while (tries := tries + 1) < 10:
        job = jenkins.builds.get_info(job_location, number)
        if job['building']:
            break
        else:
            time.sleep(1)


            
    ## this is where the streaming starts
    for output in jenkins.builds.stream(job_location, number):
        print(output)

    jenkins.close()


start_job("dev/testgene",parameters={"param1": "test", "param2": "option1"})