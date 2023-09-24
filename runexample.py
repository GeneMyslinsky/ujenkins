from ujenkins import AsyncJenkinsClient #this is GeneMyslinsky/ujenkins/streaming_batteries

import os, asyncio, dotenv


dotenv.load_dotenv()

async def start_job(job_location, parameters=None):
    jenkins = AsyncJenkinsClient(
        os.environ.get("URL"), 
        os.environ.get("USER"), 
        os.environ.get("PASSWORD")
        )
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
            await asyncio.sleep(1)


            
    ## this is where the streaming starts
    async for output in jenkins.builds.stream(job_location, number):
        print(output)


asyncio.run(start_job("dev/testgene",parameters={"param1": "test", "param2": "option1"}))