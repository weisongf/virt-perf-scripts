#!/usr/bin/env python
"""Run FIO Test.

# Interface between GenerateTestReport.py
# This script should do:
# 1. the fio outputs should be at least in json+ format
#    the "fio --group_reporting" must be used
# 2. save the fio outputs into *.fiolog
# 3. put all *.fiolog files into the spcified path
# 4. pass the additional information by "fio --description"
#    a) "driver" - frontend driver, such as SCSI or IDE
#    b) "format" - the disk format, such as raw or xfs
#    c) "round" - the round number, such as 1, 2, 3...
#    d) "backend" - the hardware which data image based on

History:
v0.1    2018-07-31  charles.shih  Refactory based on StoragePerformanceTest.py
v0.2    2018-08-03  charles.shih  Implement Class RunFioTest.
v0.3    2018-08-07  charles.shih  Finish the logic of log handling.
v0.4    2018-08-07  charles.shih  Add logic to handling CLI.
v1.0    2018-08-08  charles.shih  Init version.
"""

import os
import time
import itertools
import yaml
import click


class FioTestRunner:
    """FIO Test Runner.

    This class used to run the fio test cases. As basic functions:
    1. It loads all the needed parameters from dict named 'params';
    2. It splits the test suites into sub-cases and run them one by one;
    3. It generates the fio test report as log files ending with '.fiolog';

    """

    def __init__(self, params={}):
        """Initialize this Class.

        This function parse and check the parameters for running the fio tests.

        Args:
            params: dict
                backend: str
                    The backend device where vdisk image is based on.
                    Example: "HDD", "SSD", "NVME"...
                driver: str
                    The driver to power the vdisk..
                    Example: "SCSI", "IDE"...
                fs: str
                    The filesystem of the disk to be tested, "RAW" for no fs.
                    Example: "RAW", "XFS", "EXT4"...
                rounds: int
                    How many rounds the fio test will be repeated.
                filename: str
                    [FIO] The disk or specified file(s) to be tested by fio.
                runtime: str
                    [FIO] Terminate a job after the specified period of time.
                direct: str
                    [FIO] Direct access to the disk.
                    Example: '0' (using cache), '1' (direct access).
                numjobs: int
                    [FIO] Create the specified number of clones of the job.
                rw_list: list
                    [FIO] Type of I/O pattern.
                    Example: 'write, read, randrw'...
                bs_list: list
                    [FIO] The block size in bytes used for I/O units.
                    Example: '4k, 16k, 64k, 256k, 1m'...
                iodepth_list: list
                    [FIO] # of I/O units to keep in flight against the file.
                    Example: '1, 8, 64'...
                log_path: str
                    Where the *.fiolog files will be saved to.
        Returns:
            None

        """
        if 'backend' not in params:
            print 'ERROR: Missing required params: params[backend]'
            exit(1)
        elif not isinstance(params['backend'], (unicode, str)):
            print 'ERROR: params[backend] must be string.'
            exit(1)
        else:
            self.backend = params['backend']

        if 'driver' not in params:
            print 'ERROR: Missing required params: params[driver]'
            exit(1)
        elif not isinstance(params['driver'], (unicode, str)):
            print 'ERROR: params[driver] must be string.'
            exit(1)
        else:
            self.driver = params['driver']

        if 'fs' not in params:
            print 'ERROR: Missing required params: params[fs]'
            exit(1)
        elif not isinstance(params['fs'], (unicode, str)):
            print 'ERROR: params[fs] must be string.'
            exit(1)
        else:
            self.fs = params['fs']

        if 'rounds' not in params:
            print 'ERROR: Missing required params: params[rounds]'
            exit(1)
        elif not isinstance(params['rounds'], int) or params['rounds'] < 1:
            print 'ERROR: params[rounds] must be an integer >= 1.'
            exit(1)
        else:
            self.rounds = params['rounds']

        if 'filename' not in params:
            print 'ERROR: Missing required params: params[filename]'
            exit(1)
        elif not isinstance(params['filename'], (unicode, str)):
            print 'ERROR: params[filename] must be string.'
            exit(1)
        else:
            self.filename = params['filename']

        if 'runtime' not in params:
            print 'ERROR: Missing required params: params[runtime]'
            exit(1)
        elif not isinstance(params['runtime'], (unicode, str)):
            print 'ERROR: params[runtime] must be string.'
            exit(1)
        else:
            self.runtime = params['runtime']

        if 'direct' not in params:
            print 'ERROR: Missing required params: params[direct]'
            exit(1)
        elif not params['direct'] in (0, 1):
            print 'ERROR: params[direct] must be integer 0 or 1.'
            exit(1)
        else:
            self.direct = params['direct']

        if 'numjobs' not in params:
            print 'ERROR: Missing required params: params[numjobs]'
            exit(1)
        elif not isinstance(params['numjobs'], int):
            print 'ERROR: params[numjobs] must be an integer.'
            exit(1)
        else:
            self.numjobs = params['numjobs']

        if 'rw_list' not in params:
            print 'ERROR: Missing required params: params[rw_list]'
            exit(1)
        elif not isinstance(params['rw_list'], (list, tuple)):
            print 'ERROR: params[rw_list] must be a list or tuple.'
            exit(1)
        else:
            self.rw_list = params['rw_list']

        if 'bs_list' not in params:
            print 'ERROR: Missing required params: params[bs_list]'
            exit(1)
        elif not isinstance(params['bs_list'], (list, tuple)):
            print 'ERROR: params[bs_list] must be a list or tuple.'
            exit(1)
        else:
            self.bs_list = params['bs_list']

        if 'iodepth_list' not in params:
            print 'ERROR: Missing required params: params[iodepth_list]'
            exit(1)
        elif not isinstance(params['iodepth_list'], (list, tuple)):
            print 'ERROR: params[iodepth_list] must be a list or tuple.'
            exit(1)
        else:
            self.iodepth_list = params['iodepth_list']

        if 'log_path' not in params:
            print 'ERROR: Missing required params: params[log_path]'
            exit(1)
        elif not isinstance(params['log_path'], (unicode, str)):
            print 'ERROR: params[log_path] must be string.'
            exit(1)
        else:
            self.log_path = params['log_path']

        return None

    def _split_fio_tests(self):
        """Split fio test parameters.

        This function splits the parameters for running the fio tests.

        It will do Cartesian product with the following itmes:
        - self.rounds
        - self.bs_list
        - self.iodepth_list
        - self.rw_list          (Most often changing)

        Args:
            None

        Returns:
            The iterator of fio test parameters in (round, bs, iodepth, rw).

        """
        return itertools.product(
            range(1, self.rounds + 1), self.bs_list, self.iodepth_list,
            self.rw_list)

    def run_tests(self):
        """Split and run all the sub-cases."""
        fio_params = self._split_fio_tests()
        for fio_param in fio_params:
            (rd, bs, iodepth, rw) = fio_param

            # Set log file
            output_path = os.path.expanduser(self.log_path)
            if not os.path.exists(output_path):
                os.makedirs(output_path)

            output_file = 'fio_%s_%s_%s_%s_%s_%s_%s_%s_%s.fiolog' % (
                self.backend, self.driver, self.fs, rw, bs, iodepth,
                self.numjobs, rd,
                time.strftime('%Y%m%d%H%M%S', time.localtime()))

            output = output_path + os.sep + output_file

            # Build fio command
            command = 'fio'
            command += ' --name=%s' % output_file
            command += ' --filename=%s' % self.filename
            command += ' --size=512M'
            command += ' --direct=%s' % self.direct
            command += ' --rw=%s' % rw
            command += ' --bs=%s' % bs
            command += ' --ioengine=libaio'
            command += ' --iodepth=%s' % iodepth
            command += ' --numjobs=%s' % self.numjobs
            command += ' --time_based'
            command += ' --runtime=%s' % self.runtime
            command += ' --group_reporting'
            command += ' --description="%s"' % {
                'backend': self.backend,
                'driver': self.driver,
                'format': self.fs,
                'round': rd
            }
            command += ' --output-format=normal,json+'
            command += ' --output=%s' % output

            # Parse options only, don't start any I/O
            # command += ' --parse-only'  # (comment this line for testing)

            # Execute fio test
            print '-' * 50
            print 'Current Time: %s' % time.strftime('%Y-%m-%d %H:%M:%S',
                                                     time.localtime())
            print 'Test Command: %s' % command
            print '-' * 50
            os.system(command)


