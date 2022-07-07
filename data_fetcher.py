import sys
import glob
from scp import SCPClient
import paramiko


#Data fetcher from Bruker Host PC
#Collects the bruker scan files given the subject id

def main(server, password, local_path, animal_id):
    # server = ""
    port = 22
    # password = ""
    user = "mri"
    # animal_id = ""
    client = createSSHClient(server, port, user, password)
    print(client)
    files=find_data(client, animal_id)
    scp = scpClient(client)
    # local_path = "./fetcher_test/"
    #Set below the directory where the scan data is originally stored
    remote_path = "/opt/PV6.0.1/data/mri/"
    local_files=get_local_data_list(animal_id)
    get_data(client, files, local_path, remote_path,local_files)

def createSSHClient(server, port, user, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client


def find_data(client, animal_id):
    stdin, stdout, stderr = client.exec_command("ls -l /opt/PV6.0.1/data/mri/ | grep " + animal_id)
                                                # "| grep /opt/PV6.0.1/data/mri/" + animal_id)
    print(stdout)
    files = []
    for line in stdout:
        files.append(line.split(" ")[-1].split("\n")[0])
    print(files)
    return files

def scpClient(client):
    scp = SCPClient(client.get_transport(), progress=progress)
    return scp

def get_data(client, files, local_path, remote_path, local_files):
    scp = SCPClient(client.get_transport(),  progress=progress)
    for file in files:
        if not file in local_files:
            print("Fetching " + file)
            full_path = remote_path + file
            scp.get(full_path, local_path=local_path, recursive=True)
            print("complete")
    scp.close()

def get_local_data_list(animal_id):
    file_list=glob.glob("./samri_bindata/" + animal_id +"/*")
    files = []
    for file in file_list:
        files.append(file.split("/")[-1])

    return(files)



def progress(filename, size, sent):
    sys.stdout.write("%s's progress: %.2f%%   \r" % (filename, float(sent)/float(size)*100) )

if __name__ == '__main__':
    main()

