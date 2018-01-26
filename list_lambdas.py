"""
Enumerates Lambda functions from every region with interesting metadata
"""

from datetime import datetime
import argparse
import boto3
from boto3.session import Session
from terminaltables import AsciiTable
import progressbar

DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
BYTE_TO_MB = 1024.0 * 1024.0

ALL_TABLE_HEADERS = [
    'Region',
    'Function',
    'Memory (MB)',
    'Code Size (MB)',
    'Timeout (seconds)',
    'Runtime',
    'Description',
    'Last Modified',
    'Last Invocation',
]

SORT_KEYS = ['region', 'last-modified', 'last-invocation']


def list_available_lambda_regions():
    """
    Enumerates list of all Lambda regions
    :return: list of regions
    """
    session = Session()
    return session.get_available_regions('lambda')


def init_boto_client(client_name, region, args):
    """
    Initiates boto's client object
    :param client_name: client name
    :param region: region name
    :param args: arguments
    :return: Client
    """
    if args.token_key_id and args.token_secret:
        boto_client = boto3.client(
            client_name,
            aws_access_key_id=args.token_key_id,
            aws_secret_access_key=args.token_secret,
            region_name=region
        )
    else:
        boto_client = boto3.client(client_name, region_name=region)

    return boto_client


def get_days_ago(datetime_obj):
    """
    Converts a datetime object to "time ago" string
    :param datetime_obj: Datetime
    :return: "time ago" string
    """
    days_ago = (datetime.now() - datetime_obj).days
    datetime_str = 'Today'
    if days_ago == 1:
        datetime_str = 'Yesterday'
    elif days_ago > 1:
        datetime_str = '{0} days ago'.format(days_ago)

    return datetime_str


def create_tables(lambdas_data, args):
    """
    Create the output tables
    :param lambdas_data: a list of the Lambda functions and their data
    :param args: argparse arguments
    :return: textual table-format information about the Lambdas
    """
    all_table_data = [ALL_TABLE_HEADERS]
    for lambda_data in lambdas_data:
        function_data = lambda_data['function-data']
        all_table_data.append([
            lambda_data['region'],
            str(function_data['FunctionName']),
            str(function_data['MemorySize']),
            '%.2f' % (function_data['CodeSize'] / BYTE_TO_MB),
            str(function_data['Timeout']),
            str(function_data['Runtime']),
            str(function_data['Description']),
            get_days_ago(lambda_data['last-modified']),
            get_days_ago(datetime.fromtimestamp(lambda_data['last-invocation'] / 1000))
        ])

    if args.should_print_all:
        min_table_data = all_table_data
    else:
        # Get only the region, function, last modified and last invocation
        min_table_data = [
            [
                lambda_data[0], lambda_data[1], lambda_data[-2], lambda_data[-1]
            ]
            for lambda_data in all_table_data
        ]

    return min_table_data, all_table_data


def print_lambda_list(args):
    """
    Main function
    :return: None
    """
    regions = list_available_lambda_regions()
    progress_bar = progressbar.ProgressBar(max_value=len(regions))
    lambdas_data = []
    for region in progress_bar(regions):
        lambda_client = init_boto_client('lambda', region, args)
        logs_client = init_boto_client('logs', region, args)
        functions = lambda_client.list_functions()['Functions']
        if not functions:
            continue

        for function_data in functions:
            # Extract last modified time
            last_modified = datetime.strptime(
                function_data['LastModified'].split('.')[0],
                DATETIME_FORMAT
            )

            # Extract last invocation time from logs
            logs = logs_client.describe_log_streams(
                logGroupName='/aws/lambda/{0}'.format(function_data['FunctionName']),
                orderBy='LastEventTime',
                descending=True
            )

            last_invocation = max(
                [log.get('lastEventTimestamp', 0) for log in logs['logStreams']]
            )

            inactive_days = (datetime.now() - datetime.fromtimestamp(last_invocation / 1000)).days
            if args.inactive_days_filter > inactive_days:
                continue

            lambdas_data.append({
                'region': region,
                'function-data': function_data,
                'last-modified': last_modified,
                'last-invocation': last_invocation
            })

    # Sort data by the given key (default: by region)
    lambdas_data.sort(key=lambda x: x[args.sort_by])

    min_table_data, all_table_data = create_tables(lambdas_data, args)
    table = AsciiTable(min_table_data)
    print table.table

    if not args.csv:
        return

    with open(args.csv, 'wt') as output_file:
        for table_row in all_table_data:
            output_file.writelines('{0}\n'.format(','.join(table_row)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Enumerates Lambda functions from every region with interesting metadata.'
    )

    parser.add_argument(
        '--all',
        dest='should_print_all',
        default=False,
        action='store_true',
        help='Print all the information to the screen (default: print summarized information).'
    )
    parser.add_argument(
        '--csv',
        type=str,
        help='CSV filename to output full table data.',
        metavar='output_filename'
    )
    parser.add_argument(
        '--token-key-id',
        type=str,
        help='AWS access key id. Must provide AWS secret access key as well (default: from local configuration).',
        metavar='token-key-id'
    )
    parser.add_argument(
        '--token-secret',
        type=str,
        help='AWS secret access key. Must provide AWS access key id as well (default: from local configuration.',
        metavar='token-secret'
    )
    parser.add_argument(
        '--inactive-days-filter',
        type=int,
        help='Filter only Lambda functions with minimum days of inactivity.',
        default=0,
        metavar='minimum-inactive-days'
    )
    parser.add_argument(
        '--sort-by',
        type=str,
        help='Column name to sort by. Options: region, last-modified, last-invocation (default: region).',
        default='region',
        metavar='sort_by'
    )

    args = parser.parse_args()
    if args.sort_by not in SORT_KEYS:
        print 'ERROR: Illegal column name: {0}.'.format(args.sort_by)
        exit(1)

    print_lambda_list(args)
