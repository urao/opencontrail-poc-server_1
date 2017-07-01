import os
import sys
import json
import re
from oslo_config import cfg
from jinja2 import Environment, FileSystemLoader
from netaddr import IPNetwork
from time import sleep, strftime
import Queue
import threading

from utils.helpers import execute, from_project_root, get_project_root
from utils.remoteoperations import RemoteConnection
from utils.servermanager import serverManager

CONF = cfg.CONF

sk_img_path = '/var/www/html/pockit_images'
ubuntu_img_id = 'ubuntu-14-04-4'
sk_cluster_id = 'pockitcluster'
contrail_pkg_id = 'mitaka'

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

class reImageAndDeploy(object):

    def __init__(self):
        global jinja_env
        jinja_env = Environment(loader=FileSystemLoader(from_project_root('contrail')))
        self.sm_vm = None
        self.sm_api = None
        self.sm_home = None

    def check_sm_status(self):
        print "Checking servermanager reachablility."
        sm_m_ip = get_ip(CONF['servermanager']['management_address'])
        sm_local_user = CONF['servermanager']['local_user']
        sm_local_passwd = CONF['servermanager']['local_password']

        count = 5
        for _ in range(count):
            #ping SM
            res = os.system('ping -c 3 ' + sm_m_ip)
            if res == 0:
                print "servermanager is reachable"
                self.sm_vm = RemoteConnection()
                self.sm_vm.connect(sm_m_ip, username=sm_local_user, password=sm_local_passwd)
                self.sm_api = serverManager(sm_m_ip)
                cmd = 'eval echo ~$USER'
                self.sm_home = self.sm_vm.execute_cmd(cmd, timeout=10)
                return
            else:
                print "Waiting for servermanager to respond."
                print "Retry after 30sec"
                waiting(30)
        print "\n"
        print "Response: %s"%(res)
        print "=================================================================================="
        print "servermanager is not reachable, please check or run ./smgr_provision.sh if not done"
        print "=================================================================================="
        sys.exit(1)

    def copy_iso_contrail_images(self):
        print "Copying ubuntu OS ISO and contrail installer package onto servermanager VM"        

        svr1 = CONF['DEFAULTS']['bms'][0]
        server1_mgmt_ip = get_ip(CONF[svr1]['management_address'])
        sm_m_ip = get_ip(CONF['servermanager']['management_address'])
        ubuntuiso = CONF['DEFAULTS']['ubuntuimage']
        contrailimg = CONF['DEFAULTS']['contrailimage']

        jumphost_img_url = 'http://{}/pockit_images/'.format(server1_mgmt_ip)

        self.sm_vm.chdir('{}/images/'.format(self.sm_home))
        cmd = 'wget -q {0}{1} -O {1}'.format(jumphost_img_url,ubuntuiso)
        if self.sm_vm.status_command(cmd) != 0:
            print "\n"
            print "Command: %s"%(cmd)
            print "=========================================================="
            print "Error in downloading ubuntu ISO image onto server-manager"
            print "=========================================================="
            sys.exit(1)
        else:
            print "Downloaded ubuntu ISO image successfully onto server-manager"

        cmd = 'wget -q {0}{1} -O {1}'.format(jumphost_img_url,contrailimg)
        if self.sm_vm.status_command(cmd) != 0:
            print "\n"
            print "Command: %s"%(cmd)
            print "==================================================================="
            print "Error in downloading contrail installer package onto server-manager"
            print "==================================================================="
            sys.exit(1)
        else:
            print "Downloaded contrail installer package successfully onto server-manager"


    def create_cluster_json_file(self):
        print "Creating contrail cluster json file"        
        cluster_tmpl = jinja_env.get_template('cluster.json')
        userdata = cluster_tmpl.render(
            dns_search=CONF['DEFAULTS']['dns_search'],
            cluster_gateway=CONF['DEFAULTS']['cluster_gateway'],
            contrail_asn=CONF['DEFAULTS']['contrail_asn'],
            openstack_password=CONF['DEFAULTS']['contrail_os_webui_passwd'],
            mysql_password=CONF['DEFAULTS']['contrail_mysql_passwd'],
            cluster_netmask=CONF['DEFAULTS']['cluster_netmask']
        )
        with open(sk_img_path + '/cluster.json', 'w+') as fobj:
            fobj.write(userdata)

    def create_image_json_file(self):
        print "Creating cluster host os image and contrail installer package file"        
        img_tmpl = jinja_env.get_template('image.json')
        userdata = img_tmpl.render(
            kickseed_file=self.sm_home+'/json-files/contrail-ubuntu-sk.seed',
            kickstart_file=self.sm_home+'/json-files/contrail-ubuntu-sk.ks',
            ubuntu_iso_file=self.sm_home+'/images/'+CONF['DEFAULTS']['ubuntuimage'],
            contrail_pkg_file=self.sm_home+'/images/'+CONF['DEFAULTS']['contrailimage']
        )
        with open(sk_img_path + '/image.json', 'w+') as fobj:
            fobj.write(userdata)

    def create_vm_server_json_files(self):
        vm_list = CONF['DEFAULTS']['reimagevms']
        print "Creating VM %s json files"%(vm_list)        
        filenum = 1
        for vm in vm_list:
            vm_tmpl = jinja_env.get_template('server.json')
            userdata = vm_tmpl.render(
                    ctrldata_intf = CONF[vm]['ctrldata_interface'],
                    dns_search = CONF[vm]['dns_search'],
                    server_name = CONF[vm]['hostname'],
                    ipmi_address = "",
                    ipmi_password = "",
                    ipmi_username = "",
                    mgmt_address = CONF[vm]['management_address'],
                    mgmt_mac = CONF[vm]['management_mac'],
                    mgmt_intf = CONF[vm]['management_interface'],
                    mgmt_gateway = CONF[vm]['gateway'],
                    ctrldata_address = CONF[vm]['ctrldata_address'],
                    ctrldata_mac = CONF[vm]['ctrldata_mac'],
                    disk_partition = CONF[vm]['partition'],
                    root_password = CONF['DEFAULTS']['root_password'],
                    roles = CONF[vm]['roles']
                )
            with open(sk_img_path + '/server{}.json'.format(filenum), 'w+') as fobj:
                fobj.write(userdata)
            filenum += 1

    def copy_seed_ks_to_websvr(self):
        print "Copying ubuntu seed and kickstart files on to jumphost webserver"        
        cmd = 'cp {0}/contrail-ubuntu-sk.seed {1}/'.format(from_project_root('contrail'),sk_img_path)
        execute(cmd, ignore_errors=True)
        cmd = 'cp {0}/contrail-ubuntu-sk.ks {1}/'.format(from_project_root('contrail'),sk_img_path)
        execute(cmd, ignore_errors=True)

    def copy_json_files_to_sm(self):
        print "Copying cluster, image, VM and BMS json files on to server-manager VM"        
        svr1 = CONF['DEFAULTS']['bms'][0]
        server1_mgmt_ip = get_ip(CONF[svr1]['management_address'])
        jumphost_img_url = 'http://{}/pockit_images/'.format(server1_mgmt_ip)

        cmd = 'cd {0}/json-files/ && wget -O cluster.json {1}/cluster.json'.format(self.sm_home, jumphost_img_url)
        if self.sm_vm.status_command(cmd) != 0:
            print "\n"
            print "Command: %s"%(cmd)
            print "============================================================"
            print "Error in downloading cluster.json file onto servermanager VM"
            print "============================================================"
            sys.exit(1)
        else:
            print "Downloaded cluster.json file successfully onto servermanager VM"

        cmd = 'cd {0}/json-files/ && wget -O image.json {1}/image.json'.format(self.sm_home, jumphost_img_url)
        if self.sm_vm.status_command(cmd) != 0:
            print "\n"
            print "Command: %s"%(cmd)
            print "============================================================"
            print "Error in downloading image.json file onto servermanager VM"
            print "============================================================"
            sys.exit(1)
        else:
            print "Downloaded image.json file successfully onto servermanager VM"

        cluster_list = CONF['DEFAULTS']['reimagevms']
        for i in range(1,len(cluster_list)+1):
            cmd = 'cd {0}/json-files/ && wget -O server{1}.json {2}/server{1}.json'.format(self.sm_home, i, jumphost_img_url)
            if self.sm_vm.status_command(cmd) != 0:
                print "\n"
                print "Command: %s"%(cmd)
                print "============================================================="
                print "Error in downloading server{}.json file onto servermanager VM".format(i)
                print "============================================================"
                sys.exit(1)
            else:
                print "Downloaded server{}.json file successfully onto servermanager VM".format(i)

        self.copy_seed_ks_to_websvr()
        cmd = 'cd {0}/json-files/ && wget -O contrail-ubuntu-sk.ks {1}/contrail-ubuntu-sk.ks'.format(self.sm_home, jumphost_img_url)
        if self.sm_vm.status_command(cmd) != 0:
            print "\n"
            print "Command: %s"%(cmd)
            print "============================================================"
            print "Error in downloading kickstart file onto servermanager VM"
            print "============================================================"
            sys.exit(1)
        else:
            print "Downloaded kickstart file successfully onto servermanager VM"

        cmd = 'cd {0}/json-files/ && wget -O contrail-ubuntu-sk.seed {1}/contrail-ubuntu-sk.seed'.format(self.sm_home, jumphost_img_url)
        if self.sm_vm.status_command(cmd) != 0:
            print "\n"
            print "Command: %s"%(cmd)
            print "============================================================"
            print "Error in downloading kickseed file onto servermanager VM"
            print "============================================================"
            sys.exit(1)
        else:
            print "Downloaded kickseed file successfully onto servermanager VM"


    def reimage_vms(self):
        vm_list = CONF['DEFAULTS']['reimagevms']
        print "Re-Imaging %s VM's. Begins.."%(vm_list)

        #add cluster, image and server1,2
        print "Adding cluster.json to servermanager"
        cmd = 'server-manager delete cluster --cluster_id {}'.format(sk_cluster_id)
        self.sm_vm.execute_cmd(cmd, timeout=30)
        cmd = 'server-manager add cluster -f {}/json-files/cluster.json'.format(self.sm_home)
        self.sm_vm.execute_cmd(cmd, timeout=30)
        res = self.sm_api.cluster_get(sk_cluster_id)
        if res != 200:
            print "\n"
            print "Command: %s"%(cmd)
            print "Response: %s"%(res)
            print "======================================"
            print "Error in adding cluster.json to servermanager"
            print "======================================"
            sys.exit(1)
        else:
            print "Successfully added cluster.json to servermanager"

        print "Adding image.json to servermanager"
        cmd = 'server-manager delete image --image_id {}'.format(ubuntu_img_id)
        self.sm_vm.execute_cmd(cmd, timeout=120)
        cmd = 'server-manager add image -f {}/json-files/image.json'.format(self.sm_home)
        self.sm_vm.execute_cmd(cmd, timeout=120)
        res = self.sm_api.image_get(ubuntu_img_id)
        if res != 200:
            print "\n"
            print "Command: %s"%(cmd)
            print "Response: %s"%(res)
            print "======================================"
            print "Error in adding image.json to servermanager"
            print "======================================"
            sys.exit(1)
        else:
            print "Successfully added image.json to servermanager"

        vm_list = CONF['DEFAULTS']['reimagevms']
        i = 1
        for vm in vm_list:
            print "Adding server{}.json to servermanager".format(i)
            cmd = 'server-manager delete server --server_id {}'.format(CONF[vm]['hostname'])
            self.sm_vm.execute_cmd(cmd, timeout=30)
            cmd = 'server-manager add server -f {0}/json-files/server{1}.json'.format(self.sm_home, i)
            self.sm_vm.execute_cmd(cmd, timeout=30)
            res = self.sm_api.server_get(CONF[vm]['hostname'])
            if res != 200:
                print "\n"
                print "Command: %s"%(cmd)
                print "Response: %s"%(res)
                print "============================================="
                print "Error in adding server{}.json to servermanager".format(i)
                print "============================================="
                sys.exit(1)
            else:
                print "Successfully added server{}.json to servermanager".format(i)
                print "Issuing reimage server{}".format(i)
                cmd = 'yes y | server-manager reimage --server_id {}'.format(CONF[vm]['hostname'])
                self.sm_vm.execute_cmd(cmd, timeout=10)
                i += 1

        for vm in vm_list:
            print "Re-imaging  %s  VM" %CONF[vm]['hostname']
            cmd = "virsh destroy %s" %CONF[vm]['hostname']
            execute(cmd, ignore_errors=True)
            waiting(5)
            cmd = "virsh undefine %s" %CONF[vm]['hostname']
            execute(cmd, ignore_errors=True)
            waiting(5)
            cmd = "virt-install --os-variant=ubuntutrusty --os-type=linux --arch=x86_64 --network mac=%s,bridge=mgmtbr --network mac=%s,bridge=ctrldatabr  --file=/var/lib/libvirt/images/%s.qcow2 --graphics vnc,password=%s --noautoconsole --vcpus=%s --ram=%s --pxe --name %s --autostart --file-size=%s" %(CONF[vm]['management_mac'], CONF[vm]['ctrldata_mac'], CONF[vm]['hostname'], CONF[vm]['local_password'], CONF[vm]['vcpus'], CONF[vm]['memory'], CONF[vm]['hostname'], CONF[vm]['harddisk'])
            execute(cmd, ignore_errors=False)
            waiting(10)
            print "Waiting for %s VM to reimage" %vm
        self.check_reimage_status(vm_list)
        print "Re-Imaging %s VM's. Ends.."%vm_list

    def check_reimage_status(self, svr_list):
        queue = Queue.Queue()
        threads = []
        for vm in svr_list:
            svr = CONF[vm]['hostname']
            t = threading.Thread(target=self.check_reimage_vm_status, args=(svr,), name=svr)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        print "Completed VM re-image status verification"

    def check_reimage_vm_status(self, vmname):
        count = 40
        expected_res = "reimage_completed"
        for _ in range(count):
            #Get reimage status
            res = self.sm_api.server_get(server_id=vmname, status=True)
            print "Waiting for %s VM to get re-imaged.."%vmname
            print "Expected status:   %s      ::      Current status:  %s  "%(expected_res, res)
            if res == expected_res:
                waiting(10)
                cmd = "virsh list --all"
                res = execute(cmd, ignore_errors=True)
                if re.search(r'shut off',res,re.M|re.I):
                    print "Re-imaged VM is shut-off, starting now..."
                    cmd = "virsh start "+vmname
                    res = execute(cmd, ignore_errors=True)
                    waiting(5)
                else: 
                    print "None of the re-imaged VM's are shut-off"
                return
            else:
                print "Retry after 30sec"
                waiting(30)
        print "\n"
        print "==========================================================="
        print "VM %s did not complete Re-imaging, hence exiting..." %vmname
        print "==========================================================="
        sys.exit(1)

    def check_topology_connectivity(self):
        print "Checking the management IP and ctrldata IP reachability from servermanager VM"
        waiting(30)
        all_list = CONF['DEFAULTS']['bms'] + CONF['DEFAULTS']['reimagevms']
        for inventory in all_list:
            mgmt_ip = get_ip(CONF[inventory]['management_address'])
            cmd = 'ping -c 4 %s'%(mgmt_ip)
            res = self.sm_vm.execute_cmd(cmd, timeout=30)
            if re.search(r'4 received', res, re.M|re.I):
                print "MGMT IP(%s)of (%s) is reachable from servermanager."%(mgmt_ip,inventory)
            else:
                print "\n"
                print "Command: %s"%(cmd)
                print "Response: %s"%(res)
                print "=============================================================================="
                print "MGMT IP(%s)of (%s) is not reachable from servermanager.check configuration"%(mgmt_ip, inventory)
                print "=============================================================================="
                sys.exit(1)
        #TO DO check connectivity from cc-host VM, os-host, BMS


    def provision_contrail(self):
        print "Started provisioning contrail on to the cluster"
        waiting(5)
        provision_list = CONF['DEFAULTS']['reimagevms']

        self.check_topology_connectivity()

        cmd = 'yes y | server-manager provision --cluster_id {0} {1}'.format(sk_cluster_id, contrail_pkg_id)
        res = self.sm_vm.execute_cmd(cmd, timeout=30)
        self.check_provision_status(provision_list)
        sys.exit(0)

    def check_provision_status(self, provision_list):
        queue = Queue.Queue()
        threads = []
        for svr in provision_list:
            svr = CONF[svr]['hostname']
            t = threading.Thread(target=self.provision_status, args=(svr,), name=svr)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        print "Completed contrail provision status verification"

    def provision_status(self, bmsname):
        count = 300
        expected_res = "provision_completed"
        for _ in range(count):
            #Get provision status
            res = self.sm_api.server_get(server_id=bmsname, status=True)
            print "Waiting for VM %s to get provisioned on %s."%(bmsname, sk_cluster_id)
            print "\n"
            print "Expected status:   %s        ::      Current status:  %s  "%(expected_res, res)
            if res == expected_res:
                print "VM %s is provisioned"%bmsname
                return
            else:
                print "Retry after 30sec"
                waiting(30)
        print "\n"
        print "================================================="
        print "VM %s did not get provisioned, hence exiting..." %bmsname
        print "================================================="
        sys.exit(1)
