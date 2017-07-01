import os
import sys
from oslo_config import cfg
from utils import helpers
from utils.configsk import configSetup
from provision_vm_and_sm import createVMSM

CONF = cfg.CONF
SK_ENV_FILE = 'poc_env.conf'

class prepSetup(object):

    def __init__(self):
        pass

    def check_config_file_exists(self):
        install_dir = helpers.from_project_root('conf/')
        cfg_file = os.path.join(install_dir, SK_ENV_FILE)
        if not os.path.exists(os.path.join(install_dir, SK_ENV_FILE)):
            print "Missing required configuration file {}".format(cfg_file)
            sys.exit(1)
        print "Configuration file {} exists".format(cfg_file)


if __name__ == '__main__':

    # preparation work before spining VM and provisioning SM
    prep = prepSetup()
    prep.check_config_file_exists()

    #read conf file
    config = configSetup()
    config.set_base_config_options()

    try:
        config.load_configs(['conf/{}'.format(SK_ENV_FILE)])
        print "Loaded configuration file successfully"
    except cfg.RequiredOptError as e:
        print "Missing required input in poc_env file, {0}: {1}".format(SK_ENV_FILE, e)
        sys.exit(1)

    config.set_deploy_physical_server_config_options()
    config.set_deploy_virtual_server_config_options()

    #create VM
    vmsm = createVMSM()
    vmsm.copy_ucloud_image()
    vmsm.create_sm_vm()

    #deploy SM on the above created VM
    vmsm.deploy_sm_on_vm()
    vmsm.verify_sm_on_vm()
    sys.exit(0)
