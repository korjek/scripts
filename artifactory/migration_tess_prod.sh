#/bin/bash
art_user="admin"
art_pass="SidFielp"
k8s_worker="kube1.tess.elex.be"
k8s_master="kubemaster.tess.elex.be"
netapp_server="netapp-tess.tess.elex.be"
netapp_user="admin"
netapp_pass="SfcaGN34hhqGE5Ac"
art_nfs_volume="artifactory_prod"

port="$(kubectl -s ${k8s_master} describe svc artifactory-mlx | grep NodePort: | awk '{print $3}' | cut -d'/' -f 1)"
server_port="${k8s_worker}:${port}"
now=`date +%Y_%m_%d_%H_%M_%S`
log="/home/yko/scripts/import_export/logs/migration_${server_port}_$now.log"
storage_summary_before_export="/home/yko/scripts/import_export/logs/storage_summary_before_export_${server_port}_$now.txt"
storage_summary_after_import="/home/yko/scripts/import_export/logs/storage_summary_after_import_${server_port}_$now.txt"

echo "Starting migration" | tee -a $log
echo "Migration starting time is `date +"%T %m %Y"`" | tee -a $log
echo "Server and port are: ${server_port}" | tee -a $log

##Make snapshot of Artifactory NFS volume first"
#echo "Creating snapshot of the NFS Volume" | tee -a $log
#sshpass -p${netapp_pass} ssh -o StrictHostKeyChecking=no ${netapp_user}@${netapp_server} "volume snapshot create -vserver netappvs1 -volume ${art_nfs_volume} -snapshot db_migration"
#if [ $? == 0 ]; then
#    echo "Snapshot of the NFS Volume created successfully" 2>&1| tee -a $log
#else
#    echo "FAILED to create snaphost of the NFS Volume. Exiting..." 2>&1| tee -a $log
#    exit 1
#fi

#Get storage summary before export
echo "Storage summary before export" | tee -a $log
exit_code="$(curl -X GET -w "\n%{http_code}" "http://${server_port}/artifactory/api/storageinfo" -u${art_user}:${art_pass} | tee -a ${storage_summary_before_export} | tail -n 1)"
if [ $? == 0 ] && [ "${exit_code}" == "200" ]; then
    echo "Sucessfully got storage info. Check ${storage_summary_before_export}" 2>&1| tee -a $log
else
    echo "FAILED to get storage info. Exiting..." 2>&1| tee -a $log
    exit 1
fi

#Disable Artifactory replication
exit_code="$(curl -X POST -w "\n%{http_code}" "http://${server_port}/artifactory/api/system/replications/block" -u${art_user}:${art_pass} 2>&1| tee -a $log | tail -n 1)"
if [ $? == 0 ] && [ "${exit_code}" == "200" ]; then
    echo "Artifactory replication disabled" 2>&1| tee -a $log
else
    echo "FAILED to disable Artifactory replication. Exiting..." 2>&1| tee -a $log
    exit 1
fi

#Export 
echo "Starting export" | tee -a $log
echo "Export starting time is `date +"%T %m %Y"`" | tee -a $log

export_parameters=$(cat <<EOF
{
    "exportPath" : "/opt/jfrog/artifactory/backup",
    "includeMetadata" : true,
    "createArchive" : false,
    "excludeContent" : true,
    "failOnError" : true
}
EOF
)

exit_code="$(curl -X POST -w "\n%{http_code}" "http://${server_port}/artifactory/api/export/system" -d "${export_parameters}" -H "Content-Type: application/json" -u ${art_user}:${art_pass} 2>&1| tee -a $log | tail -n 1)"
if [ $? == 0 ] && [ "${exit_code}" == "200" ]; then
    echo "Export SUCCESSFULLY finished" | tee -a $log
else
    echo "Export FAILED. Exiting..." | tee -a $log
    exit 1
fi
echo "Export finishing time is `date +"%T %m %Y"`" | tee -a $log

#Change db config on Artifactory to use PosgresDB
kubectl -s ${k8s_master} exec -i $(kubectl -s ${k8s_master} get po | grep artifactory | awk '{ print $1 }') -- cp -p /opt/jfrog/artifactory/etc/db.properties.pg /opt/jfrog/artifactory/etc/db.properties
if [ $? == 0 ]; then
    echo "Successfully changed DB config" | tee -a $log
