import os
import sys
from oslo_config import cfg
from utils import helpers
from utils.configsk import configSetup
from netaddr import IPNetwork
from utils.helpers import execute, from_project_root, get_project_root
from utils.remoteoperations import RemoteConnection
from time import sleep, strftime
from contrail.deploy_contrail import reImageAndDeploy

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

class cleanupEnv(object):

    def __init__(self):
        install_dir = helpers.from_project_root('conf/')
        cfg_file = os.path.join(install_dir, SK_ENV_FILE)
        if not os.path.exists(os.path.join(install_dir, SK_ENV_FILE)):
            print "Missing required configuration file {}".format(cfg_file)
            sys.exit(1)
        print "Configuration file {} exists".format(cfg_file)

    def delete_vms(self):
        vm_list = CONF['DEFAULTS']['reimagevms']
        print "Deleting %s VMS"%(vm_list)
        for vm in vm_list:
            print "Deleting VM %s"%(vm)
            cmd = "virsh destroy %s" %CONF[vm]['hostname']
            execute(cmd, ignore_errors=True)
            waiting(5)
            cmd = "virsh undefine %s" %CONF[vm]['hostname']
            execute(cmd, ignore_errors=True)
            waiting(5)

    def delete_sm(self):
        sm_name = CONF['servermanager']['hostname']
        print "Deleting SM-VM %s"%(sm_name)
        cmd = "virsh destroy %s" %sm_name
        execute(cmd, ignore_errors=True)
        waiting(5)
        cmd = "virsh undefine %s" %sm_name
        execute(cmd, ignore_errors=True)
        waiting(5)

    def cleanup_jumphost(self):
        svr1 = CONF['DEFAULTS']['bms'][0]
        print "Cleaning up jumphost server (%s) configuration"%(svr1)
        m_intf = CONF[svr1]['management_interface']
        c_intf = CONF[svr1]['ctrldata_interface']
        m_ip = get_ip(CONF[svr1]['management_address'])
        m_netmask = get_netmask(CONF[svr1]['management_address'])
        c_ip = get_ip(CONF[svr1]['ctrldata_address'])
        c_netmask = get_netmask(CONF[svr1]['ctrldata_address'])
        cmd = "/sbin/ifconfig %s 0.0.0.0" %m_intf
        execute(cmd, ignore_errors=True)
        cmd = "/sbin/ifconfig %s %s netmask %s up" %(m_intf, m_ip, m_netmask)
        execute(cmd, ignore_errors=False)
        cmd = "/sbin/ifconfig mgmtbr 0.0.0.0 down && brctl delif mgmtbr %s && brctl delbr mgmtbr" %(m_intf)
        execute(cmd, ignore_errors=False)
        cmd = "/sbin/ifconfig %s 0.0.0.0" %c_intf
        execute(cmd, ignore_errors=False)
        cmd = "/sbin/ifconfig %s %s netmask %s up" %(c_intf, c_ip, c_netmask)
        execute(cmd, ignore_errors=False)
        cmd = "/sbin/ifconfig ctrldatabr 0.0.0.0 down && brctl delif ctrldatabr %s && brctl delbr ctrldatabr" %(c_intf)
        execute(cmd, ignore_errors=False)

        cmd = "/sbin/ip route | grep default |  awk '{print $3}'"
        ext_gw = execute(cmd, ignore_errors=False)
        cmd = "brctl show extbr | grep extbr | awk '{print $4}'"
        ext_intf = execute(cmd, ignore_errors=False)
        cmd = "/sbin/ifconfig extbr | grep inet | grep -oE \"\\b([0-9]{1,3}\.){3}[0-9]{1,3}\\b\""
        ext_intf_ips = execute(cmd, ignore_errors=False)
        ext_intf_ip = ext_intf_ips.splitlines()[0]
        ext_intf_netmask = ext_intf_ips.splitlines()[2]
        cmd = "/sbin/ifconfig %s %s netmask %s up" %(ext_intf, ext_intf_ip, ext_intf_netmask)
        execute(cmd, ignore_errors=False)
        cmd = "/sbin/route add default gw %s dev %s" %(ext_gw, ext_intf)
        execute(cmd, ignore_errors=False)
        cmd = "/sbin/ifconfig extbr 0.0.0.0 down && brctl delif extbr %s && brctl delbr extbr" %(ext_intf)
        execute(cmd, ignore_errors=False)

        cmd = "mv /etc/network/interfaces.bak /etc/network/interfaces"
        execute(cmd, ignore_errors=False)
        cmd = "/sbin/ifconfig %s 0.0.0.0 up" %(m_intf)
        execute(cmd, ignore_errors=False)
        cmd = "/sbin/ifconfig %s 0.0.0.0 up" %(c_intf)
        execute(cmd, ignore_errors=False)

        cmd = "/bin/rm -rf /var/www/html/pockit_images/"
        execute(cmd, ignore_errors=False)
        cmd = "/bin/rm -rf /root/sm_vm/"
        execute(cmd, ignore_errors=False)


if __name__ == '__main__':

    cSetup = cleanupEnv()

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

    #cleanup
    cSetup.delete_vms()
    cSetup.delete_sm()
    cSetup.cleanup_jumphost()
    sys.exit(0)
