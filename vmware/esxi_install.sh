#!/bin/bash
#Color! 
if /usr/bin/tty -s; then
	TPUT=/usr/bin/tput 
	GREEN=$( $TPUT setaf 2)
	RED=$( $TPUT setaf 1)
	NORMAL=$( $TPUT op)
	BLUE=$( $TPUT setaf 6)
	YELLOW=$( $TPUT setaf 3)
fi

#Don't annoy us with hostkeythings when we want to sshpass you meany!
SSH="ssh -o StrictHostKeyChecking=no"
SCP="scp -o StrictHostKeyChecking=no"

#Root is required 
if [ `whoami` != 'root' ]; then
        echo -e "${RED}You must be root to run this script. Execute sudo su - and try again.${end}${NORMAL}"
        exit 1
fi

cd /usr/local/bin/esxi-sai

#import functions used for tftpboot part
functions="functions_vm.ash"

if [ ! -e "$functions" ]; then 
    echo -e "${RED}Required functions files can not be found in: $functions${end}${NORMAL}"
    exit 1
fi
source $functions

#import config file
config_file="esxi_install.cfg"

if [ ! -e "$config_file" ]; then
    echo -e "{RED}Required config file can not be found in: $config_file${end}${NORMAL}"
    exit 1
fi
source $config_file

#Get our arguments and validate them 
while getopts ":m:h:b:l:p:u:v:" opt; do
        case $opt in
        m)
                MAC=`echo ${OPTARG,,}`
		[[ "$MAC" =~ ^([0-9a-f]{2}-){5}[0-9a-f]{2}$ ]] && MS=1 || echo -e "${RED}Invalid MAC address or format. Please format like: 00-AD-85-C6-85-23${end}${NORMAL}"
                ;;
        h) 
                HOST=${OPTARG} 
		HS=1
                ;; 
	b)	
		BLADEBAY=${OPTARG}
		;;
	l)	
		BLADEMM=${OPTARG}
		;;
	p)	
		BLADEPASS=${OPTARG}
                ;;
	u)	
		BLADEUSER=${OPTARG}
                ;;
	v)
		ESXIVERSION=${OPTARG}
		[[ "$ESXIVERSION" =~ ^(5\.5)|(6\.5)$ ]] && ES=1 || echo -e "${RED}Incorrect ESXi version. 5.5 or 6.5 only available${end}${NORMAL}"
		;;
	?)
		echo "This data has not been provided: ${OPTARG}"
        esac
done

#check if we have everything
if [ ! $MS ] || [ ! $HS ] || [ ! $ES ]; then
	echo -e "${RED}Missing Parameter${end}${NORMAL}"
	echo "Usage: esxi_install -m MA-CA-DD-RE-SS -h hostname.site.elex.be -v 5.5"
	echo "Example: esxi_install -m 00-AD-85-C6-85-23- -h mynewhost.colo.elex.be -v 5.5"
	exit 1
fi 

mkdir -p /mnt/esxi${ESXIVERSION}_install_mnt
if [ "${ESXIVERSION}" = "5.5" ]; then 
	mount ksstorage:/vol/kickstart/kickstart/esxi/${ESXIVERSION}.5.update02 /mnt/esxi${ESXIVERSION}_install_mnt >> /dev/null
else
	mount ksstorage:/vol/kickstart/kickstart/esxi/${ESXIVERSION} /mnt/esxi${ESXIVERSION}_install_mnt >> /dev/null
fi

#check if another install is in progress
if [ -e /mnt/esxi${ESXIVERSION}_install_mnt/sai/install.lock ]; then
	lockage=$(( `date +%s` - `stat -L --format %Y /mnt/esxi${ESXIVERSION}_install_mnt/sai/install.lock` ))
	if [ "$lockage" -lt "600" ]; then
		time_left=$[600-$lockage]
		echo -e "${RED}Another install is still in progress. Please wait another${end}${NORMAL} $time_left ${RED}seconds and try again.${end}${NORMAL}"
		exit 1
	fi
fi

#Check if Blade credentials are correct
if [[ "$BLADEBAY" && "$BLADEMM" && "$BLADEPASS" && "$BLADEUSER" ]]; then
	sshpass -p "${BLADEPASS}" $SSH ${BLADEUSER}@${BLADEMM} exit > /dev/null || { echo -e "${RED}Login to BladeMM FAILED. Please check username/password${end}${NORMAL}" && exit 1; }
fi

#determine our env.
HOSTSHORT=`echo $HOST | awk -F '.' '{print $1}'`
ENVIRONMENT="prod"
[[ "$HOSTSHORT" =~ -test$ ]] && ENVIRONMENT="test"
[[ "$HOSTSHORT" =~ -uat$ ]] && ENVIRONMENT="uat"

