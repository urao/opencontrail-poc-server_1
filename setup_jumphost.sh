#!/usr/bin/env bash

setup_function () {
    echo "Installing dependencies and setting up installer environment"

    if [ `whoami` != "root" ]; then
        echo "must run as root, try \"sudo su\" and re-run"
        exit 1
    fi
    
    DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
    export PYTHONPATH=$PYTHONPATH:$DIR
    
    #verify the default route and ping the gateway
    gateway=$(ip route | awk '/default/ {print $3}')
    ping "$gateway" -c 4 > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "Gateway IP $gateway is reachable"
    else
        echo 
        echo "==================================================================="
        echo "Gateway IP $gateway is not reachable, please check the configuration"
        echo "==================================================================="
        exit 1
    fi
    
    #check internet is accessible, http google.com 
    ipaddr='8.8.8.8'
    ping "$ipaddr" -c 4 > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "Internet is reachable via external IP address ($ipaddr)"
    else
        echo 
        echo "=========================================================="
        echo "Internet is not reachable, please check routes to internet"
        echo "=========================================================="
        exit 1
    fi
    
    url='www.google.com'
    ping "$url" -c 4 > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "Internet is reachable via URL ($url), DNS is working"
    else
        echo 
        echo "=========================================================="
        echo "Internet is not reachable, please check DNS configuration"
        echo "=========================================================="
        exit 1
    fi
    
    #check ubuntu version
    expected_os_ver='14.04.4'
    current_ver=$(cat -n /etc/lsb-release | tail -n 1 | awk '{print $3}')
    check_os_version() {
        [ "$1" == "`echo -e "$1\n$2" | sort -V | tail -n1`" ]
    }
    output=$(check_os_version $expected_os_ver $current_ver && echo "yes" || echo "no")
    if [ $output == "yes" ]; then
        echo "Host OS version matches with that of the expected OS version $expected_os_ver."
    else
        echo 
        echo "========================================================================="
        echo "Host OS version does not match with expecting OS version $expected_os_ver"
        echo "========================================================================="
        exit 1
    fi

    apt-get update
    
    cur_intf=$(/sbin/ip route | awk '/default/ {print $5}')
    ip_intf=$(/sbin/ip -o -4 addr list $cur_intf | awk '{print $4}')
    ip_only=$(/sbin/ip -o -4 addr list $cur_intf | awk '{print $4}' | cut -d/ -f1)
    subnet_mask=$(/sbin/ifconfig $cur_intf | grep Mask | cut -d":" -f4)
    dns_server=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}' | head -n1)
    dns_search=$(cat /etc/resolv.conf | grep search | awk '{print $2}')
    
    echo "Check the bridge configuration.."
    bridgename="extbr"
    sudo brctl show
    if [ $? -eq 0 ]; then
        echo "bridge-utils package is installed"
        brctl show | grep $bridgename 
        if [ $? -eq 0 ]; then
            echo "Bridge interface extbr, exists"
        else
            echo "Bridge interface extbr does not exists, hence creating the same"
            brctl addbr extbr
        fi
        grep "$bridgename" /etc/network/interfaces
        if [ $? -eq 0 ]; then
            echo "Bridge interface extbr related configuration is updated in /etc/network/interfaces file."
        else
            echo "Updating /etc/network/interface with extbr interface configuration"
            /sbin/ifconfig $bridgename $ip_only netmask $subnet_mask up && brctl addif $bridgename $cur_intf && ifup $bridgename && /sbin/ifconfig $cur_intf 0.0.0.0 && /sbin/route add default gw $gateway
            #modify /etc/network/interfaces file
            mv /etc/network/interfaces /etc/network/interfaces.bak
            cat << EOF >> /etc/network/interfaces
                
            auto lo
            iface lo inet loopback
                
            auto $cur_intf
            iface $cur_intf inet manual

            auto $bridgename
            iface $bridgename inet static
               address $ip_only
               netmask $subnet_mask
               gateway $gateway
               dns-nameservers $dns_server
               dns-search $dns_search
               bridge_ports $cur_intf
               bridge_stp off
               bridge_fd 0
               bridge_maxwait 0
EOF
        fi
    else
        echo "bridge-utils package is not installed, installing it"
        apt-get install -y bridge-utils
        #create internet/external bridge and add interface of the default route this it
        brctl addbr $bridgename && /sbin/ifconfig $bridgename $ip_only netmask $subnet_mask up && brctl addif $bridgename $cur_intf && ifup $bridgename && /sbin/ifconfig $cur_intf 0.0.0.0 && /sbin/route add default gw $gateway
        if [ $? != 0 ]; then
            echo 
            echo "=============================================================="
            echo "Bridge interface creation failed!!!! check logs at location $1"
            echo "=============================================================="
            exit 1
        else
            echo "Bridge interface extbr is created successfully.."
        fi
        
        
        #modify /etc/network/interfaces file
        echo "Modifying /etc/network/interfaces file with extbr bridge details"
        mv /etc/network/interfaces /etc/network/interfaces.bak
        cat << EOF >> /etc/network/interfaces
        
        auto lo
        iface lo inet loopback
        
        auto $cur_intf
        iface $cur_intf inet manual

        auto $bridgename
        iface $bridgename inet static
            address $ip_only
            netmask $subnet_mask
            gateway $gateway
            dns-nameservers $dns_server
            dns-search $dns_search
            bridge_ports $cur_intf
            bridge_stp off
            bridge_fd 0
            bridge_maxwait 0

EOF
    fi
    
    #enable SSH to allow root to login
    sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/g' /etc/ssh/sshd_config
    echo 'UseDNS no' >> /etc/ssh/sshd_config
    service ssh restart
    
    #install required pkgs
    apt-get install -y software-properties-common
    apt-get install -y apache2 cpu-checker
    apt-get install -y python-pip python-dev build-essential libssl-dev libffi-dev
    pip install virtualenv
    
    if [ -d "$DIR/.pockit" ]; then
        rm -rf $DIR/.pockit
    fi
    
    virtualenv $DIR/.pockit --system-site-packages
    source $DIR/.pockit/bin/activate
    
    pip install --no-cache-dir --ignore-installed -r $DIR/requirements.txt
    
    #copy of images existing in webserver folder
    if [ -d "$DIR/artifacts" ]; then
        if [ -d "/var/www/html/pockit_images" ]; then
            rm -rf /var/www/html/pockit_images
        fi
        sudo cp -r $DIR/artifacts /var/www/html/pockit_images
    fi

    echo 
    echo "**********************************************************************************"
    echo "Setup completed, next step to provision servermanager by doing ./smgr_provision.sh"
    echo "**********************************************************************************"
    echo 
    exit 0
}

log_file_name="setup_jumphost_log"
current_time=$(date "+%Y_%m_%d_%H_%M_%S")
new_log_file="$log_file_name-$(date "+%Y_%m_%d_%H_%M_%S").txt"
setup_function $new_log_file 2>&1 | tee -a logs/$new_log_file
