#!/usr/bin/env bash

provision_sm_function () {
    DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
    export PYTHONPATH=$PYTHONPATH:$DIR

    if [ `whoami` != "root" ]; then
        echo "must run as root, try \"sudo su\" and re-run"
        exit -1
    fi
    
    #check CPU supports virtualization
    virt=$(egrep -c '(vmx|svm)' /proc/cpuinfo)
    if [ $virt != 0 ] ; then
        echo "CPU supports hardware virtualization"
    else
        echo "============================================"
        echo "CPU does not support hardware virtualization"
        echo "============================================"
        exit 1
    fi
    
    kvm_op=$(kvm-ok)
    if echo "$kvm_op" | grep -q "NOT"; then
        echo "==============================="
        echo "BIOS virtualization not enabled"
        echo "==============================="
        exit 1
    else 
        echo "BIOS virtualization is enabled"
    fi

    #install required packages before provisioning VM and deploying SM on it
    apt-get update
    apt-get install -y sysfsutils python-pip python-dev libffi-dev apache2 libssl-dev
    apt-get install -y qemu-kvm libvirt-bin ubuntu-vm-builder bridge-utils 
    apt-get install -y qemu-utils virtinst virt-manager 
    apt-get install -y cloud-utils cloud-init
    
    #check if extbr is created or not
    brctl show | grep 'extbr' &> /dev/null
    if [ $? == 0 ]; then
        echo "Bridge interface (extbr) is created and configured"
    else
        echo "======================================================================================"
        echo "Bridge interface (extbr) is not created, run ./setup_jumphost.sh before moving further"
        echo "======================================================================================"
        exit 1
    fi

    #create bridge for mgmt and ctrl_data interfaces
    brctl show | grep 'mgmtbr' &> /dev/null
    if [ $? == 0 ]; then
        echo "Management bridge (mgmtbr) is already created"
    else
        echo "Creating management bridge (mgmtbr)"
        brctl addbr mgmtbr
    fi
    
    brctl show | grep 'ctrldatabr' &> /dev/null
    if [ $? == 0 ]; then
        echo "Control_Data bridge  (ctrldatabr)is already created"
    else
        echo "Creating control_data bridge (ctrldatabr)"
        brctl addbr ctrldatabr
    fi
    
    #create ssh-keygen for users
    su - root -c "echo |ssh-keygen -t rsa"
    readarray -t users <<< "$(cat /etc/passwd | cut -d: -f 1,3,6 | grep "/home" | grep "[1-9][0-9][0-9][0-9]" | cut -d: -f1)"
    for user in "${users[@]}"
    do
        su - $user -c "echo |ssh-keygen -t rsa"
    done

    #log file
    path_to_log_file=$DIR/logs/$1 

    source $DIR/.pockit/bin/activate
    
    echo
    echo "*******************************************************************"
    echo "Creating Virtual Machine and deploying ServerManager on it"
    echo
    echo "This may take a while...."
    echo
    echo "*******************************************************************"
    
    python -u $DIR/smgr/sk_smgr.py
    if [ $? -eq 1 ]; then
        echo "================================================================="
        echo "Either VM creation or ServerManager deployment encountered errors"
        echo "Please check log file at $path_to_log_file for errors"
        echo "================================================================="
        exit 1
    else
        echo
        echo "**************************************************************************"
        echo "VM creation and ServerManager deployment successfully completed, Proceed to
re-image VM, BMS and provision contrail by doing ./contrail_provision.sh"
        echo
        echo "**************************************************************************"
        exit 0
    fi
}

log_file_name="smgr_provision_log"
new_log_file="$log_file_name-$(date "+%Y_%m_%d_%H_%M_%S").txt"
provision_sm_function $new_log_file 2>&1 | tee -a logs/$new_log_file