else
    echo "FAILED to change DB config. Exiting..." | tee -a $log
    exit 1
fi

pod_name_derby="$(kubectl -s ${k8s_master} get po | grep artifactory | awk '{ print $1 }')"

#Restarting Artifactory
kubectl -s ${k8s_master} delete po $(kubectl -s ${k8s_master} get po | grep artifactory | awk '{ print $1 }') --grace-period=0
if [ $? == 0 ]; then
    echo "Successfully killed old pod" | tee -a $log
else
    echo "FAILED to kill old pod. Exiting..." | tee -a $log
    exit 1
fi

#Check that new pod has been started
sleep 5
pod_name_pg="$(kubectl -s ${k8s_master} get po | grep artifactory | awk '{ print $1 }')"
echo "Pod name with Derby: ${pod_name_derby}" | tee -a $log 
echo "Pod name with Postgres: ${pod_name_pg}" | tee -a $log

if [ "${pod_name_pg}" == "${pod_name_derby}" ]; then
    echo "New pod name is the same as old one. Exiting..." | tee -a $log
    exit 1
else
    echo "New pod name is different as old one. This means pod has been restarted. Continue..." | tee -a $log
fi

#Give some time for Artifactory to start up
sleep 120

art_pass_default="password"

#Disable Artifactory replication
exit_code="$(curl -X POST -w "\n%{http_code}" "http://${server_port}/artifactory/api/system/replications/block" -u${art_user}:${art_pass_default} 2>&1| tee -a $log | tail -n 1)"
if [ $? == 0 ] && [ "${exit_code}" == "200" ]; then
    echo "Artifactory replication disabled" 2>&1| tee -a $log
else
    echo "FAILED to disable Artifactory replication. Exiting..." 2>&1| tee -a $log
    exit 1
fi

#Check if Artifactory uses new DB
until [ ! -z  "${current_db}" ]; do
    current_db="$(kubectl -s ${k8s_master} exec -i $(kubectl -s ${k8s_master} get po | grep artifactory | awk '{ print $1 }') -- grep '^type' /opt/jfrog/artifactory/etc/db.properties | cut -d'=' -f 2)"
    current_db=$(tr -dc '[[:print:]]' <<< "${current_db}")
done

if [ "${current_db}" == "postgresql" ]; then
    echo "Artifactory is using PostgresDB now" | tee -a $log
else
    echo "Artifactory is still using old DB. Exiting..." | tee -a $log
    exit 1
fi 

#Find out the name of the folder where export has been executed to
src_folder="$(kubectl -s ${k8s_master} exec -i $(kubectl -s ${k8s_master} get po | grep artifactory | awk '{ print $1 }') -- ls /opt/jfrog/artifactory/backup/ | grep -v 'backup-daily')"

#Import
echo "Starting import " | tee -a $log
echo "Starting time is `date +"%T %m %Y"`" | tee -a $log

import_parameters=$(cat <<EOF
{
    "importPath":"/opt/jfrog/artifactory/backup/${src_folder}",
    "includeMetadata":"true",
    "verbose":"true"
}
EOF
)

exit_code="$(curl -X POST -w "\n%{http_code}" "http://${server_port}/artifactory/api/import/system" -d "$import_parameters" -H "Content-Type: application/json" -u ${art_user}:${art_pass_default} 2>&1| tee -a $log | tail -n 1)"
if [ $? == 0 ] && [ "${exit_code}" == "200" ]; then
    echo "Import SUCCESSFULLY finished" | tee -a $log
else
    echo "Import FAILED. Exiting..." | tee -a $log
    exit 1
fi
echo "Import finishing time is `date +"%T %m %Y"`" | tee -a $log

#Get storage summary after import
echo "Storage summary after import" | tee -a $log
exit_code="$(curl -X GET -w "\n%{http_code}" "http://${server_port}/artifactory/api/storageinfo" -u${art_user}:${art_pass} | tee -a ${storage_summary_after_import} | tail -n 1)"
if [ $? == 0 ] && [ "${exit_code}" == "200" ]; then
    echo "Sucessfully got storage info. Check ${storage_summary_after_import}" 2>&1| tee -a $log
else
    echo "FAILED to get storage info." 2>&1| tee -a $log
fi

echo "Migration completed" | tee -a $log
echo "Migration finishing time is `date +"%T %m %Y"`" | tee -a $log

exit 0
