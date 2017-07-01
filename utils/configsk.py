import os
import sys
from oslo_config import cfg
import helpers

CONF = cfg.CONF

class configSetup(object):

    def __init__(self):
        pass

    def set_base_config_options(self):

        DEFAULTS = cfg.OptGroup('DEFAULTS')
        default_opts = [
                cfg.StrOpt(name = 'ntp_servers', help = 'NTP server', required = True),
                cfg.StrOpt(name = 'dns_servers', help = 'DNS server', required = True),
                cfg.StrOpt(name = 'dns_search', help = 'Domain name', default = "example.net", required = True),
                cfg.StrOpt(name = 'root_username', help = 'Root User', required = True),
                cfg.StrOpt(name = 'root_password', help = 'Root Password', required = True),

                cfg.StrOpt(name = 'cluster_netmask', help = 'contrail cluster netmask', required = True),
                cfg.StrOpt(name = 'cluster_gateway', help = 'contrail cluster gateway', required = True),
                cfg.StrOpt(name = 'sm_network', help='DHCP Template network and netmask', required = True),
                cfg.StrOpt(name = 'sm_ext_address', help = 'SM external IP address', required = True),
                cfg.StrOpt(name = 'sm_ext_gateway', help = 'SM external gateway address', required = True),

                cfg.ListOpt(name = 'bms', help = 'Physical Servers', required = True),
                cfg.ListOpt(name = 'vms', help = 'Virtual Machines', required = True),
                cfg.ListOpt(name = 'reimagevms', help = 'Re-image Virtual Machines', required = True),
                cfg.StrOpt(name = 'contrail_asn', help = 'contrail_ASN #', required = True),
                cfg.StrOpt(name = 'contrail_os_webui_passwd', help = 'contrail and openstack_webui_passwd', required = True),
                cfg.StrOpt(name = 'contrail_mysql_passwd', help = 'contrail mysql_passwd', required = True),
                cfg.StrOpt(name = 'ubuntuimage', help = 'ubuntu iso image', required = True),
                cfg.StrOpt(name = 'contrailimage', help = 'contrail image', required = True),
                cfg.StrOpt(name = 'cloudimage', help = 'ubuntu cloud image', required = True),
                cfg.StrOpt(name = 'cirrosimage', help = 'cirros image', required = True),
                cfg.StrOpt(name = 'smimage', help = 'sm image', required = True)
                ]
        CONF.register_group(DEFAULTS)
        CONF.register_opts(default_opts, group=DEFAULTS)

    def set_deploy_virtual_server_config_options(self):

        for virtual_server in CONF['DEFAULTS']['vms']:
            VIRTUALSERVER = cfg.OptGroup(virtual_server)
            virtual_server_opts = [
                    cfg.StrOpt(name = 'management_address', help = 'mgmt ip of server', required = True),
                    cfg.StrOpt(name = 'management_interface', help = 'mgmt nic of server', required = True),
                    cfg.StrOpt(name = 'management_mac', help = 'mgmt mac address', required = True),
                    cfg.StrOpt(name = 'ctrldata_address', help = 'mgmt ip of server', required = True),
                    cfg.StrOpt(name = 'ctrldata_interface', help = 'mgmt nic of server', required = True),
                    cfg.StrOpt(name = 'ctrldata_mac', help = 'mgmt mac address', required = True),
                    cfg.StrOpt(name = 'gateway', help = 'gateway address to reach vMX loopback', required = True),
                    cfg.StrOpt(name = 'dns-search', help = 'dns-search', required = True),
                    cfg.StrOpt(name = 'dns-servers', help = 'dns-servers', required = True),
                    cfg.StrOpt(name = 'hostname', help = 'hostname', required = True),
                    cfg.StrOpt(name = 'local_user', help = 'local_user', required = True),
                    cfg.StrOpt(name = 'local_password', help = 'local_password', required = True),
                    cfg.StrOpt(name = 'memory', help = 'memory of the VM', required = True),
                    cfg.StrOpt(name = 'vcpus', help = 'vcpus of the VM', required = True),
                    cfg.StrOpt(name = 'harddisk', help = 'hardisk size of the VM', required = True),
                    cfg.StrOpt(name = 'partition', help = 'parition of the VM', required = True),
                    cfg.StrOpt(name = 'roles', help = 'contrail roles to be run on this VM', required = True)
                 ]
            CONF.register_group(VIRTUALSERVER)
            CONF.register_opts(virtual_server_opts, group=VIRTUALSERVER)

    def set_deploy_physical_server_config_options(self):

        for physical_server in CONF['DEFAULTS']['bms']:
            PHYSICALSERVER = cfg.OptGroup(physical_server)
            physical_server_opts = [
                    cfg.StrOpt(name = 'ipmi_address', help = 'IPMI ip of server', required = True),
                    cfg.StrOpt(name = 'ipmi_username', help = 'IPMI username', required = True),
                    cfg.StrOpt(name = 'ipmi_password', help = 'IPMI password', required = True),
                    cfg.StrOpt(name = 'management_address', help = 'mgmt ip of server', required = True),
                    cfg.StrOpt(name = 'management_interface', help = 'mgmt nic of server', required = True),
                    cfg.StrOpt(name = 'management_mac', help = 'mgmt mac address', required = True),
                    cfg.StrOpt(name = 'ctrldata_address', help = 'mgmt ip of server', required = True),
                    cfg.StrOpt(name = 'ctrldata_interface', help = 'mgmt nic of server', required = True),
                    cfg.StrOpt(name = 'ctrldata_mac', help = 'mgmt mac address', required = True),
                    cfg.StrOpt(name = 'dns-search', help = 'dns-search', required = True),
                    cfg.StrOpt(name = 'dns-servers', help = 'dns-servers', required = True),
                    cfg.StrOpt(name = 'hostname', help = 'hostname', required = True),
                    cfg.StrOpt(name = 'local_user', help = 'local_user', required = True),
                    cfg.StrOpt(name = 'local_password', help = 'local_password', required = True),
                    cfg.StrOpt(name = 'partition', help = 'parition of the server', required = True),
                    cfg.StrOpt(name = 'roles', help = 'contrail roles to be run on this VM', required = True)
                 ]
            CONF.register_group(PHYSICALSERVER)
            CONF.register_opts(physical_server_opts, group=PHYSICALSERVER)

    def load_configs(self, config_files=[]):
        project_root = helpers.get_project_root()
        default_cfg_files = []
        for cfile in config_files:
            default_cfg_files.append(os.path.join(project_root, cfile))
        CONF(args=sys.argv[1:], project='contrail pockit', default_config_files=default_cfg_files)
