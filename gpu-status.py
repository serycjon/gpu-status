#!/usr/bin/python
import subprocess as sp
import xml.etree.ElementTree
import os
import pwd
import argparse
import psutil


def owner(pid):
    try:
        # the /proc/PID is owned by process creator
        proc_stat_file = os.stat("/proc/{}".format(pid))
        # get UID via stat call
        uid = proc_stat_file.st_uid
        # look up the username from uid
        username = pwd.getpwuid(uid)[0]
    except:
        username = 'unknown'
    return username


def get_status():
    status = {}

    smi_cmd = ['nvidia-smi', '-q', '-x']  # get XML output
    proc = sp.Popen(smi_cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    stdout, stderr = proc.communicate()

    gpu_info_cmd = ['nvidia-smi',
                    '--query-gpu=index,memory.total,memory.used,memory.free,utilization.gpu',
                    '--format=csv,noheader']

    proc = sp.Popen(gpu_info_cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    gpu_stdout, gpu_stderr = proc.communicate()
    gpu_infos = gpu_stdout.strip().split('\n')
    gpu_infos = map(lambda x: x.split(', '), gpu_infos)
    gpu_infos = [{'index': x[0],
                  'mem_total': x[1],
                  'mem_used': x[2],
                  'mem_free': x[3],
                  'gpu_util': x[4]}
                 for x in gpu_infos]

    e = xml.etree.ElementTree.fromstring(stdout)
    for id, gpu in enumerate(e.findall('gpu')):
        gpu_stat = {}

        index = int(gpu_infos[id]['index'])
        utilization = gpu.find('utilization')
        gpu_util = utilization.find('gpu_util').text
        mem_free = gpu_infos[id]['mem_free'].split()[0]
        mem_total = gpu_infos[id]['mem_total'].split()[0]

        gpu_stat['gpu_util'] = float(gpu_util.split()[0]) / 100
        gpu_stat['mem_free'] = int(mem_free)
        gpu_stat['mem_total'] = int(mem_total)

        gpu_procs = []
        procs = gpu.find('processes')
        for procinfo in procs.iter('process_info'):
            pid = int(procinfo.find('pid').text)
            mem = procinfo.find('used_memory').text
            mem_num = int(mem.split()[0])
            user = owner(pid)

            tmp = {'user': user,
                   'mem': mem_num}
            command = ""
            try:
                p = psutil.Process(pid)
                command = ' '.join(p.cmdline())
                tmp['command'] = command
            except:
                pass
            gpu_procs.append(tmp)
        gpu_stat['proc'] = gpu_procs
        status[index] = gpu_stat

    return status


def pretty_print(status, verbose=False):
    for id, stats in status.iteritems():
        mem_free = stats['mem_free']
        color_out = '\x1b[0m'
        color_in = color_out
        if mem_free > 10000:
            color_in = '\x1b[0;32m'
        elif mem_free > 5000:
            color_in = '\x1b[0;36m'

        header = 'gpu {}: {}%, freeMEM {}{}{}/{} MiB'.format(id,
                                                             int(100*stats['gpu_util']),
                                                             color_in,
                                                             stats['mem_free'],
                                                             color_out,
                                                             stats['mem_total'])
        print header
        print ('-'*(len(header) - len(color_in) - len(color_out)))
        for proc in stats['proc']:
            line = '{} - {} MiB'.format(proc['user'], proc['mem'])
            print(line)
            if verbose:
                print(proc['command'])
                print('')
        print('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', action='store_true', help='show commands')
    args = vars(parser.parse_args())

    verbose = args['v']

    pretty_print(get_status(), verbose)
