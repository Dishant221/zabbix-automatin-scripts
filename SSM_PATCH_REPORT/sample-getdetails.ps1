param (
    [Parameter(Position=0, Mandatory=$true)]
    [string]$ProfileName
)

function Get-EBS-VolumeSize ($BlockDeviceMappings)
{
    $VolSize = 0
    foreach($device in $BlockDeviceMappings)
    {
        $VolSize = $VolSize + (Get-EC2Volume -ProfileName $ProfileName  -Region $Region.Region -VolumeId $device.Ebs.VolumeId -ErrorAction SilentlyContinue).Size
    }
    
    return $VolSize
}

Import-Module ".\LOG-FILER.psm1" -DisableNameChecking

$logfilepath = (Get-Location).Path + "\Log\"+$ProfileName + "_" +(Get-Date).ToString("yyyy_MM_dd") +"_Log.txt"

$CSVFilePath = (Get-Location).Path + "\Files\"+ $ProfileName + "\"
$EC2InstancesCSV = $CSVFilePath + $ProfileName + "_EC2Instances_" + (Get-Date).ToString("yyyy_MM_dd_HH_mm")+".csv"
$EC2InstancesMcAddCSV = $CSVFilePath + $ProfileName + "_EC2Instances_McAdd_" + (Get-Date).ToString("yyyy_MM_dd_HH_mm")+".csv"

$null = New-Item .\Files\$ProfileName -ItemType Directory -Force -ErrorAction SilentlyContinue
$null = Remove-Item .\Files\$ProfileName\*.* -ErrorAction SilentlyContinue

Log-filer -Message "-------------------------- START-----------------------------" -logfile $logfilepath 
Log-filer -Message "Get Regions..." -logfile $logfilepath 

$Regions = Get-AWSRegion -IncludeChina 

$InstanceDetailsList = @()
$InstanceMacAddressesList = @()