def get_cli_params(backend, driver, fs, rounds, filename, runtime, direct,
                   numjobs, rw_list, bs_list, iodepth_list, log_path):
    """Get parameters from the CLI."""
    cli_params = {}

    if backend:
        cli_params['backend'] = backend
    if driver:
        cli_params['driver'] = driver
    if fs:
        cli_params['fs'] = fs
    if rounds:
        cli_params['rounds'] = int(rounds)
    if filename:
        cli_params['filename'] = filename
    if runtime:
        cli_params['runtime'] = runtime
    if direct:
        cli_params['direct'] = direct
    if numjobs:
        cli_params['numjobs'] = numjobs
    if rw_list:
        cli_params['rw_list'] = rw_list.split(',')
    if bs_list:
        cli_params['bs_list'] = bs_list.split(',')
    if iodepth_list:
        cli_params['iodepth_list'] = iodepth_list.split(',')
    if log_path:
        cli_params['log_path'] = log_path

    return cli_params


def get_yaml_params():
    """Get parameters from the yaml file."""
    yaml_params = {}

    try:
        with open('./virt_perf_scripts.yaml', 'r') as f:
            yaml_dict = yaml.load(f)
            yaml_params = yaml_dict['FioTestRunner']

    except Exception as err:
        print 'WARNING: Fail to get default value from virt_perf_scripts.yaml'
        print err

    return yaml_params


