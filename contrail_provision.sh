#!/usr/bin/env bash

deploy_contrail_function () {
    DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
    export PYTHONPATH=$PYTHONPATH:$DIR


    if [ `whoami` != "root" ]; then
        echo "must run as root, try \"sudo su\" and re-run"
        exit -1
    fi

    #log file
    path_to_log_file=$DIR/logs/$1 

    source $DIR/.pockit/bin/activate

    echo
    echo "************************************************"
    echo "Re-imaging the cluster and provisioning contrail"
    echo
    echo "This may take a while............................"
    echo 
    echo "************************************************"

    python -u $DIR/contrail/sk_contrail.py
    if [ $? -eq 1 ]; then
        echo
        echo "======================================================="
        echo "Either re-image or provisioning contrail encountered errors"
        echo "Please check log file at $path_to_log_file for errors"
        echo "======================================================="
        exit 1
    else
        echo
        echo "**********************************************************"
        echo "Re-imaging and provisoning contrail successfully completed,
proceed to run post deployment script by doing ./post_deployment.sh"
        echo
        echo "**********************************************************"
        exit 0
    fi
}

log_file_name="contrail_provision_log"
new_log_file="$log_file_name-$(date "+%Y_%m_%d_%H_%M_%S").txt"
deploy_contrail_function $new_log_file 2>&1 | tee -a logs/$new_log_file
