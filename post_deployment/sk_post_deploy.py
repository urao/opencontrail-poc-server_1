import os
import sys
import psutil
from oslo_config import cfg
from utils import helpers
from utils.configsk import configSetup
import re
from netaddr import IPNetwork
from utils.helpers import execute, from_project_root, get_project_root
from utils.remoteoperations import RemoteConnection
from time import sleep, strftime

CONF = cfg.CONF
SK_ENV_FILE = 'poc_env.conf'

def get_ip(ip_w_pfx):
    return str(IPNetwork(ip_w_pfx).ip)

def get_netmask(ip_w_pfx):
    return str(IPNetwork(ip_w_pfx).netmask)

def waiting(count):
    for i in range(count):
        print ".",
        sys.stdout.flush()
        sleep(1)
    print "\n"

class postDeploy(object):

    def __init__(self):
        install_dir = helpers.from_project_root('conf/')
        cfg_file = os.path.join(install_dir, SK_ENV_FILE)
        if not os.path.exists(os.path.join(install_dir, SK_ENV_FILE)):
            print "Missing required configuration file {}".format(cfg_file)
            sys.exit(1)
        print "Configuration file {} exists".format(cfg_file)

    def check_connectivity_to_allnodes(self):
        print "Checking connectivity to ctrldata IPs of all nodes in cluster"
        all_list = CONF['DEFAULTS']['bms'] + CONF['DEFAULTS']['reimagevms']
        for inventory in all_list:
            ctrld_ip = get_ip(CONF[inventory]['ctrldata_address'])
            cmd = 'ping -c 4 %s'%(ctrld_ip)
            res = execute(cmd, ignore_errors=True)
            if re.search(r'4 received', res, re.M|re.I):
                print "CTRLDATA IP(%s)of (%s) is reachable from jumphost."%(ctrld_ip,inventory)
            else:
                print "\n"
                print "Command: %s"%(cmd)
                print "Response: %s"%(res)
                print "=========================================================================="
                print "CTRLDATA IP(%s)of (%s) is not reachable from jumphost.check configuration"%(ctrld_ip, inventory)
                print "=========================================================================="
                sys.exit(1)

    def check_contrail_status(self):
        print "Checking contrail-status on the contrail controller node"
        cc_name = CONF['DEFAULTS']['reimagevms'][0]
        os_name = CONF['DEFAULTS']['reimagevms'][1]
        cc_ip = get_ip(CONF[cc_name]['management_address'])
        cc_ctrld_ip = get_ip(CONF[cc_name]['ctrldata_address'])
        os_ctrld_ip = get_ip(CONF[os_name]['ctrldata_address'])
        user = CONF['DEFAULTS']['root_username']
        passwd = CONF['DEFAULTS']['root_password']
        reconnect = RemoteConnection()
        reconnect.connect(cc_ip, username=user, password=passwd)
        cmd = 'contrail-status'
        res = reconnect.execute_cmd(cmd, timeout=20)
        if re.search(r'NTP state|inactive', res, re.M|re.I):
            print "\n"
            print "Command: %s"%(cmd)
            print "Response: %s"%(res)
            print "========================================================================================="
            print "contrail services on controller show in NTP state unsynchronized/inactive. please check."
            print "========================================================================================="
            sys.exit(1)
        else:
            print "All the services on contrail controller shows active. Installation successfully done."
            print res
            print "Access to Contrail web-ui: https://{0}:8143/".format(cc_ctrld_ip)
            print "Access to Openstack Horizon web-ui: http://{0}/horizon".format(os_ctrld_ip)

if __name__ == '__main__':

    pDeploy = postDeploy()

    #read conf file
    config = configSetup()
    config.set_base_config_options()

    try:
        config.load_configs(['conf/{}'.format(SK_ENV_FILE)])
        print "Loaded configuration file successfully"
    except cfg.RequiredOptError as e:
        print "Missing required input in poc_env.conf file, {0}: {1}".format(SK_ENV_FILE, e)
        sys.exit(1)

    config.set_deploy_virtual_server_config_options()
    config.set_deploy_physical_server_config_options()

    #post deployment setups
    pDeploy.check_connectivity_to_allnodes()
    pDeploy.check_contrail_status()
    sys.exit(0)
