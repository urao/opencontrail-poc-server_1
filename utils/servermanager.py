import requests
import json


class serverManager(object):


    def __init__(self, ip, port='9001'):

        self.sm_port = port
        self.base_url = 'http://{0}:{1}/'.format(ip, self.sm_port)
        self.ip = ip
        self.headers = {'content-type': 'application/json'}


    def __get_url(self, resource):

        if resource == 'server':
            url = self.base_url + 'server'
        elif resource == 'image':
            url = self.base_url + 'image'
        elif resource == 'cluster':
            url = self.base_url + 'cluster'
        elif resource == 'all':
            url = self.base_url + 'all'
        elif resource == 'reimage':
            url = self.base_url + 'reimage'
        elif resource == 'provision':
            url = self.base_url + 'server/provision'
        elif resource == 'provision_status':
            url = self.base_url + 'server_status'
        elif resource == 'restart':
            url = self.base_url + 'restart'
        else:
            raise AssertionError('Not valid resource {0}'.format(resource))

        return url

    def cluster_get(self, cluster_id=None, debug=False):
        if cluster_id is None:
            raise AssertionError('Cluster id is None.')

        url = self.__get_url('cluster') + '?id=' + cluster_id
        response = requests.get(url, headers=self.headers)
        return response.status_code

    def image_get(self, image_id=None, debug=False):
        if image_id is None:
            raise AssertionError('Image id is None.')

        url = self.__get_url('image') + '?id=' + image_id
        response = requests.get(url, headers=self.headers)
        return response.status_code

    def server_get(self, server_id=None, status=False, debug=False):
        if server_id is None:
            raise AssertionError('Server id is None.')

        if status:
            url = self.__get_url('server') + '?id=' + server_id+'&detail'
        else:
            url = self.__get_url('server') + '?id=' + server_id

        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print "\n"
            print "**** ERROR FROM THE REST SERVER ****"
            print "**** RESPONSE CODE : ", response.status_code, " ****"
            raise AssertionError("Return code expected : 200 but got {0}".format(response.status_code))

        server = json.loads(response.text)
        if status:
            return server['server'][0]['status']
        else:
            return response.status_code

    def provision_status(self, debug=False):

        url = self.__get_url('provision_status')
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print "\n"
            print "**** ERROR FROM THE REST SERVER ****"
            print "**** RESPONSE CODE : ", response.status_code, " ****"
            raise AssertionError("Return code expected : 200 but got {0}".format(response.status_code))

        server = json.loads(response.text)
        return server

if __name__ == '__main__':
    sm = serverManager('172.16.70.245')
    sm_img = sm.image_get('ubuntu-14-04-4')
    print sm_img
