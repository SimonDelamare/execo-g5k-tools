#!/usr/bin/env python
# import necessary libraries
from execo import *
from execo_g5k import *
from getpass import getuser

# define some constants (storage & distant sites are hard-coded as of now)
user = getuser()
storage_site = 'rennes'
distant_site = 'nancy'
logger.info('Benchmarking %s storage from %s site', storage_site, distant_site)

# perform a storage reservation on the storage site (rennes) using storage5k
get_chunk_size = SshProcess("storage5k -a chunk_size | cut -f 4 -d ' '",
                            storage_site).run()
chunk_size = int(get_chunk_size.stdout[1:])
number = 50 / chunk_size
get_storage = SshProcess('storage5k -a add -l chunks=' + str(number) + ',walltime=2:00:00', storage_site).run()
for s in get_storage.stdout.split('\n'):
    if 'OAR_JOB_ID' in s:
        storage_job_id = int(s.split('=')[1])
        break
logger.info('Storage available on %s: /data/%s_%s', storage_site, user,
            storage_job_id)

# reserve a node on the distant site (nancy)
logger.info('Reserving a node on %s', distant_site)
jobs = oarsub([(OarSubmission(resources="nodes=1",
                              job_type="deploy",
                              walltime="2:00:00",
                              name="Bench_storage5k"), distant_site)])

# deploy environment "wheezy-x64-nfs" on the reserved node
hosts = get_oar_job_nodes(jobs[0][0], distant_site)
logger.info('Deploying %s', hosts[0].address)

# enter the block for actually performing the benchmark tests
# catch exception if deployment was not successful
try:
    deployed, undeployed = deploy(Deployment(hosts, env_name="wheezy-x64-nfs"))
    hosts = list(deployed)
    if len(hosts) == 0:
        exit()
    # mount storage on deployed nodes
    logger.info('Mount storage on node')
    mount_storage = SshProcess('mount storage5k.%s.grid5000.fr:data/%s_%s /mnt/'
                                % (storage_site, user, storage_job_id), hosts[0],
                                connection_params={'user': 'root'}).run()
    # perform benchs
    logger.info('Perform bench write')
    bench_write = SshProcess('dd if=/dev/zero of=/mnt/test.out bs=64M count=200 conv=fdatasync oflag=direct',
                             hosts[0]).run()
    print bench_write.stdout.strip().split('\n')[-1].split()[7]
    print bench_write.start_date
    print bench_write.end_date

    logger.info('Perform bench read')
    bench_read = SshProcess('dd if=/mnt/test.out of=/dev/null bs=64M count=200 conv=fdatasync iflag=direct',
                            hosts[0]).run()
    print bench_read.stdout.strip().split('\n')[-1].split()[7]
    print bench_read.start_date
    print bench_read.end_date

finally:
    # destroying jobs (storage and node reservations)
    logger.info('Destroying jobs')
    oardel([(storage_job_id, storage_site), (jobs[0][0], distant_site)])
