from ujenkins import JenkinsClient #this is GeneMyslinsky/ujenkins/streaming_batteries
from ujenkins.endpoints.builds import DelayInterface
import os, time, dotenv
from rich import print

dotenv.load_dotenv()

class MyCustomDelay(DelayInterface):
    def __init__(self, min_delay: float, max_delay: float) -> None:
        self.std_delay = 2.5
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.i = 0
        self.average_size = 0
    def calculate_delay(self, output: str, text_size: int) -> float:
        # Custom logic to calculate delay
        # delay = min(self.max_delay, max(self.min_delay, text_size * 0.001))
        text_size = int(text_size)
        self.i += 1
        self.average_size = ((self.average_size*self.i) + text_size) / self.i
        if text_size > self.average_size:
            delay = self.std_delay / 1.5
        else:
            delay = self.std_delay * 1.5
    
        if delay < self.min_delay: delay = self.min_delay
        if delay > self.max_delay: delay = self.max_delay
        print(delay, self.average_size, self.text_size)
        return delay
    
my_custom_delay = MyCustomDelay(min_delay=1.0, max_delay=5.0)


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
    for output in jenkins.builds.stream(job_location, number, False, delay_handler=my_custom_delay):
        print(output)

    jenkins.close()


start_job("dev/testgene",parameters={"param1": "test", "param2": "option1"})