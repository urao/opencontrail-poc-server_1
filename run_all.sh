#!/usr/bin/env sh

echo 'Running the complete deployment scripts from here'
./setup_jumphost.sh && echo "Setup Jumphost done, Running ServerManager Provisioning" && ./smgr_provision.sh && echo "Provisioning ServerManager done, Running Contrail Provisioning" && ./contrail_provision.sh && echo "Provisioning Contrail done, Running Post deployment" && ./post_deployment.sh && echo "Post deployment done, Complete Contrail deployment, SUCCESSFULLY!!!!"
