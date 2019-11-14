#! /usr/bin/python3

import sys
import os

import docker
import argparse
import logging

import subprocess
import time


dockerTunnel = None

def createTunnel(port, user, host):
    logging.info(f'Creating tunnel for port {port} to {user}@{host}')
    p = subprocess.Popen([
            'ssh', '-nNT',
            '-L', f'{port}:localhost:{port}',
            f'{user}@{host}'
    ])
    return p


def main(args, spath):
    global dockerTunnel

    dockerTunnel = subprocess.Popen([
            'ssh', '-nNT',
            '-L', f'localhost:{args.p}:/var/run/docker.sock',
            f'{args.user}@{args.host}'
    ])
    logging.info(f'Docker socket forwarding started to {args.user}@{args.host} on local port {args.p}')

    # Get list of running containers
    logging.debug('Waiting for SSH to stabilize')
    time.sleep(5)
    dClient = docker.DockerClient(base_url=f'tcp://localhost:{args.p}')
    logging.info(f'Remote docker engine connection established')
    cList = dClient.containers.list()
    logging.debug(f'Found {len(cList)} running containers on connect')

    dRunning = {}
    """
    >>> x.attrs['NetworkSettings']['Ports']
    {'3000/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '3000'}]}
    """
    while True:
        cList = dClient.containers.list()
        tRunning = {}
        for c in cList:
            if c.id not in dRunning:
                logging.info(f'Found new container with ID {c.short_id} and name {c.name}')
                cPortsRaw = c.attrs['NetworkSettings']['Ports']
                for k,v in cPortsRaw.items():
                    if v:
                        for p in v:
                            port = p['HostPort']
                            proc = createTunnel(port, args.user, args.host)
                            dRunning[c.id] = proc
                            tRunning[c.id] = proc
            else:
                tRunning[c.id] = "still running"
        dead = {k: dRunning[k] for k in dRunning if k not in tRunning}
        for k in dead:
            logging.info(f'Closing tunnel {k}')
            dRunning[k].terminate()
            del dRunning[k]
        time.sleep(1)


def configfile(spath, port):
    hmsShellPrepend = [
        '#<<<$< DO NOT REMOVE OR MODIFY NEXT 2 LINES, USED BY HARBOR MASTER >$>>>\n',
        f'export DOCKER_HOST=localhost:{port}\n',
        '#<<<$< END HARBOR MASTER >$>>>\n'
    ]
    logging.debug(f'Opening shell config at {spath}')
    with open(spath, 'r') as f:
        dat = f.readlines()

    dat.extend(hmsShellPrepend)

    logging.debug(f'Writing harbormaster shell config at {spath}')
    with open(spath, 'w') as f:
        for item in dat:
            f.write('%s' %  item)


    logging.info(f'Added HM params on port {port} to shell config, please start a new shell to begin using forwarded docker')


def cleanfile(spath, port):
    hmsShellPrepend = [
        '#<<<$< DO NOT REMOVE OR MODIFY NEXT 2 LINES, USED BY HARBOR MASTER >$>>>\n',
        f'export DOCKER_HOST=localhost:{port}\n',
        '#<<<$< END HARBOR MASTER >$>>>\n'
    ]
    with open(spath, 'r') as f:
        dat = f.readlines()

    dat = [x for x in dat if x not in hmsShellPrepend]

    with open(spath, 'w') as f:
        for item in dat:
            f.write('%s' %  item)
    logging.info('Removed HM params from shell config')


def cleanup(spath, port):
    global dockerTunnel

    cleanfile(spath, port)

    logging.warning(f'Closing remote docker socket connection')
    dockerTunnel.terminate()

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='Automatically port forward the docker socket and container')

        parser.add_argument('user', type=str, help='User to SSH as')
        parser.add_argument('host', type=str, help='Host to SSH to')
        parser.add_argument('-p', type=int, help='Local port for forwarded socket, default 2377', default=2377)
        parser.add_argument('-v', action='store_true', help='Verbose output', default=False)

        a = parser.parse_args()
        if a.v:
            logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG)
            logging.debug('Debug logging enabled')
        else:
            logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

        s = os.path.abspath(os.path.expanduser('~/.zshrc'))

        configfile(s, a.p)

        main(a, s)
    except KeyboardInterrupt:
        logging.warning('Got CTRL-C, cleaning up (CTRL-C again to force)')
        cleanup(s, a.p)

