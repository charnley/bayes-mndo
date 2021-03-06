#!/bin/bash
#!
#! Example SLURM job script for Wilkes2 (Broadwell, ConnectX-4, P100)
#! Last updated: Mon 13 Nov 12:06:57 GMT 2017

#! sbatch directives begin here ###############################
#! Name of the job:
#SBATCH -J amm-testing-heavy
#! Which project should be charged (NB Wilkes2 projects end in '-GPU'):
#SBATCH -A LEE-SL3-GPU
#! How many whole nodes should be allocated?
#SBATCH --nodes=1
#! How many (MPI) tasks will there be in total?
#! Note probably this should not exceed the total number of GPUs in use.
#SBATCH --ntasks=1
#! Specify the number of GPUs per node (between 1 and 4; must be 4 if nodes>1).
#! Note that the job submission script will enforce no more than 3 cpus per GPU.
#SBATCH --gres=gpu:1
#! How much wallclock time will be required?
#SBATCH --time=10:00:00
#! What types of email messages do you wish to receive?
#SBATCH --mail-type=BEGIN,END,FAIL
#! Uncomment this to prevent the job from being requeued (e.g. if
#! interrupted by node failure or system downtime):
##SBATCH --no-requeue

#! Do not change:
#SBATCH -p pascal

#! sbatch directives end here (put any additional directives above this line)

#! Notes: Charging is determined by GPU number*walltime.

#! Modify the settings below to specify the application's environment, location and launch method.

#! Optionally modify the environment seen by the application
#! (note that SLURM reproduces the environment at submission irrespective of ~/.bashrc):
. /etc/profile.d/modules.sh                # Leave this line (enables the module command)
module purge                               # Removes all modules still loaded
module load rhel7/default-gpu              # REQUIRED - loads the basic environment

#! Insert additional module load commands after this line if needed:

#! Full path to application executable:
application="python"

#! Run options for the application:
#! --- Single Job ---
options="src/scipy_optim"
#! submit with `sbatch hpc/gpu_submit`
# --- Array Job ---
# options="-m src.job_array $SLURM_ARRAY_TASK_ID"
#! submit with `sbatch --array=0-15 hpc/gpu_submit`
#! then in the Python script, read the task id via:
#! task_id = int(sys.argv[1])
#! and use it something like this:
#! models, labels = ["RF", "MAP", "HMC", "Dropout"], ["rho", "seebeck", "kappa", "zT"]
#! model, label = tuple(itertools.product(models, labels))[task_id]

CMD="$application $options"

cd $SLURM_SUBMIT_DIR

echo -e "JobID: $SLURM_JOB_ID\n"
echo "Time: `date`"
echo "Running on master node: `hostname`"
echo "Current directory: `pwd`"
echo -e "\nNodes allocated: numtasks=$numtasks, numnodes=$numnodes"
echo -e "\nExecuting command: $CMD\n\n=================="

eval $CMD