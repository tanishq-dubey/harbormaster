# Harbor Master

![](https://i.imgur.com/Q44BIZN.jpeg)

Harbor Master is a simple script to help manage Docker remote socket forwarding.

Specifically, this script uses SSH forwarding to forward the Docker socket of a remote machine to your local environment. This is quite useful when running heavy Dockerized applications, which can be run on some remote/cloud server, while being treated as a local container.

The benefit Harbor Master provides is that not only does it maintain the SSH tunnel for the remote socket, but it _also port forwards exposed container ports_. This is a severe
oversight in the current Docker implementation, and Harbor Master just makes your life that much easier :^).

## Pre-Installation

Harbor Master requires Python3

Before you can use Harbor Master, you must have a trusted host that is already running docker. In addition you _must_ be using passwordless SSH to connect to this host and have
already done the key transfer. Harbor Master does not, and (probably) will not, manage/accept passwords for SSH connections. These are insecure and add unnecessary complexity. In
addition, please read the SSH Configuration notes below to ensure your remote host has the proper configuration.

## Installation

Harbor Master is available on PiPY and can be installed via a `pip install harbormaster`, or `pip3 install harbormaster` if you have multiple python versions.

Alternatively, you may clone this repository, install the docker python package as specified in the `requirements.txt`, and then copy `harbormaster.py` into your path.

## Usage

```
usage: harbormaster.py [-h] [-p P] [-v] user host

Automatically port forward the docker socket and container

positional arguments:
  user        User to SSH as
  host        Host to SSH to

optional arguments:
  -h, --help  show this help message and exit
  -p P        Local port for forwarded socket, default 2377
  -v          Verbose output
```

For example:

```
harbormaster.py dubey 192.168.1.111
```

This would connect to a machine on the IP `192.168.1.111` as user `dubey`, establishing a Docker socket tunnel on port 2377. Once this command is run, you can let the Harbor Master manage all the SSH tunnels necessary as containers go up and down.

### Important Notes

#### SSH Configuration

Most \*Nix distros come with sane defaults for the number of SSH connections allowed to a host, usually 10 concurrent connections. If you plan to have more than 10 ports forwarded,
then you must change the `sshd` config located at `/etc/ssh/sshd_config` and change the parameters:

```
MaxSessions 100
MaxStartups 100
```

In the above example, the host will accept 100 concurrent connections, allowing you to port forward 100 ports.

In addition it is highly recommended to disallow password SSH login, and only use SSH key files.

### Version Notes

As of `v0.1`, Harbor Master assumes that you are using `zsh` and will modify your `~/.zshrc` file by appending a `export` statement that lets any new shell sessions use the forwarded Docker socket. Harbor Master does cleanup on shutdown: all SSH tunnels that are open, and any changes to the `.zshrc` file.
