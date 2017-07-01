import os
import sys
import requests
import logging
import subprocess
import shlex
import shutil
import paramiko

LOG = logging.getLogger(__name__)

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_dir = os.path.abspath(os.path.join(script_dir, '../'))


def get_project_root():
    return project_root_dir

def from_project_root(path):
    return os.path.abspath(os.path.join(project_root_dir, path))

def create_dir_if_not_exists(d):
    if not os.path.exists(d):
        os.makedirs(d)

def execute(command, ignore_errors=False):
    pipe = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, 
                            stderr=subprocess.STDOUT, close_fds=True)
    data = ''
    for line in pipe.stdout:
        data += line

    rc = pipe.wait()
    cwd = os.getcwd()
    if rc and not ignore_errors:
        print 'Error : Working directory : %s' %(cwd)
        print 'Error : Failed to execute command: %s\n%s' % (command, data)
        sys.exit(1)
    return data.strip()

def get_artifact(download_dir, access_method=None, download_url=None, **kwargs):
    #print download_dir, access_method, download_url
    if access_method == "download_url":
        if not download_url:
            raise Exception('Input missing: download_url {}', format(download_url))
        download_file(download_dir, download_url)
    else:
        raise Exception('Valid values for access_method is download_url')


def download_file(filedir, url):
    print '\n====\nDownloading from {0} to directory {1}'.format(url, filedir)
    local_filename = url.split('/')[-1]
    r = requests.get(url, stream=True, verify=False)
    if r.status_code != 200:
        raise Exception('Artifact not found.')

    total_len = int(r.headers.get('content-length', -1))
    dl_unit = 1024
    dl =0
    with open(filedir + '/' + local_filename, 'wb') as f:
        for i, chunk in enumerate(r.iter_content(chunk_size=dl_unit)):
            if total_len:
                dl += dl_unit
                if i % 10 == 0:
                    print '{0:.2f}% complete\r'.format((float(dl) / total_len) * 100)
            if chunk:
                f.write(chunk)
                f.flush()
