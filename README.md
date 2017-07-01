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

With root user, execute the next steps

Clone this repo  

Change directory, cd <repo-folder>

Copy contrail and servermanager packages into artifacts folder

Run setup_jumphost.sh [./setup_jumphost.sh]

Modify the configuration file [conf/poc_env.conf], refer above Github link for reference file

Run smgr_provision.sh [./smgr_provision.sh]

Run contrail_provision.sh [./contrail_provision.sh]

Run post_deployment.sh [./post_deployment.sh]