IPADDR=`host $HOST | awk '/has address/ { print $4 }'`

#getting some other stuff needed for the network config:
SITE="$( cut -d '.' -f 2 <<< "$HOST" )"
SITE="${SITE^^}"
GATEWAY=${SITE}_GATEWAY
GATEWAY=${!GATEWAY}
DNS2=${SITE}_DNS2
DNS2=${!DNS2}
NAGSITE=${SITE}_NAGSITE
NAGSITE=${!NAGSITE}
SHORTSITE=${SITE}_SHORTSITE
SHORTSITE=${!SHORTSITE}
LONGSITE=${SITE}_LONGSITE
LONGSITE=${!LONGSITE}
DATASTORE_QTY=${SITE}_DATASTORE_QTY
DATASTORE_QTY=${!DATASTORE_QTY}
#Check if provided hostname is valid (site exist)
for site in $AVAILABLE_SITES; do
	if [[ "$SITE" == "$site" ]]; then
		real_site=1
		break
	fi
done

[[ "real_site" -ne "1" ]] && echo -e "${RED}There is no such sitei${end}${NORMAL} $SITE.\n${RED}Please check hostname${end}${NORMAL} $HOST ${RED}and try again${end}${NORMAL}" && exit 1

#Generate a random password
PASSWORD=`date +%s | sha256sum | base64 | head -c 8`

#define some vars we'll be using
TFTP_API="http://tftpboot.${LONGSITE}/1.0/mac"
DNS=`host dns1.${LONGSITE} | awk '/has address/ { print $4 }'`

#Lets get ready to rumble!
echo " "
echo -e "${BLUE}************${end}${NORMAL}"
echo -e "${BLUE}* ${end}${YELLOW}Starting the ESXi ${ESXIVERSION} installation process ${end}${NORMAL}"
echo -e "${BLUE}* ${end}${YELLOW}Server: ${end}${NORMAL}$HOST"
echo -e "${BLUE}* ${end}${YELLOW}Put this password in the password file: ${end}${NORMAL}$PASSWORD"
echo -e "${BLUE}***************** ${end}${NORMAL}"
echo -e "${BLUE}* ${end}${YELLOW}Setting permissions on netapp for datastore volume ${end}${NORMAL}"

#Set correct exports for cluster ontap filers
FILERNAME="netapp-${SHORTSITE}.${LONGSITE}"
sshpass -p "$NETAPPCLPWD" $SSH nagios@$FILERNAME "vserver export-policy rule create -policyname ds1test -clientmatch $IPADDR -rorule any -rwrule any -allow-suid true -allow-dev true -protocol nfs -superuser any" 2> /tmp/esxi_mnts > /tmp/esxi_mnts2
sshpass -p "$NETAPPCLPWD" $SSH nagios@$FILERNAME "vserver export-policy rule create -policyname ds1uat -clientmatch $IPADDR -rorule any -rwrule any -allow-suid true -allow-dev true -protocol nfs -superuser any" 2> /tmp/esxi_mnts > /tmp/esxi_mnts2
sshpass -p "$NETAPPCLPWD" $SSH nagios@$FILERNAME "vserver export-policy rule create -policyname ds1prod -clientmatch $IPADDR -rorule any -rwrule any -allow-suid true -allow-dev true -protocol nfs -superuser any" 2> /tmp/esxi_mnts > /tmp/esxi_mnts2

#create the custom kickstart file, based on KS.CFG template & make a lock file that makes sure no other install overwrites it for the first 20 mins
touch /mnt/esxi${ESXIVERSION}_install_mnt/sai/install.lock

#if it still exists from a previous install; delete it.
[[ -e /mnt/esxi${ESXIVERSION}_install_mnt/sai/KS.CFG ]] && rm -f /mnt/esxi${ESXIVERSION}_install_mnt/sai/KS.CFG
cp /mnt/esxi${ESXIVERSION}_install_mnt/KS.CFG /mnt/esxi${ESXIVERSION}_install_mnt/sai/KS.CFG

#Remove some lines which are used by the non automated install
sed -i '/bootproto=dhcp/d' /mnt/esxi${ESXIVERSION}_install_mnt/sai/KS.CFG
sed -i '/change_after_install/d' /mnt/esxi${ESXIVERSION}_install_mnt/sai/KS.CFG

