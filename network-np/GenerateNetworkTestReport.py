#!/usr/bin/env python3
"""Generate netperf Test Report.

Deal with the test logs generated by virt_netperf_test.py

History:
v0.1    2020-05-20  charles.shih  Init version.
v0.2    2020-07-02  charles.shih  Basic function completed.
v0.3    2020-07-20  charles.shih  Adapt the script for virt_netperf_test.
v0.4    2020-07-21  charles.shih  Add KPI TransRate.
v0.5    2020-07-21  charles.shih  Modify KPI Throughput, MSize, RRSize.
v0.6    2020-07-21  charles.shih  Adjust MSize, RRSize, add KPI Latency.
"""

import json
import os
import click
import pandas as pd


class NetperfTestReporter():
    """Netperf Test Reporter.

    This class used to generate the Netperf test report. As basic functions:
    1. It loads the raw data from *.nplog.json log files;
    2. It analyse the raw data and extract performance KPIs from raw data;
    3. It generates the report DataFrame and dump to a CSV file;

    Attributes:
        raw_data_list: the list to store raw data.
        perf_kpi_list: the list to store performance KPI tuples.
        df_report: a DataFrame to store the test report.

    """

    # The list of raw data, the item is loaded from netperf log file.
    # Each item is a full data source (raw data) in Python dict format.
    raw_data_list = []

    # The list of performance KPIs, which are extracted from the raw data.
    # Each item represents a single netperf test results in Python dict format.
    perf_kpi_list = []

    # The DataFrame to store performance KPIs for reporting, which is powered
    # by Pandas.
    df_report = None

    def _byteify(self, inputs):
        """Convert unicode to utf-8 string.

        This function converts the unicode string to bytes.

        Args:
            inputs: the object which contain unicode.

        Returns:
            The byteify version of inputs.

        """
        if isinstance(inputs, dict):
            return {
                self._byteify(key): self._byteify(value)
                for key, value in inputs.items()
            }
        elif isinstance(inputs, list):
            return [self._byteify(element) for element in inputs]
        elif isinstance(inputs, str):
            return inputs.encode('utf-8')
        else:
            return inputs

    def _get_raw_data_from_netperf_log(self, data_file):
        """Get the raw data from a specified netperf log file.

        This function open a specified netperf log file and read the json
        block. Then converts it into Python dict format and returns it.

        Args:
            data_file: string, the path to the netperf log file.

        Returns:
            This function returns a tuple like (result, raw_data):
            result:
                0: Passed
                1: Failed
            raw_data:
                The raw data in Python dict format.

        Raises:
            1. Error while handling the new json file

        """
        # Parse required params
        if data_file == '':
            print('[ERROR] Missing required params: data_file')
            return (1, None)

        try:
            with open(data_file, 'r') as f:
                json_data = json.load(f)
                if '' == b'':
                    # Convert to byteify for Python 2
                    raw_data = self._byteify(json_data)
                else:
                    # Keep strings for Python 3
                    raw_data = json_data
        except Exception as err:
            print('[ERROR] Error while handling the new json file: %s' % err)
            return (1, None)

        return (0, raw_data)

    def load_raw_data_from_netperf_logs(self, params={}):
        """Load raw data from netperf log files.

        This function loads raw data from a sort of netperf log files and stores
        the raw data (in Python dict format) into self.raw_data_list.

        Args:
            params: dict
                result_path: string, the path where netperf log files located.

        Returns:
            0: Passed
            1: Failed

        Updates:
            self.raw_data_list: store all the raw data;

        """
        # Parse required params
        if 'result_path' not in params:
            print('[ERROR] Missing required params: params[result_path]')
            return 1

        # Load raw data from files
        for fname in os.listdir(params['result_path']):
            filename = params['result_path'] + os.sep + fname

            # Tarball support
            tmpfolder = '/tmp/netperf-report.tmp'
            if filename.endswith('.tar.gz') and os.path.isfile(filename):
                os.system('mkdir -p {0}'.format(tmpfolder))
                os.system('tar xf {1} -C {0}'.format(tmpfolder, filename))
                filename = tmpfolder + os.sep + fname.replace(
                    '.tar.gz', '.nplog.json')

            # Load raw data
            if filename.endswith('.nplog.json') and os.path.isfile(filename):
                (result,
                 raw_data) = self._get_raw_data_from_netperf_log(filename)
                if result == 0:
                    self.raw_data_list.append(raw_data)

            # Tarball support, cleanup
            os.system('[ -e {0} ] && rm -rf {0}'.format(tmpfolder))

        return 0

    def _get_kpis_from_raw_data(self, raw_data):
        """Get KPIs from a specified raw data.

        This function get the performance KPIs from a specified tuple of raw
        data. It converts the units and format the values so that people can
        read them easily.

        Args:
            raw_data: dict, the specified raw data.

        Returns:
            This function returns a tuple like (result, perf_kpi):
            result:
                0: Passed
                1: Failed
            perf_kpi:
                The performance KPIs in Python dict format.

        Raises:
            1. Error while extracting performance KPIs

        """
        # Parse required params
        if raw_data == '':
            print('[ERROR] Missing required params: raw_data')
            return (1, None)

        # Get the performance KPIs
        perf_kpi = {}

        metadata = raw_data['metadata']
        perf_kpi['driver'] = metadata['DRIVER']
        perf_kpi['round'] = metadata['ROUNDS']
        perf_kpi['test'] = metadata['NAME']

        series_meta = metadata['SERIES_META']
        for name in series_meta.keys():
            if name in ('TCP_STREAM', 'TCP_MAERTS', 'UDP_STREAM',
                        'UDP_MAERTS'):

                # Message / RR size
                perf_kpi['msize'] = metadata['M_SIZE']
                perf_kpi['rrsize'] = '0'

                # Bandwidth in "Mbits/s".
                unit = series_meta[name]['THROUGHPUT_UNITS']
                if unit != '10^6bits/s':
                    raise Exception('Bandwidth unit is not "10^6bits/s".')
                perf_kpi['throughput'] = series_meta[name]['THROUGHPUT']
                perf_kpi['transrate'] = 'NaN'

                # Latency in "ms"
                perf_kpi['latency'] = series_meta[name]['MEAN_LATENCY']

            elif name in ('TCP_RR', 'TCP_CRR', 'UDP_RR'):

                # Message / RR size
                perf_kpi['msize'] = '0'
                perf_kpi['rrsize'] = metadata['RR_SIZE']

                # Bandwidth in "Mbits/s".
                perf_kpi['throughput'] = 'NaN'
                perf_kpi['transrate'] = series_meta[name]['TRANSACTION_RATE']

                # Latency in "ms"
                perf_kpi['latency'] = series_meta[name]['MEAN_LATENCY']

        return (0, perf_kpi)

    def calculate_performance_kpis(self, params={}):
        """Calculate performance KPIs.

        This function calculates performance KPIs from self.raw_data_list and
        stores the performance KPI tuples into self.perf_kpi_list.

        As data source, the following attributes should be ready to use:
        1. self.raw_data_list: the list of raw data (Python dict format)

        Args:
            params: dict
                None

        Returns:
            0: Passed
            1: Failed

        Updates:
            self.perf_kpi_list: store the performance KPI tuples.

        """
        # Calculate performance KPIs
        for raw_data in self.raw_data_list:
            (result, perf_kpi) = self._get_kpis_from_raw_data(raw_data)
            if result == 0:
                self.perf_kpi_list.append(perf_kpi)
            else:
                return 1

        return 0

    def _create_report_dataframe(self):
        """Create report DataFrame.

        This function creates the report DataFrame by reading the performance
        KPIs list.

        As data source, the following attributes should be ready to use:
        1. self.perf_kpi_list: the list of performance KPIs.

        Updates:
            self.df_report: the report DataFrame.

        """
        # Create report DataFrame from self.perf_kpi_list
        self.df_report = pd.DataFrame(self.perf_kpi_list,
                                      columns=[
                                          'driver', 'test', 'msize', 'rrsize',
                                          'round', 'throughput', 'transrate',
                                          'latency'
                                      ])

        # Rename the columns of the report DataFrame
        self.df_report.rename(columns={
            'driver': 'Driver',
            'test': 'Test',
            'msize': 'MSize',
            'rrsize': 'RRSize',
            'round': 'Round',
            'throughput': 'Throughput(10^6bits/s)',
            'transrate': 'TransRate(per sec)',
            'latency': 'Latency(ms)'
        },
                              inplace=True)

        return None

    def _format_report_dataframe(self):
        """Format report DataFrame.

        This function sorts and formats the report DataFrame.

        As data source, the following attributes should be ready to use:
        1. self.df_report: the report DataFrame.

        Updates:
            self.df_report: the report DataFrame.

        """
        # Sort the report DataFrame and reset its index
        self.df_report = self.df_report.sort_values(
            by=['Driver', 'Test', 'MSize', 'RRSize', 'Round'])

        self.df_report = self.df_report.reset_index().drop(columns=['index'])

        # Format the KPI values
        self.df_report = self.df_report.round(4)

        return None

    def generate_report_dataframe(self):
        """Generate the report DataFrame.

        This function generates the report DataFrame by reading the
        performance KPIs list.

        As data source, the following attributes should be ready to use:
        1. self.perf_kpi_list: the list of performance KPIs.

        Updates:
            self.df_report: the report DataFrame.

        """
        # Create DataFrame
        self._create_report_dataframe()

        # Format DataFrame
        self._format_report_dataframe()

        return None

    def report_dataframe_to_csv(self, params={}):
        """Dump the report DataFrame to a csv file.

        As data source, the self.df_report should be ready to use.

        Args:
            params: dict
                report_csv: string, the csv file to dump report DataFrame to.

        Returns:
            0: Passed
            1: Failed

        Raises:
            1. Error while dumping to csv file

        """
        # Parse required params
        if 'report_csv' not in params:
            print('[ERROR] Missing required params: params[report_csv]')
            return 1

        # Write the report to the csv file
        try:
            print('[NOTE] Dumping data into csv file "%s"...' %
                  params['report_csv'])
            content = self.df_report.to_csv()
            with open(params['report_csv'], 'w') as f:
                f.write(content)
            print('[NOTE] Finished!')

        except Exception as err:
            print('[ERROR] Error while dumping to csv file: %s' % err)
            return 1

        return 0


