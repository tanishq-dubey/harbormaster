#! /usr/bin/env python3

import sys
import os
import logging
import subprocess
import time
import argparse

import docker


dockerSocketPath = '/var/run/docker.sock'
dockerTunnel = None
dRunning = {}

def createTunnel(port, user, host):
    logging.info(f'Creating tunnel for port {port} to {user}@{host}')
    p = subprocess.Popen([
            'ssh', '-nNT',
            '-L', f'0.0.0.0:{port}:localhost:{port}',
            f'{user}@{host}'
    ])
    return p


def main(args, spath):
    global dockerTunnel
    global dRunning

    if args.l > 0:
        # Not using createTunnel() here because this one off tunnel has slightly different syntax
        dockerTunnel = subprocess.Popen([
                'ssh', '-nNT',
                '-L', f'localhost:{args.p}:localhost:{args.l}',
                f'{args.user}@{args.host}'
        ])
    else:
        # Not using createTunnel() here because this one off tunnel has slightly different syntax
        dockerTunnel = subprocess.Popen([
                'ssh', '-nNT',
                '-L', f'localhost:{args.p}:{dockerSocketPath}',
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
                        if c.id in dRunning:
                            dRunning[c.id].append(proc)
                        else:
                            dRunning[c.id] = [proc]

    # Main Loop
    for event in dClient.events(decode=True):
        try:
            if event['Type'] == 'container' and event['status'] == 'start':
                c = dClient.containers.get(event['id'])
                logging.info(f'Got container start event for {c.name} ({c.short_id})')
                cPortsRaw = c.attrs['NetworkSettings']['Ports']
                if cPortsRaw is None:
                    logging.info(f'Container {c.name} was removed too quickly!')
                    continue
                for _,v in cPortsRaw.items():
                    if v:
                        for p in v:
                            port = p['HostPort']
                            proc = createTunnel(port, args.user, args.host)
                            if c.id in dRunning:
                                dRunning[c.id].append(proc)
                            else:
                                dRunning[c.id] = [proc]
            if event['Type'] == 'container' and event['status'] == 'die':
                c = dClient.containers.get(event['id'])
                logging.info(f'Got container die event for {c.name} ({c.short_id})')
                if c.id in dRunning:
                    logging.info(f'Closing tunnel(s) {event["id"]}')
                    for p in dRunning[event['id']]:
                        p.terminate()
                    del dRunning[event['id']]
                else:
                    logging.info(f'Harbormaster is no longer managing {c.name} ({event["id"]})')
        except docker.errors.NotFound as e:
            logging.info(e)
            continue

def configfile(spath, port):
    hmsShellPrepend = [
        '#<<<$< DO NOT REMOVE OR MODIFY NEXT 2 LINES, USED BY HARBOR MASTER >$>>>\n',
        f'export DOCKER_HOST=localhost:{port}\n',
        '#<<<$< END HARBOR MASTER >$>>>\n'
    ]
    logging.debug(f'Opening shell config at {spath}')
    try:
        with open(spath, 'r') as f:
            dat = f.readlines()
    except Exception as e:
        logging.error(f'There was an error opeing your .zshenv file: {e}')
        sys.exit(-1)

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
        logging.info(f'Closing tunnel(s) for {k}')
        for p in v:
            p.terminate()


    logging.warning(f'Closing remote docker socket connection')
    dockerTunnel.terminate()

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='Automatically port forward the docker socket and container')

        parser.add_argument('user', type=str, help='User to SSH as')
        parser.add_argument('host', type=str, help='Host to SSH to')
        parser.add_argument('-p', type=int, help='Local port for forwarded socket, default 2377', default=2377)
        parser.add_argument('-v', action='store_true', help='Verbose output', default=False)
        parser.add_argument('-l', type=int, help='Legacy TCP port to use instead of socket for Docker API', default=0)

        a = parser.parse_args()
        if a.v:
            logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG)
            logging.debug('Debug logging enabled')
        else:
            logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
        if a.l > 0:
            logging.info(f'Connecting to remote port {a.l} for Docker API')
        else:
            logging.info(f'Connecting to remote socket {dockerSocketPath}')

        s = os.path.abspath(os.path.expanduser('~/.zshenv'))

        configfile(s, a.p)

        main(a, s)
    except KeyboardInterrupt:
        logging.info('Got CTRL-C, cleaning up (CTRL-C again to force)')
    except Exception as e:
        logging.error(f'There was an error: {e}')
    finally:
        cleanup(s, a.p)