foreach($Region in $Regions)
{
    try
    {
        Log-filer -Message "Get EC2 instances for profile $ProfileName and region $Region" -logfile $logfilepath        

        $InstanceIds = (Get-EC2Instance -ProfileName $ProfileName -Region $Region.Region -ErrorAction SilentlyContinue).Instances.InstanceId

        if ($null -eq $InstanceIds)
        {
            continue
        }

        $InstanceList =  New-Object -TypeName 'System.Collections.ArrayList'       

        foreach ($i in $InstanceIds)
        {
            $ec2Instance = Get-EC2Instance -InstanceId $i -ProfileName $ProfileName -Region $Region.Region
            $null = $InstanceList.Add($ec2Instance)
        }

        $ec2DetailsList = $InstanceList | ForEach-Object {
            try
            {
                $properties = $null
                $InstanceId  = $_.Instances[0].InstanceId
                $properties = [ordered]@{    
                    InstanceID = $_.Instances[0].InstanceId
                    #Name = ($_.Instances[0].Tags | Where-Object Key -EQ "Name").Value
                    Name = ( $_.Instances[0].Tags | Where-Object { $_.Key -eq "Name" } | Select-Object -ExpandProperty Value -ErrorAction SilentlyContinue | Select-Object -First 1)
                    CreatedOn = ([datetime]::Parse($_.Instances[0].LaunchTime))
                    PrivateIP = $_.Instances[0].PrivateIpAddress    
                    PublicIp = $_.Instances[0].PublicIpAddress  
                    PublicDnsName = $_.Instances[0].PublicDnsName 
                    PrivateDnsName = $_.Instances[0].PrivateDnsName 
                    SubnetId = $_.Instances[0].SubnetId
                    KeyName = $_.Instances[0].KeyName
                    InstanceType = $_.Instances[0].InstanceType
                    AmiID = $_.Instances[0].ImageId 
                    Hypervisor = $_.Instances[0].Hypervisor
                    Cores = $_.Instances[0].CpuOptions[0].CoreCount * $_.Instances[0].CpuOptions[0].ThreadsPerCore
                    MemoryMB = (Get-EC2InstanceType -InstanceType $_.Instances[0].InstanceType -ProfileName $ProfileName -Region $Region.Region -ErrorAction SilentlyContinue | select -ExpandProperty MemoryInfo | Select SizeInMiB).SizeInMiB
                    StorageGB = Get-EBS-VolumeSize ($_.Instances[0].BlockDeviceMappings) 
                    Platform = $_.Instances[0].Platform
                    VirtualizationType = $_.Instances[0].VirtualizationType
                    Architecture = $_.Instances[0].Architecture
                    State = $_.Instances[0].State.Name
                    StateReason = $_.Instances[0].StateReason.Message
                    ENV = ($_.Instances[0].Tags | Where-Object Key -EQ "CI:Env").Value
                    PURPOSE = ($_.Instances[0].Tags | Where-Object Key -EQ "CI:Purpose").Value
                    HubID = ($_.Instances[0].Tags | Where-Object Key -EQ "CI:HubID").Value
                    MonitoringState = $_.Instances[0].Monitoring.MonitoringState.Value
                    AVZ = $_.Instances[0].Placement.AvailabilityZone
                    Region = $Region
                    Profile = $ProfileName
                }
            }
            catch
            {
                $Msg = "Instance Id:" + $InstanceId + " Exception: " + $_.Exception.Message
                Log-filer -Message $Msg -logfile $logfilepath
            }  
            if ($properties -ne $null)
            { 
                New-Object -TypeName PSObject -Property $properties
            }
        }

        $InstanceDetailsList += $ec2DetailsList

        $ec2MacAddresses = $InstanceList | ForEach-Object {
            foreach ($nic in $_.Instances[0].NetworkInterfaces)
            {
                $nicDetails = [ordered]@{    
                    InstanceID = $_.Instances[0].InstanceId
                    Name = ($_.Instances[0].Tags | Where-Object Key -EQ "Name").Value
                    Region = $Region
                    Profile = $ProfileName
                    MacAddress = $nic.MacAddress
                    Groups = ($nic.Groups | foreach {$_.GroupName }) -join ";"
                    NetworkInterfaceId = $nic.NetworkInterfaceId
                    SubnetId = $nic.SubnetId
                    VpcId = $nic.VpcId
                    InterfaceType = $nic.InterfaceType
                }
                New-Object -TypeName PSObject -Property $nicDetails
            }            
        }

        $InstanceMacAddressesList += $ec2MacAddresses

    }
    catch
    {
        $Msg = "Failed to get Availability Zones for region " + $Region.Region + ". Reason:" + $_.Exception.Message
        Log-filer -Message $Msg -logfile $logfilepath
    }    
}

# Write the CSV headers if no data found
if ($InstanceDetailsList.Count -eq 0) {
    $headers = "Profile,Region,AVZ,Hypervisor,InstanceID,AmiID,Name,CreatedOn,InstanceType,Cores,MemoryMB,StorageGB,Platform,State,StateReason,ENV,PURPOSE,HubID,PublicIp,PublicDnsName,PrivateIP,PrivateDnsName"
    $headers | Out-File -FilePath $EC2InstancesCSV -Encoding utf8
} else {
    $InstanceDetailsList | Select Profile,Region,AVZ,Hypervisor,InstanceID,AmiID,Name,CreatedOn,InstanceType,Cores,MemoryMB,StorageGB,Platform,State,StateReason,ENV,PURPOSE,HubID,PublicIp,PublicDnsName,PrivateIP, PrivateDnsName | Export-Csv $EC2InstancesCSV -Append -NoTypeInformation
}

if ($InstanceMacAddressesList.Count -eq 0) {
    $headers = "Profile,Region,InstanceID,Name,MacAddress,Groups,NetworkInterfaceId,SubnetId,VpcId,InterfaceType"
    $headers | Out-File -FilePath $EC2InstancesMcAddCSV -Encoding utf8
} else {
    $InstanceMacAddressesList | Select Profile,Region,InstanceID,Name,MacAddress,Groups,NetworkInterfaceId,SubnetId,VpcId,InterfaceType | Export-Csv $EC2InstancesMcAddCSV -Append -NoTypeInformation
}

Move-Item $CSVFilePath\*.* -Destination \\nfsserver.chg.prod.e2open.com\NFS_CI_SFTP\e2Export01\ci-sftp\CI_SFTP\ci-sftp\inbound\AWS\IN -Force 

Log-filer -Message "-------------------------- END-----------------------------" -logfile $logfilepath