#Add the lines that set our network config, root password and shared datastores
sed -i "s/\#NETWORK/\#NETWORK\nnetwork --bootproto=static --addvmportgroup=false --device=vmnic0 --ip=$IPADDR --netmask=255.255.240.0 --gateway=$GATEWAY --nameserver=$DNS,$DNS2 --hostname=$HOST\nrootpw $PASSWORD/" /mnt/esxi${ESXIVERSION}_install_mnt/sai/KS.CFG 
while [ ${DATASTORE_QTY} -gt 0 ]; do
	sed -i "s/\#DATASTORE/\#DATASTORE\nesxcli storage nfs add --host netappvs1_lif${DATASTORE_QTY}.${LONGSITE} --share \/ds${DATASTORE_QTY}test  --volume-name ds${DATASTORE_QTY}test\nesxcli storage nfs add --host netappvs1_lif${DATASTORE_QTY}.${LONGSITE} --share \/ds${DATASTORE_QTY}uat --volume-name ds${DATASTORE_QTY}uat\nesxcli storage nfs add --host netappvs1_lif${DATASTORE_QTY}.${LONGSITE} --share \/ds${DATASTORE_QTY}prod --volume-name ds${DATASTORE_QTY}prod/" /mnt/esxi${ESXIVERSION}_install_mnt/sai/KS.CFG
	let DATASTORE_QTY-=1
done

#Set license key for ESXi
if [ "${ESXIVERSION}" = "5.5" ]; then
        LICENSE=ESXI55_LICENSE
	LICENSE=${!LICENSE}
else
        LICENSE=ESXI65_LICENSE
	LICENSE=${!LICENSE}
fi

sed -i "s/\#LICENSE/\#LICENSE\nvim-cmd vimsvc\/license --set ${LICENSE}/" /mnt/esxi${ESXIVERSION}_install_mnt/sai/KS.CFG

#Activate the tftpboot entry for our install
if [ "${ESXIVERSION}" = "5.5" ]; then 
	tftp_manage_mac "$TFTP_API" "{\"label\":\"esxi5-sai\", \"mac\":\"01-$MAC\"}" "POST" > /dev/nul
else
	tftp_manage_mac "$TFTP_API" "{\"label\":\"esxi65-sai\", \"mac\":\"01-$MAC\"}" "POST" > /dev/nul
fi

#Give feedback that the server is ready to be installed
umount /mnt/esxi${ESXIVERSION}_install_mnt
rmdir /mnt/esxi${ESXIVERSION}_install_mnt

# Set server to boot with PXE and reboot it if necessary data has been provided
if [[ "$BLADEBAY" && "$BLADEMM" && "$BLADEPASS" && "$BLADEUSER" ]]; then
	echo -e "${BLUE}*${end}${YELLOW} Rebooting host to boot with PXE.${end}${NORMAL}"
	sshpass -p "${BLADEPASS}" $SSH ${BLADEUSER}@${BLADEMM} > /dev/null <<EOF
	env -T blade[${BLADEBAY}]
	bootseq nw cd usb hd0
	power -cycle
EOF
else
	echo -e "${BLUE}*${end}${YELLOW} Reboot host to PXE manually.${end}${NORMAL}"
fi

#Start 10 minute countdown in which we can start our unattended install. The KS file has to be read before the timer runs out, else it risks being overwritten by another install.
i="600"
while [ $i -gt 0 ]
do
	echo -en "\r${BLUE}* ${end}${YELLOW}Install available for${end}${NORMAL} $i${end}${YELLOW} seconds    ${end}${NORMAL}"
	sleep 120
	i=$[$i - 120]
done

#Remove the install image
tftp_manage_mac "$TFTP_API" "{\"mac\":\"01-$MAC\"}" "DELETE" > /dev/null
echo -en "\r${BLUE}* ${end}${YELLOW}Install no longer available.     ${end}${NORMAL}"

# Set server's device boot order if necessary data has been provided
if [[ "$BLADEBAY" && "$BLADEMM" && "$BLADEPASS" && "$BLADEUSER" ]]; then
	sshpass -p "${BLADEPASS}" $SSH ${BLADEUSER}@${BLADEMM} > /dev/null <<EOF
	env -T blade[${BLADEBAY}]
	bootseq cd usb hd0 nw
EOF
fi

#We will wait till we can do an ssh login on our new server, then we know it is ready
echo " "
echo -e "${BLUE}************************* ${end}${NORMAL}"
echo -e "${BLUE}* ${end}${YELLOW}Waiting for the server to be ready to perform post install operations.${end}${NORMAL}"
echo "" > /tmp/esxi_user
echo "" > /tmp/esxi_user_err
while ! grep -q "successfully" /tmp/esxi_user; do

#When we manage to log in, create our esxnagios user, which nagios uses for its checks
	sshpass -p "$PASSWORD" $SSH $ESXI_USER@$HOST "mkdir -p /home/esxnagios ; /usr/lib/vmware/auth/bin/adduser -D esxnagios ; echo $ESXINAGPWD | passwd esxnagios --stdin ; vim-cmd vimsvc/auth/entity_permission_add vim.Folder:ha-folder-root esxnagios false ReadOnly true" 2> /tmp/esxi_user_err > /tmp/esxi_user

