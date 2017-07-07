#!/usr/bin/env bash

echo -e '---Running the complete deployment scripts from here---\n'
echo -e '---(1)Running the jumphost setup---\n'
./setup_jumphost.sh >/dev/null && echo -e "---(2)Setup Jumphost done, Running ServerManager Provisioning---\n" && ./smgr_provision.sh && echo -e "---(3)Provisioning ServerManager done, Running Contrail Provisioning---\n" && ./contrail_provision.sh && echo -e "---(4)Provisioning Contrail done, Running Post deployment---\n" && ./post_deployment.sh && echo -e "---(5)Post deployment done, Complete Contrail deployment, SUCCESSFULLY!!!!---\n"
