# Harbor Master

![](https://i.imgur.com/Q44BIZN.jpeg)

Harbor Master is a simple script to help manage Docker remote socket forwarding.

Specifically, this script uses SSH forwarding to forward the Docker socket of a remote machine to your local environment. This is quite useful when running heavy Dockerized applications, which can be run on some remote/cloud server, while being treated as a local container.

The benefit Harbor Master provides is that not only does it maintain the SSH tunnel for the remote socket, but it _also port forwards exposed container ports_. This is a severe
oversight in the current Docker implementation, and Harbor Master just makes your life that much easier :^).

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
./harbormaster.py dubey 192.168.1.111
```

This would connect to a machine on the IP `192.168.1.111` as user `dubey`, establishing a Docker socket tunnel on port 2377. Once this command is run, you can let the Harbor Master manage all the SSH tunnels necessary as containers go up and down.

### Important Notes

As of `v0.1`, Harbor Master assumes that you are using `zsh` and will modify your `~/.zshrc` file by appending a `export` statement that lets any new shell sessions use the forwarded Docker socket. Harbor Master does cleanup on shutdown: all SSH tunnels that are open, and any changes to the `.zshrc` file.