#Login will fail when we do a reinstall, cause of conflicting keys... so delete the conflicting key and try again
	if grep -q "Offending " /tmp/esxi_user_err ; then 
		line_number=`grep "Offending " /tmp/esxi_user_err | awk -F ':' '{print $2}'`
		line_number=`echo "${line_number//[$'\t\r\n ']}"`
		sed -i -e "${line_number}d" /root/.ssh/known_hosts
	fi
	sleep 5
done
echo -e "${BLUE}*${end}${YELLOW} Added Nagios user${end}${NORMAL}"

#Set our standard startup/shutdown delays
sshpass -p "$PASSWORD" $SSH $ESXI_USER@$HOST "vim-cmd hostsvc/autostartmanager/update_defaults 600 120 GuestShutdown"
echo -e "${BLUE}*${end}${YELLOW} Set default startup / shutdown times${end}${NORMAL}"
sshpass -p "$PASSWORD" $SSH $ESXI_USER@$HOST 'sed -i "s/<SystemDefaults>/<SystemDefaults>\n<enabled>true<\/enabled>/" /etc/vmware/hostd/vmAutoStart.xml'

echo -e "${BLUE}*${end}${YELLOW} Checking Nagios config${end}${NORMAL}"

#checkout/update nagios config
CURRENT_DIR=`pwd`

if [[ "$ENVIRONMENT" == "prod" ]] ; then
	NAGIOSENV="production"
	NAGIOSENV2="STABLE"
else
	NAGIOSENV=${ENVIRONMENT}
	NAGIOSENV2=`echo ${NAGIOSENV^^}`
fi

if [ -d nagios3 ]; then
        cd nagios3 && cvs -q update -dP > /dev/null 2>&1
        cd $CURRENT_DIR
else
        read -p "Please provide you login details for nagios checkout: "
        cvs -d :pserver:$REPLY@$CVS_SERVER:/var/cvsit login
        cvs -d :pserver:$REPLY@$CVS_SERVER:/var/cvsit co nagios3 > /dev/null
fi

#check if the host already exists; and is still accurate
cd nagios3
NAGIOSHOST=`find * | grep $HOST | grep host.cfg`
if [ -e "$NAGIOSHOST" ] && grep -q "vmesx_hosts" $NAGIOSHOST && grep -q "$IPADDR" $NAGIOSHOST; then 
	echo -e "${BLUE}*${end}${YELLOW} Host already in Nagios.${end}${NORMAL}"	
else
	echo -e "${BLUE}*${end}${YELLOW} Host has to be added to Nagios:${end}${NORMAL}"
	if [ -e "$NAGIOSHOST" ]; then
	        echo -e "${BLUE}*${end}${YELLOW} Deleting existing host...${end}${NORMAL}"
		cvs tag -d $NAGIOSENV2 $NAGIOSHOST > /dev/null
		rm -f $NAGIOSHOST
		cvs commit -m "Removed $NAGIOSHOST" $NAGIOSHOST > /dev/null
	fi
	./nagios-addesxihost.sh -g $NAGSITE -h $HOST -a $IPADDR -t vmesx_hosts -d server -e $NAGIOSENV2 
	echo ""
fi
cd $CURRENT_DIR

# Joine Host to vCenter
echo -e "${BLUE}*${end}${YELLOW} Joining host to vCenter.${end}${NORMAL}"
export PYTHONPATH=/usr/lib/python2.7:/usr/lib/python2.7/lib-dynload:/usr/local/lib/python2.7/dist-packages:/usr/lib/python2.7/dist-packages
/usr/bin/python2.7 joinHosttoVCenter.py $VCENTER_HOST $VCENTER_USER $VCENTER_PWD $HOST $ESXI_USER $PASSWORD $LONGSITE `echo ${ENVIRONMENT^^}`

#installing the vaai plugin
echo -e "${BLUE}*${end}${YELLOW} Installing Netapp plugin.${end}${NORMAL}"
sshpass -p "$PASSWORD" $SCP NetAppNasPlugin.v21.vib $ESXI_USER@$HOST:/tmp > /dev/null
sshpass -p "$PASSWORD" $SSH $ESXI_USER@$HOST "esxcli software vib install -v /tmp/NetAppNasPlugin.v21.vib" > /dev/null

sleep 30
echo -e "${BLUE}*${end}${YELLOW} Rebooting host to apply config changes.${end}${NORMAL}"
sshpass -p "$PASSWORD" $SSH $ESXI_USER@$HOST "reboot"
echo -e "${BLUE}*************************${end}${NORMAL}-Melexis IT 2014-${end}${BLUE}***** ${end}${NORMAL}" 
