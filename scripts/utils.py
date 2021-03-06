from subprocess import PIPE, Popen


def run_cmd(cmd, verbose=False, output=False):
    stream=Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = stream.communicate()
    
    stdout=stdout.decode('utf-8')
    stderr=stderr.decode('utf-8')
    
    if verbose:
        print(stdout, flush=True)
        print(stderr, flush=True)
        
    if output:
        return stdout
