Deploy opencontrail as POC on 1 Server:
========================================

Topology:
==========

Steps:
========
Setup the servers as per the topology

Make physical connection (management, IPMI, Internet)

Assign IP address to IPMI interface to all the servers

Configure TOR switch and External GW

Install Ubuntu 14.04.4 base OS on Server 1

Configure internet facing interface

With root user, execute the next steps

Install git package, apt-get update && apt-get install -y git

Clone this repo 

Change directory, cd opencontrail-poc-server_1

Copy below packages into artifacts folder 
[contrail-install-packages_3.2.2.0-33mitaka_all.deb
contrail-server-manager-installer_3.2.2.0-33-ubuntu-14-04mitaka_all.deb
ubuntu-14.04.4-server-amd64.iso
ubuntu-14.04-server-cloudimg-amd64-disk1.img]

Run setup_jumphost.sh [./setup_jumphost.sh]

Modify the configuration file [conf/poc_env.conf], refer above Github link for reference file

Run smgr_provision.sh [./smgr_provision.sh]

Run contrail_provision.sh [./contrail_provision.sh]

Run post_deployment.sh [./post_deployment.sh]