def generate_netperf_test_report(result_path, report_csv):
    """Generate netperf test report."""
    netperfreporter = NetperfTestReporter()

    # Load raw data from *.netperf files
    return_value = netperfreporter.load_raw_data_from_netperf_logs(
        {'result_path': result_path})
    if return_value:
        exit(1)

    # Caclulate performance KPIs for each test
    return_value = netperfreporter.calculate_performance_kpis()
    if return_value:
        exit(1)

    # Convert the KPIs into Dataframe
    netperfreporter.generate_report_dataframe()

    # Dump the Dataframe as CSV file
    return_value = netperfreporter.report_dataframe_to_csv(
        {'report_csv': report_csv})
    if return_value:
        exit(1)

    exit(0)


@click.command()
@click.option('--result_path',
              type=click.Path(exists=True),
              help='Specify the path where *.netperf files are stored in.')
@click.option('--report_csv',
              type=click.Path(),
              help='Specify the name of CSV file for netperf test reports.')
def cli(result_path, report_csv):
    """Command Line Interface."""
    # Parse and check the parameters
    if not result_path:
        print('[ERROR] Missing parameter, use "--help" to check the usage.')
        exit(1)
    if not report_csv:
        print('[WARNING] No CSV file name (--report_csv) was specified. Will \
use "%s/netperf_report.csv" instead.' % result_path)
        report_csv = result_path + os.sep + 'netperf_report.csv'

    # Generate netperf test report
    generate_netperf_test_report(result_path, report_csv)


if __name__ == '__main__':
    cli()
