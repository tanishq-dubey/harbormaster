#! /usr/bin/python3

import sys
import os

import docker
import argparse
import logging

import subprocess
import time


dockerTunnel = None
dRunning = {}

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
    global dRunning

    # Not using createTunnel() here because this one off tunnel has slightly different syntax
    dockerTunnel = subprocess.Popen([
            'ssh', '-nNT',
            '-L', f'localhost:{args.p}:/var/run/docker.sock',
            f'{args.user}@{args.host}'
    ])
    logging.info(f'Docker socket forwarding started to {args.user}@{args.host} on local port {args.p}')

    logging.debug('Waiting for SSH to stabilize')
    connected = False
    while not connected:
        try:
            dClient = docker.DockerClient(base_url=f'tcp://localhost:{args.p}')
            dClient.ping()
            connected = True
        except:
            logging.info(f'Waiting for tunnel to come up...')
            time.sleep(1)

    logging.info(f'Remote docker engine connection established')

    # Get list of running containers
    cList = dClient.containers.list()
    logging.debug(f'Found {len(cList)} running containers on connect')
    for c in cList:
        if c.id not in dRunning:
            logging.info(f'Found existing container with ID {c.short_id} and name {c.name}')
            cPortsRaw = c.attrs['NetworkSettings']['Ports']
            for _,v in cPortsRaw.items():
                if v:
                    for p in v:
                        port = p['HostPort']
                        proc = createTunnel(port, args.user, args.host)
                        dRunning[c.id] = proc

    # Main Loop
    for event in dClient.events(decode=True):
        if event['Type'] == 'container' and event['status'] == 'start':
            c = dClient.containers.get(event['id'])
            logging.info(f'Got container start event for {c.name} ({c.short_id})')
            cPortsRaw = c.attrs['NetworkSettings']['Ports']
            for _,v in cPortsRaw.items():
                if v:
                    for p in v:
                        port = p['HostPort']
                        proc = createTunnel(port, args.user, args.host)
                        dRunning[c.id] = proc
        if event['Type'] == 'container' and event['status'] == 'die':
            c = dClient.containers.get(event['id'])
            logging.info(f'Got container die event for {c.name} ({c.short_id})')
            logging.info(f'Closing tunnel {event["id"]}')
            dRunning[event['id']].terminate()
            del dRunning[event['id']]

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
    global dRunning

    cleanfile(spath, port)

    for k, v in dRunning.items():
        logging.info(f'Closing tunnel {k}')
        v.terminate()


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

        s = os.path.abspath(os.path.expanduser('~/.zshenv'))

        configfile(s, a.p)

        main(a, s)
    except KeyboardInterrupt:
        logging.warning('Got CTRL-C, cleaning up (CTRL-C again to force)')
        cleanup(s, a.p)
    except Exception:
        cleanup(s, a.p)

