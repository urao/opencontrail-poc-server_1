import os
import sys
import re
import Queue
import threading
from oslo_config import cfg
from jinja2 import Environment, FileSystemLoader
from netaddr import IPNetwork
from time import sleep, strftime

from utils.helpers import execute, from_project_root, get_project_root
from utils.remoteoperations import RemoteConnection

CONF = cfg.CONF

sk_img_path = '/var/www/html/pockit_images'
internet_ip = '8.8.8.8'
internet_www = 'www.google.com'
kill = False
stop = False

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

class createVMSM(object):

    def __init__(self):
        global jinja_env
        jinja_env = Environment(loader=FileSystemLoader(from_project_root('smgr')))

        # configure server1 bridge ips
        svr1 = CONF['DEFAULTS']['bms'][0]
        print "Checking ntp server reachability from jumphost(%s)"%(svr1)
        sm_ntp_server = CONF['DEFAULTS']['ntp_servers']
        res = os.system('ping -c 3 ' + sm_ntp_server)
        if res == 0:
            print "NTP server %s is reachable"%(sm_ntp_server)
        else:
            print "Response: %s"%(res)
            print "NTP server %s is not reachable"%(sm_ntp_server)
            sys.exit(1)
        print "Checking mgmtbr, ctrldatabr bridge configuration on jumphost server."
        m_intf = CONF[svr1]['management_interface']
        c_intf = CONF[svr1]['ctrldata_interface']
        m_ip = get_ip(CONF[svr1]['management_address'])
        m_netmask = get_netmask(CONF[svr1]['management_address'])
        c_ip = get_ip(CONF[svr1]['ctrldata_address'])
        c_netmask = get_netmask(CONF[svr1]['ctrldata_address'])
        command = 'brctl show mgmtbr'
        res1 = execute(command, ignore_errors=False)
        command = 'brctl show ctrldatabr'
        res2 = execute(command, ignore_errors=False)
        if None not in (re.search(r'%s' %m_intf,res1,re.M|re.I), re.search(r'%s' %c_intf,res2,re.M|re.I)):
            print "Jumphost server bridge interface configuration exists."
        else:
            print "Configuring jumphost server bridge interfaces. Begins.."
            command = '/sbin/ifconfig %s 0.0.0.0 up' %(m_intf)
            execute(command, ignore_errors=False)
            command = '/sbin/ifconfig mgmtbr %s netmask %s up' %(m_ip, m_netmask)
            execute(command, ignore_errors=False)
            command = 'brctl addif mgmtbr %s' %(m_intf)
            execute(command, ignore_errors=False)

            command = '/sbin/ifconfig %s 0.0.0.0 up' %(c_intf)
            execute(command, ignore_errors=False)
            command = '/sbin/ifconfig ctrldatabr %s netmask %s up' %(c_ip, c_netmask)
            execute(command, ignore_errors=False)
            command = 'brctl addif ctrldatabr %s' %(c_intf)
            execute(command, ignore_errors=False)
            print "Configuring jumphost server bridge interfaces. Ends.."

        #update /etc/network/interfaces file with this ip
        cmd = 'cat /etc/network/interfaces'
        res = execute(cmd, ignore_errors=False)
        if re.search(r'mgmtbr|ctrldatabr', res, re.M|re.I):
            print "mgmtbr/ctrldatabr interface configuration exists"
        else:
            print "mgmtbr/ctrldatabr interface configuration does not exists, hence configuring"
            command = 'sudo echo -ne \"auto {}\n iface {} inet manual\n auto mgmtbr\n iface mgmtbr inet static\n address {}\n netmask {}\n bridge_ports {}\n bridge_stp off\n bridge_fd 0\n bridge_maxwait 0\n\" >> /etc/network/interfaces'.format(m_intf, m_intf, m_ip, m_netmask, m_intf)
            execute(command, ignore_errors=False)
            command = 'sudo echo -ne \"auto {}\n iface {} inet manual\n auto ctrldatabr\n iface ctrldatabr inet static\n address {}\n netmask {}\n bridge_ports {}\n bridge_stp off\n bridge_fd 0\n bridge_maxwait 0\n\" >> /etc/network/interfaces'.format(c_intf, c_intf, c_ip, c_netmask, c_intf)
            execute(command, ignore_errors=False)

    def copy_ucloud_image(self):
        print "Coping ubuntu cloud image to libvirt/images folder."
        waiting(10)
        global cloudimg
        cloudimg = CONF['DEFAULTS']['cloudimage']
        command = 'cp %s/%s /var/lib/libvirt/images/' %(sk_img_path, cloudimg)
        execute(command, ignore_errors=False)

    def create_sm_vm(self):
        vm = 'servermanager'
        vm_name = CONF[vm]['hostname']
        sm_m_ip = get_ip(CONF[vm]['management_address'])
        global sm_creation
        sm_creation = False

        #Check if the SM VM is created and service is UP
        command = 'virsh list | grep %s | awk \'{print $3}\''%(vm_name)
        res = execute(command, ignore_errors=True)
        vm_running = False
        if res == 'running':
            print "SM VM is created and UP and RUNNING"
            vm_running = True

        #check if VM is reachable if so, check service is running
        #ping SM
        vm_pingable = False
        res = os.system('ping -c 5 ' + sm_m_ip)
        if res == 0:
            print "Servermanger VM is UP and reachable"
            vm_pingable = True

            sm_local_user = CONF[vm]['local_user']
            sm_local_passwd = CONF[vm]['local_password']

            sm_vm = RemoteConnection()
            sm_vm.connect(sm_m_ip, username=sm_local_user, password=sm_local_passwd)
            cmd = 'sudo service contrail-server-manager status'
            res = sm_vm.execute_cmd(cmd, timeout=10)
            if re.search(r'not|unrecognized', res, re.M|re.I):
                sm_vm_service = False
            else:
                print "contrail-server-manager service is running."
                sm_vm_service = True
        else:
            print "Servermanager VM is not reachable or does not exists"


        if vm_running and vm_pingable and sm_vm_service:
            print "The existing servermanager VM is UP and RUNNING, hence not deleting and creating a new one"
        else:
            sm_creation = True
            print "Creating servermanager VM with name  "+vm_name

            print "Deleting existing servermanager VM"
            command = 'virsh destroy ' + vm_name
            execute(command, ignore_errors=True)
            waiting(3)
            command = 'virsh undefine ' + vm_name
            execute(command, ignore_errors=True)
            waiting(3)

            vncpasswd = CONF[vm]['local_password']
            OS = '--os-variant=ubuntutrusty --os-type=linux'
            ARCH = '--arch=x86_64'
            NET1 = '--network bridge=mgmtbr'
            NET2 = '--network bridge=extbr'
            Disk = '--boot hd'
            Gr = '--graphics vnc,password={} --noautoconsole'.format(vncpasswd)
            Cpu = '--vcpus=%s' % CONF[vm]['vcpus']
            Ram = '--ram=%s' % CONF[vm]['memory']
            Src = '--disk path=/var/lib/libvirt/images/%s.qcow2,format=qcow2,bus=virtio --import --autostart --disk path=/var/lib/libvirt/images/%s_init.iso,bus=virtio,device=cdrom' % (vm_name, vm_name)
    
            #print OS, ARCH, NET1, NET2, Disk, Gr, Cpu, Ram, Src
            command = 'cp -f /var/lib/libvirt/images/%s /var/lib/libvirt/images/%s.qcow2' % (cloudimg, vm_name)
            execute(command, ignore_errors=False)
            command = 'qemu-img resize /var/lib/libvirt/images/%s.qcow2 +%sG' % (vm_name, CONF[vm]['harddisk'])
            execute(command, ignore_errors=False)
    
            # create user-data and meta-data file
            print "Creating user-data and meta-data files to boot ubuntu cloud image. Begins.."
            vm_disk_path = '/root/sm_vm/{0}'.format(vm_name)
            command = 'rm -rf {0}'.format(vm_disk_path)
            execute(command, ignore_errors=False)
            waiting(3)
            command = 'mkdir -p {0}'.format(vm_disk_path)
            execute(command, ignore_errors=False)
    
            sm_root_password = CONF['DEFAULTS']['root_password']
            sm_dns_search = CONF[vm]['dns_search']
            sm_dns_server = CONF[vm]['dns_servers']
            sm_local_user = CONF[vm]['local_user']
            sm_local_passwd = CONF[vm]['local_password']
            sm_m_ip = get_ip(CONF[vm]['management_address'])
            sm_m_netmask = get_netmask(CONF[vm]['management_address'])
            sm_ext_ip = get_ip(CONF['DEFAULTS']['sm_ext_address'])
            sm_ext_netmask = get_netmask(CONF['DEFAULTS']['sm_ext_address'])
            sm_ext_gateway = CONF['DEFAULTS']['sm_ext_gateway']
            command = 'cat /home/{0}/.ssh/id_rsa.pub'.format(sm_local_user)
            sm_rsa_user = execute(command, ignore_errors=False)
            command = 'cat /root/.ssh/id_rsa.pub'.format(sm_local_user)
            sm_rsa_root = execute(command, ignore_errors=False)
    
            print "Creating user-data file required for cloud init image.."
            userdata_tmpl = jinja_env.get_template('user-data')
            userdata = userdata_tmpl.render(
                password=sm_root_password,
                local_user=sm_local_user,
                local_password=sm_local_passwd,
                dns_server=sm_dns_server,
                ssh_rsa_user=sm_rsa_user,
                ssh_rsa_root=sm_rsa_root,
                dns_search=sm_dns_search
            )
            fobj = open(vm_disk_path + '/user-data', 'w')
            if hasattr(userdata, '__iter__'):
                for data in userdata:
                    fobj.write(data)
                fobj.close()
            else:
                fobj.write(userdata)
                fobj.close()
    
            print "Creating meta-data file required for cloud init image.."
            metadata_tmpl = jinja_env.get_template('meta-data')
            metadata = metadata_tmpl.render(
                hostname=vm_name,
                mgmt_ip=sm_m_ip,
                mgmt_netmask=sm_m_netmask,
                ext_ip=sm_ext_ip,
                ext_netmask=sm_ext_netmask,
                ext_gateway=sm_ext_gateway
            )
            fobj = open(vm_disk_path + '/meta-data', 'w')
            if hasattr(metadata, '__iter__'):
                for data in metadata:
                    fobj.write(data)
                fobj.close()
            else:
                fobj.write(metadata)
                fobj.close()
            print "Creating user-data and meta-data files to boot ubuntu cloud image. Ends.."
    
            # Launch VM
            print "Launching servermanager VM..."
            cwddir = os.getcwd()
            command = 'cd {}'.format(vm_disk_path+'/')
            os.chdir(vm_disk_path)
            command = 'cloud-localds  -v  /var/lib/libvirt/images/{}_init.iso user-data meta-data'.format(vm_name)
            os.system(command)
            os.chdir(cwddir)
            command = 'virt-install {} {} {} {} {} {} {} {} {} --name={}'.format(OS, ARCH, NET1, NET2, Disk, Src, Gr, Cpu, Ram, vm_name)
            execute(command, ignore_errors=False)
            print "Launched servermanager VM, Waiting for the VM to come up...."
            self.verify_sm_vm(vm)

    def verify_sm_vm(self, vmname):
        count = 10
        sm_mgmt_ip = get_ip(CONF[vmname]['management_address'])
        for _ in range(count):
            #ping SM
            res = os.system('ping -c 3 ' + sm_mgmt_ip)
            if res == 0:
                print "Servermanger VM is UP and reachable"
                return
            else:
                print "Waiting for servermanager VM to come UP.."
                print "Retry after 30sec"
                waiting(30)
        print "\n"
        print "=================================================="
        print "ServerManager VM is not reachable, did not come up"
        print "=================================================="
        sys.exit(1)

    def create_dhcp_template(self, smname):

        print "Creating dhcp-template file required for servermanager deployment."

        sm_cidr = get_ip(CONF['DEFAULTS']['sm_network'])
        sm_cidr_netmask = get_netmask(CONF['DEFAULTS']['sm_network'])

        dhcp_tmpl = jinja_env.get_template('dhcp.template')
        userdata = dhcp_tmpl.render(
            sm_network=sm_cidr,
            sm_netmask=sm_cidr_netmask,
            gateway=CONF[smname]['gateway'],
            dns_server=CONF[smname]['dns_servers'],
            dns_search=CONF[smname]['dns_search']
         )
        fobj = open(sk_img_path + '/dhcp.template', 'w')
        if hasattr(userdata, '__iter__'):
            for data in userdata:
                fobj.write(data)
            fobj.close()
        else:
            fobj.write(userdata)
            fobj.close()

    def deploy_sm_on_vm(self):

        if sm_creation:
            print "Servermanager software deployment is started on VM..."

            vm = 'servermanager'
            sm_m_ip = get_ip(CONF[vm]['management_address'])
            sm_local_user = CONF[vm]['local_user']
            sm_local_passwd = CONF[vm]['local_password']
    
            #create dhcp.template file
            self.create_dhcp_template(vm)
    
            sm_img = CONF['DEFAULTS']['smimage']
            svr1 = CONF['DEFAULTS']['bms'][0]
            server1_mgmt_ip = get_ip(CONF[svr1]['management_address'])
    
            sm_vm = RemoteConnection()
            sm_vm.connect(sm_m_ip, username=sm_local_user, password=sm_local_passwd)
            cmd = 'eval echo ~$USER'
            sm_home_dir = sm_vm.execute_cmd(cmd, timeout=10)
    
            #check internet reachability from SM
            cmd = 'ping -c 4 %s'%internet_ip
            res = sm_vm.execute_cmd(cmd, timeout=10)
            if re.search(r'4 received', res, re.M|re.I):
                print "Internet IP (%s) is reachable from servermanager VM."%internet_ip
            else:
                print "\n"
                print "Command:%s"%(cmd)
                print "Response:%s"%(res)
                print "========================================================================="
                print "Internet IP (%s) is not reachable from servermanager...please check configuration"%internet_ip
                print "========================================================================="
                sys.exit(1)
    
            cmd = 'ping -c 4 %s'%internet_www
            res = sm_vm.execute_cmd(cmd, timeout=10)
            if re.search(r'4 received', res, re.M|re.I):
                print "Internet URL (%s) is reachable from servermanager VM."%internet_www
            else:
                print "\n"
                print "Command:%s"%(cmd)
                print "Response:%s"%(res)
                print "========================================================================="
                print "Internet URL (%s) is not reachable from servermanager...please check configuration"%internet_www
                print "========================================================================="
                sys.exit(1)
    
    
            #create dir images
            cmd = 'rm -rf images/; mkdir -p images'
            sm_vm.execute_cmd(cmd, timeout=10)
            cmd = 'rm -rf json-files/; mkdir -p json-files'
            sm_vm.execute_cmd(cmd, timeout=10)
    
            sm_vm.chdir(sm_home_dir+'/images/')
            jumphost_img_url = 'http://{}/pockit_images/'.format(server1_mgmt_ip)
            cmd = 'wget -q {0}{1} -O {1}'.format(jumphost_img_url,sm_img)
            if sm_vm.status_command(cmd) != 0:
                print "\n"
                print "Command:%s"%(cmd)
                print "=============================================================="
                print "Error in downloading servermanager build onto servermanager VM"
                print "=============================================================="
                sys.exit(1)
            else:
                print "Successfully downloaded servermanager build onto servermanager VM"
    
    
            cmd = 'sudo dpkg -i {0}/images/{1}'.format(sm_home_dir, sm_img)
            if sm_vm.status_command(cmd) != 0:
                print "\n"
                print "Command:%s"%(cmd)
                print "====================================================="
                print "Error in depackaging the servermanager debian package"
                print "====================================================="
                sys.exit(1)
            else:
                print "Successfully Depackaged the servermanager debian package"
    
            print "Starting setup.sh --all command, this will take a while"
	    global kill
	    global stop
            sm_vm.chdir('/opt/contrail/contrail_server_manager/')
            queue = Queue.Queue()
            t = threading.Thread(target=self.progress_bar_print, args=())
            t.start()
            try:
                #cmd = 'sudo ./setup.sh --sm={0}'.format(sm_img)
                cmd = 'sudo ./setup.sh --all'
                if sm_vm.status_command(cmd) != 0:
                    kill = True
                    stop = True
                    print "\n"
                    print "Command:%s"%(cmd)
                    print "======================================="
                    print "Error in running setup.sh --all command"
                    print "======================================="
                    sys.exit(1)
                else:
                    stop = True
                    print "\nSuccessfully completed running setup.sh --all command"
            except KeyboardInterrupt or EOFError:
	        print "entering keyboard error"
                kill = True
                stop = True
            sm_vm.chdir(sm_home_dir+'/json-files/')
            cmd = 'sudo wget -q {0}dhcp.template -O /etc/cobbler/dhcp.template'.format(jumphost_img_url)
            if sm_vm.status_command(cmd, timeout=90) != 0:
                print "\n"
                print "Command:%s"%(cmd)
                print "=========================================================="
                print "Error in copying dhcp.template file on to servermanager VM"
                print "=========================================================="
                sys.exit(1)
            else:
                print "Successfully copied dhcp.template file on to servermanager VM"
    
            cmd = 'sudo sed -i \'s/= authn_testing/= authn_configfile/g\' /etc/cobbler/modules.conf'
            sm_vm.execute_cmd(cmd, timeout=10)
            cmd = 'sudo sed -i \'/^cobbler_username/c\cobbler_username  \t= cobbler\' /opt/contrail/server_manager/sm-config.ini'
            sm_vm.execute_cmd(cmd, timeout=10)
            cmd = 'sudo sed -i \'/^cobbler_password/c\cobbler_password  \t= cobbler\' /opt/contrail/server_manager/sm-config.ini'
            sm_vm.execute_cmd(cmd, timeout=10)
            cmd = 'sudo cp /etc/contrail_smgr/cobbler/named.conf.options.u.sample /etc/bind/named.conf.options'
            sm_vm.execute_cmd(cmd, timeout=10)
            cmd = 'sudo cp /etc/contrail_smgr/cobbler/named.template.u.sample /etc/cobbler/named.template'
            sm_vm.execute_cmd(cmd, timeout=10)
    
            #comment ubuntu ntp servers in /etc/ntp.conf and add ntp_server
            sm_ntp_server = CONF['DEFAULTS']['ntp_servers']
            cmd = 'sudo sed -i \'/ubunt/s/^/#/\' /etc/ntp.conf'
            sm_vm.execute_cmd(cmd, timeout=10)
    
            cmd = 'echo server {} | sudo tee --append /etc/ntp.conf > /dev/null'.format(sm_ntp_server)
            sm_vm.execute_cmd(cmd, timeout=10)
    
            #restart ntp service
            cmd = 'sudo service ntp stop; sudo ntpdate {};sudo service ntp start'.format(sm_ntp_server)
            res = sm_vm.execute_cmd(cmd, timeout=30)
            waiting(10)
    
            cmd = 'sudo service contrail-server-manager status'
            res = sm_vm.execute_cmd(cmd, timeout=10)
            print "Servermanager software deployment ended."
            print "\n"
            print "Starting servermanager service on the VM"
            cmd = 'sudo service contrail-server-manager start'
            res = sm_vm.execute_cmd(cmd, timeout=10)
            waiting(20)
    
    def verify_sm_on_vm(self):
        sm_creation = True
        if sm_creation:
            print "\nVerifying contrail-server-manager service is running on the VM"

            vm = 'servermanager'
            sm_m_ip = get_ip(CONF[vm]['management_address'])
            sm_local_user = CONF[vm]['local_user']
            sm_local_passwd = CONF[vm]['local_password']
            svr1 = CONF['DEFAULTS']['bms'][0]
    
            sm_vm = RemoteConnection()
            sm_vm.connect(sm_m_ip, username=sm_local_user, password=sm_local_passwd)
            cmd = 'sudo service contrail-server-manager status'
            res = sm_vm.execute_cmd(cmd, timeout=10)
            #print res
            if re.search(r'not', res, re.M|re.I):
                print "\n"
                print "Command:%s"%(cmd)
                print "Response:%s"%(res)
                print "======================================================================"
                print "contrail-server-manager service is not running...please check the logs"
                print "======================================================================"
                sys.exit(1)
            else:
                print "contrail-server-manager service is running."
                sm_ext_ip = get_ip(CONF['DEFAULTS']['sm_ext_address'])
                print "Access to ServerManager web-ui from jumphost({}): https://{}:9143/".format(svr1,sm_m_ip)
                print "Do ssh tunnel command, ssh -f -N -L 9143:{}:9143 root@{}".format(sm_m_ip, sm_ext_ip)
                print "Access to ServerManager web-ui from laptop to monitor provisioning \
                        and health of servers: https://127.0.0.1:9143/"

    def progress_bar_print(self):
        global stop
        global kill

        print "Provisioning contrail-server-manager [           ]",
        print "\b"*12,
        sys.stdout.flush()
        i=0
        while stop != True:
            if (i%4) == 0:
                print "\b.",
            elif (i%4) == 1:
                print "\b.",
            elif (i%4) == 2:
                print "\b.",
            elif (i%4) == 3:
                print "\b.",

            sys.stdout.flush()
            sleep(5)
            i+=1
        if kill == True:
            print '\b\b\b\b ABORT!',
	    sys.exit(1)
        else:
	    pass
            #print '\b\bdone!',