def run_fio_test(params={}):
    """Initialize and run the fio test."""
    print '=' * 50
    print 'Start Time: %s' % time.strftime('%Y-%m-%d %H:%M:%S',
                                           time.localtime())
    print '=' * 50

    fiorunner = FioTestRunner(params)
    fiorunner.run_tests()

    print '=' * 50
    print 'Finish Time: %s' % time.strftime('%Y-%m-%d %H:%M:%S',
                                            time.localtime())
    print '=' * 50


@click.command()
@click.option(
    '--backend', help='The backend device where vdisk image is based on.')
@click.option('--driver', help='The driver to power the vdisk..')
@click.option(
    '--fs', help='The filesystem of the disk to be tested, "RAW" for no fs.')
@click.option(
    '--rounds',
    type=click.IntRange(1, 1000),
    help='How many rounds the fio test will be repeated.')
@click.option(
    '--filename',
    help='[FIO] The disk or specified file(s) to be tested by fio.')
@click.option(
    '--runtime',
    help='[FIO] Terminate a job after the specified period of time.')
@click.option(
    '--direct',
    type=click.Choice(['0', '1']),
    help='[FIO] Direct access to the disk.')
@click.option(
    '--numjobs',
    type=click.IntRange(1, 65535),
    help='[FIO] Create the specified number of clones of the job.')
@click.option('--rw_list', help='[FIO] Type of I/O pattern.')
@click.option(
    '--bs_list', help='[FIO] The block size in bytes used for I/O units.')
@click.option(
    '--iodepth_list',
    help='[FIO] # of I/O units to keep in flight against the file.')
@click.option('--log_path', help='Where the *.fiolog files will be saved to.')
def cli(backend, driver, fs, rounds, filename, runtime, direct, numjobs,
        rw_list, bs_list, iodepth_list, log_path):
    """Command line interface.

    Take arguments from CLI, load default parameters from yaml file.
    Then initialize the fio test.

    """
    # Read user specified parameters from CLI
    cli_params = get_cli_params(backend, driver, fs, rounds, filename, runtime,
                                direct, numjobs, rw_list, bs_list,
                                iodepth_list, log_path)

    # Read user configuration from yaml file
    yaml_params = get_yaml_params()

    # Combine user input and config
    params = {}
    params.update(yaml_params)
    params.update(cli_params)

    # Run fio test
    run_fio_test(params)

    exit(0)


if __name__ == '__main__':
    cli()