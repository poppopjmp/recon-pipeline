.. _install-ref-label:

Installation Instructions
=========================

There are two primary phases for installation:

* prior to the python dependencies being installed
* everything else

Manual Steps
############

First, the steps to get python dependencies installed in a virtual environment are as follows (and shown below)

Kali
----

.. code-block:: console

    sudo apt update
    sudo apt install pipenv


Ubuntu 18.04/20.04
------------------

.. code-block:: console

    sudo apt update
    sudo apt install python3-pip
    pip install --user pipenv
    echo "PATH=${PATH}:~/.local/bin" >> ~/.bashrc
    bash

Both OSs After ``pipenv`` Install
---------------------------------

.. code-block:: console

    git clone https://github.com/epi052/recon-pipeline.git
    cd recon-pipeline
    pipenv install
    pipenv shell


.. raw:: html

    <script id="asciicast-318395" src="https://asciinema.org/a/318395.js" async></script>

Everything Else
###############

After installing the python dependencies, the recon-pipeline shell provides its own :ref:`tools_command` command (seen below).
A simple ``tools install all`` will handle all installation steps.  Installation has **only** been tested on **Kali 2019.4 and Ubuntu 18.04/20.04**.

    **Ubuntu Note (and newer kali versions)**: You may consider running ``sudo -v`` prior to running ``./recon-pipeline.py``. ``sudo -v`` will refresh your creds, and the underlying subprocess calls during installation won't prompt you for your password. It'll work either way though.

Individual tools may be installed by running ``tools install TOOLNAME`` where ``TOOLNAME`` is one of the known tools that make
up the pipeline.

The installer does not maintain state.  In order to determine whether a tool is installed or not, it checks the `path` variable defined in the tool's .yaml file.  The installer in no way attempts to be a package manager.  It knows how to execute the steps necessary to install and remove its tools.  Beyond that, it's
like Jon Snow, **it knows nothing**.

Current tool status can be viewed using ``tools list``. Tools can also be uninstalled using the ``tools uninstall all`` command. It is also possible to individually uninstall them in the same manner as shown above.

.. raw:: html

    <script id="asciicast-343745" src="https://asciinema.org/a/343745.js" async></script>

Alternative Distros
###################

In v0.8.1, an effort was made to remove OS specific installation steps from the installer.  However, if you're
using an untested distribution (i.e. not Kali/Ubuntu 18.04/20.04), meeting the criteria below **should** be sufficient
for the auto installer to function:

- systemd-based system (``luigid`` is installed as a systemd service)
- python3.6+ installed

With the above requirements met, following the installation steps above starting with ``pipenv install`` should be sufficient.

The alternative would be to manually install each tool.

Docker
######

If you have Docker installed, you can run the recon-pipeline in a container with the following commands:

.. code-block:: console

        git clone https://github.com/epi052/recon-pipeline.git
        cd recon-pipeline
        docker build -t recon-pipeline .
        docker run -d \
            -v ~/docker/recon-pipeline:/root/.local/recon-pipeline \
            -p 8082:8082 \
            --name recon-pipeline \
            recon-pipeline


It is important to note that you should not lose any data during an update because all important information is saved to the ``~/docker/recon-pipeline`` location as specified by the ``-v`` option in the ``docker run`` command. If this portion of the command was not executed, data will not persist across container installations.

At this point the container should be running and you scan enter the shell with the following command:

.. code-block:: console

        docker exec -it recon-pipeline pipeline

Starting & Stopping
-------------------

In the event that you need to start or stop the container, you can do so with the following commands after having run the installation commands above once:

.. code-block:: console

    docker start recon-pipeline
    docker stop recon-pipeline

This is useful knowledge because Docker containers do not normally start on their own and executing the ``docker run`` command above again will result in an error if it is already installed.

Update
------

To update, you can run the following commands from inside the ``recon-pipeline`` folder cloned in the installation:

.. code-block:: console

    git pull
    docker stop recon-pipeline
    docker rm recon-pipeline

When complete, execute the inital installation commands again starting with ``docker build``.

Purpose and Usage of Each Tool and Task
#######################################

The recon-pipeline project integrates various tools and tasks to perform automated reconnaissance. Below is an overview of the purpose and usage of each tool and task in the project:

1. **Amass**: Used for subdomain enumeration. The `AmassScan` task runs the `amass` tool to discover subdomains of a target domain.
2. **Masscan**: Used for fast port scanning. The `MasscanScan` task runs the `masscan` tool to identify open ports on the target hosts.
3. **Nmap**: Used for detailed port scanning and service enumeration. The `ThreadedNmapScan` task runs the `nmap` tool to perform detailed scans on the identified open ports.
4. **Searchsploit**: Used for vulnerability scanning. The `SearchsploitScan` task runs the `searchsploit` tool to identify known vulnerabilities in the services running on the open ports.
5. **Gobuster**: Used for directory and file brute-forcing on web servers. The `GobusterScan` task runs the `gobuster` tool to identify hidden directories and files on the target web servers.
6. **Aquatone**: Used for taking screenshots of web pages. The `AquatoneScan` task runs the `aquatone` tool to capture screenshots of the target web pages.
7. **Waybackurls**: Used for fetching known URLs from the Wayback Machine. The `WaybackurlsScan` task runs the `waybackurls` tool to retrieve historical URLs for the target domains.
8. **Webanalyze**: Used for identifying web technologies. The `WebanalyzeScan` task runs the `webanalyze` tool to detect the technologies used by the target web servers.
9. **Subjack**: Used for subdomain takeover detection. The `SubjackScan` task runs the `subjack` tool to identify subdomains that are vulnerable to takeover.
10. **TKOSubs**: Used for subdomain takeover detection. The `TKOSubsScan` task runs the `tkosubs` tool to identify subdomains that are vulnerable to takeover.

Each task in the recon-pipeline project is defined as a `luigi.Task` or `luigi.ExternalTask` and can have dependencies on other tasks. The tasks are executed in a specific order based on their dependencies, allowing for the definition and execution of complex workflows.
