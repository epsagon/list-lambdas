"""
Enumerates Lambda functions from every region with interesting metadata
"""

from __future__ import print_function
from datetime import datetime
import argparse
import codecs
import boto3
from boto3.session import Session
from botocore.exceptions import ClientError
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
    'Last Modified',
    'Last Invocation',
    'Description',
]

SORT_KEYS = ['region', 'last-modified', 'last-invocation', 'runtime']


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
    elif args.profile:
        session = boto3.session.Session(profile_name=args.profile)
        boto_client = session.client(client_name, region_name=region)
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


def get_last_invocation(region, args, function_name):
    """
    Return last invocation timestamp (epoch) or -1 if not found.
    -1 can be returned if no log group exists for Lambda,
    or if there are no streams in the log.
    :param region: function region
    :param args: arguments
    :param function_name: function name
    :return: last invocation or -1
    """
    logs_client = init_boto_client('logs', region, args)
    last_invocation = -1

    try:
        logs = logs_client.describe_log_streams(
            logGroupName='/aws/lambda/{0}'.format(function_name),
            orderBy='LastEventTime',
            descending=True
        )
    except ClientError as _:
        return last_invocation

    log_streams_timestamp = [
        log.get('lastEventTimestamp', 0) for log in logs['logStreams']
    ]

    if log_streams_timestamp:
        last_invocation = max(log_streams_timestamp)

    return last_invocation


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
        last_invocation = 'N/A (no invocations?)'
        if lambda_data['last-invocation'] != -1:
            last_invocation = get_days_ago(
                datetime.fromtimestamp(lambda_data['last-invocation'] / 1000)
            )
        all_table_data.append([
            lambda_data['region'],
            str(function_data['FunctionName']),
            str(function_data['MemorySize']),
            '%.2f' % (function_data['CodeSize'] / BYTE_TO_MB),
            str(function_data['Timeout']),
            str(function_data['Runtime']) if 'Runtime' in function_data else '',
            get_days_ago(lambda_data['last-modified']),
            last_invocation,
            '"' + function_data['Description'] + '"'
        ])

    if args.should_print_all:
        min_table_data = all_table_data
    else:
        # Get only the region, function, last modified and last invocation
        min_table_data = [
            [
                lambda_data[0], lambda_data[1], lambda_data[5], lambda_data[-2], lambda_data[-1]
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
        next_marker = None
        response = lambda_client.list_functions()
        while next_marker != '':
            next_marker = ''
            functions = response['Functions']
            if not functions:
                continue

            for function_data in functions:
                # Extract last modified time
                last_modified = datetime.strptime(
                    function_data['LastModified'].split('.')[0],
                    DATETIME_FORMAT
                )

                # Extract last invocation time from logs
                last_invocation = get_last_invocation(
                    region,
                    args,
                    function_data['FunctionName']
                )

                if last_invocation != -1:
                    inactive_days = (
                        datetime.now() -
                        datetime.fromtimestamp(last_invocation / 1000)
                    ).days
                    if args.inactive_days_filter > inactive_days:
                        continue

#                print(function_data)
                lambdas_data.append({
                    'region': region,
                    'function-data': function_data,
                    'last-modified': last_modified,
                    'last-invocation': last_invocation,
                    'runtime': function_data['Runtime'] if 'Runtime' in function_data else ''
                })

            # Verify if there is next marker
            if 'NextMarker' in response:
                next_marker = response['NextMarker']
                response = lambda_client.list_functions(Marker=next_marker)

    # Sort data by the given key (default: by region)
    lambdas_data.sort(key=lambda x: x[args.sort_by])

    min_table_data, all_table_data = create_tables(lambdas_data, args)
    table = AsciiTable(min_table_data)
    print(table.table)

    if not args.csv:
        return

    with codecs.open(args.csv, 'w', encoding='utf-8') as output_file:
        for table_row in all_table_data:
            output_line = '{0}\n'.format(','.join(table_row))
            output_file.writelines(output_line)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=(
            'Enumerates Lambda functions from every region with '
            'interesting metadata.'
        )
    )

    parser.add_argument(
        '--all',
        dest='should_print_all',
        default=False,
        action='store_true',
        help=(
            'Print all the information to the screen '
            '(default: print summarized information).'
        )
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
        help=(
            'AWS access key id. Must provide AWS secret access key as well '
            '(default: from local configuration).'
        ),
        metavar='token-key-id'
    )
    parser.add_argument(
        '--token-secret',
        type=str,
        help=(
            'AWS secret access key. Must provide AWS access key id '
            'as well (default: from local configuration.'
        ),
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
        help=(
            'Column name to sort by. Options: region, '
            'last-modified, last-invocation, '
            'runtime (default: region).'
        ),
        default='region',
        metavar='sort_by'
    )
    parser.add_argument(
        '--profile',
        type=str,
        help=(
            'AWS profile. Optional '
            '(default: "default" from local configuration).'
        ),
        metavar='profile'
    )

    arguments = parser.parse_args()
    if arguments.sort_by not in SORT_KEYS:
        print('ERROR: Illegal column name: {0}.'.format(arguments.sort_by))
        exit(1)

    print_lambda_list(arguments)
