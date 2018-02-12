"""
Script to generate most optimal high load configuration for PostgreSQL.
Supported versions: 9.1
Version: 1.0b
"""

# Standard imports
from re import sub
from math import ceil
from argparse import ArgumentParser


PARSER = ArgumentParser()
PARSER.add_argument(
    '-m',
    '--memory',
    type=str,
    help=(
        'Operating memory. '
        'Supported units: kB, MB, GB, TB. '
        'If no unit was specified GB units will be used by default.'
    ),
    default='1GB'
)
PARSER.add_argument(
    '-p',
    '--cpus',
    type=int,
    help='CPU count.',
    default=2
)
PARSER.add_argument(
    '-c',
    '--connections',
    type=int,
    help='Maximum connections that database server aimed to support.',
    default=100
)
PARSER.add_argument(
    '-d',
    '--databases',
    type=int,
    help='Database count.',
    default='1'
)
PARSER.add_argument(
    '-v',
    '--version',
    type=str,
    help='PostgreSQL version to generate configuration for (default: 9.1).',
    default='9.1'
)

ARGUMENTS = PARSER.parse_args()

OPERATING_MEMORY = ARGUMENTS.memory
CPU_COUNT = ARGUMENTS.cpus
CONNECTION_COUNT = ARGUMENTS.connections
DATABASE_COUNT = ARGUMENTS.databases
POSTGRESQL_VERSION = ARGUMENTS.version

WAL_SEGMENT_SIZE = 16.0 * 1024


if POSTGRESQL_VERSION.strip() != '9.1':
    print(
        'At present this script supported only version 9.1, '
        'some values are known to be missing in 9.5+'
    )
    print('Exiting...')
    exit(1)


def normalize_value(value):
    """ Remove whitespace from value and cast it to lower case. """

    return(sub('[ \t]', '', value).lower())


def value_in_kilobytes(value):
    """ Check whether units were specified and convert value accordingly. """

    # NOTE: The multiplier for memory units is 1024, not 1000.
    # NOTE: valid memory units are:
    # * kB (kilobytes)
    # * MB (megabytes)
    # * GB (gigabytes)
    # * TB (terabytes)

    if value.endswith('kb'):
        value = float(value[:-2])
    elif value.endswith('mb'):
        value = float(value[:-2]) * 1024
    elif value.endswith('gb'):
        value = float(value[:-2]) * 1024 * 1024
    elif value.endswith('tb'):
        value = float(value[:-2]) * 1024 * 1024 * 1024
    else:
        # By default we assume value is in Gigabytes
        value = float(value) * 1024 * 1024

    return value


def normalize_memory_units(value, floor_to_mb=False):
    """
    Form string representation of current memory value using suitable units.
    It is possible to round value to megebyte based units.
    """

    # NOTE: The multiplier for memory units is 1024, not 1000.
    # NOTE: valid memory units are:
    # * kB (kilobytes)
    # * MB (megabytes)
    # * GB (gigabytes)
    # * TB (terabytes)

    units = 'kB'

    value = float(value)

    if not value % 1024:
        value = value / 1024
        units = 'MB'

        if not value % 1024:
            value = value / 1024
            units = 'GB'

            if not value % 1024:
                value = value / 1024
                units = 'TB'

    elif floor_to_mb:
        value = value // 1024 * 1024 / 1024
        units = 'MB'

    return ''.join((str(int(round(value))), units))


def output_description(  # IGNORE:too-many-arguments
    description='???',
    default='???',
    limitations='N/A',
    multipliers='N/A',
    recommended='???',
    reference='/'
):
    """
    Prints detailed information for each configuration value being changed.
    """

    print(
        (
            '# Description: %s\n'
            '# Default:     %s\n'
            '# Limitations: %s\n'
            '# Multipliers: %s\n'
            '# Recommended: %s\n'
            '# Reference:   https://www.postgresql.org/docs%s'
        ) % (
            description,
            default,
            limitations,
            multipliers,
            recommended,
            reference
        )
    )


OPERATING_MEMORY = value_in_kilobytes(normalize_value(OPERATING_MEMORY))

output_description(
    description='Memory for interprocess communication and caching.',
    default='32MB',
    limitations='At least 128kB',
    recommended='25% of RAM',
    reference='/9.1/static/runtime-config-resource.html#GUC-SHARED-BUFFERS'
)
SHARED_BUFFERS = OPERATING_MEMORY / 4
print(
    'shared_buffers = %s\n' % normalize_memory_units(
        SHARED_BUFFERS, floor_to_mb=True
    )
)

output_description(
    description='Memory for internal sort and hash operations.',
    default='1MB',
    multipliers='Parallel running operations',
    recommended='RAM / connections',
    reference='/9.1/static/runtime-config-resource.html#GUC-WORK-MEM'
)
print(
    'work_mem = %s\n' % normalize_memory_units(
        (
            OPERATING_MEMORY - SHARED_BUFFERS - (OPERATING_MEMORY / 100 * 5)
        ) / CONNECTION_COUNT,
        floor_to_mb=True
    )
)

output_description(
    description='Memory for WAL data that has not yet been written to disk.',
    default=(
        '1 equals to 3%% of shared_buffers, but not more than %s' % (
            normalize_memory_units(WAL_SEGMENT_SIZE)
        )
    ),
    limitations='At least 64kB',
    recommended=(
        '3%% of shared_buffers, multiple of %s' % (
            normalize_memory_units(WAL_SEGMENT_SIZE)
        )
    ),
    reference='/9.1/static/runtime-config-wal.html#GUC-WAL-BUFFERS'
)
print(
    'wal_buffers = %s\n' % normalize_memory_units(
        max(
            (SHARED_BUFFERS / 100) * 3 // WAL_SEGMENT_SIZE * WAL_SEGMENT_SIZE,
            WAL_SEGMENT_SIZE
        )
    )
)

# NOTE: not present in 9.5
output_description(
    description='Maximum number of log file segments between WAL checkpoints.',
    default='3',
    limitations='Higher values minimize IO but slow down crash recovery',
    recommended='120',
    reference='/9.1/static/runtime-config-wal.html#GUC-CHECKPOINT-SEGMENTS'
)
print('checkpoint_segments = 120\n')

output_description(
    description='Maximum time between automatic WAL checkpoints',
    default='5min',
    limitations='Range between 30 seconds and one hour',
    recommended='1h',
    reference='/9.1/static/runtime-config-wal.html#GUC-CHECKPOINT-TIMEOUT'
)
print('checkpoint_timeout = 1h\n')

output_description(
    description='Maximum number of autovacuum workers running simultaneously.',
    default='3',
    recommended='Amount of CPUs',
    reference=(
        '/9.1/static/runtime-config-autovacuum.html#GUC-AUTOVACUUM-MAX-WORKERS'
    )
)
AUTOVACUUM_WORKERS = CPU_COUNT
print('autovacuum_max_workers = %s\n' % AUTOVACUUM_WORKERS)

output_description(
    description=(
        'Memory to be used by maintenance operations (VACUUM, REINDEX, etc)'
    ),
    default='16MB',
    multipliers='Running autovacuum workers or any maintenance operations',
    recommended='5% of RAM distributed between autovacuum workers',
    reference=(
        '/9.1/static/runtime-config-resource.html#GUC-MAINTENANCE-WORK-MEM'
    )
)
print(
    'maintenance_work_mem = %s\n' % normalize_memory_units(
        OPERATING_MEMORY / 100 * 5 / AUTOVACUUM_WORKERS, floor_to_mb=True
    )
)

output_description(
    description='Planner\'s assumption about the size of the disk cache.',
    default='128MB',
    limitations='Less than [free + cached] values from `free` utility.',
    recommended='70% of RAM',
    reference='/9.1/static/runtime-config-query.html#GUC-EFFECTIVE-CACHE-SIZE'
)
print(
    'effective_cache_size = %s\n' % normalize_memory_units(
        OPERATING_MEMORY / 100 * 70, floor_to_mb=True
    )
)

output_description(
    description='Minimum delay between autovacuum runs on any given database.',
    default='1min',
    recommended='2 minutes per 5 databases per 1 autovacuum worker',
    reference=(
        '/9.1/static/runtime-config-autovacuum.html#GUC-AUTOVACUUM-NAPTIME'
    )
)
print(
    'autovacuum_naptime = %smin\n' % (
        max(int(ceil(DATABASE_COUNT / 5 * 2 / AUTOVACUUM_WORKERS)), 1)
    )
)

output_description(
    description='Checkpoint completion, as a fraction of total time.',
    default='0.5',
    recommended='0.9',
    reference=(
        '/9.1/static/runtime-config-wal.html#GUC-CHECKPOINT-COMPLETION-TARGET'
    )
)
print('checkpoint_completion_target = 0.9\n')

output_description(
    description=(
        'Planner\'s cost estimate of a non-sequential-fetch operation.'
    ),
    default='4.0',
    recommended='2.0',
    reference='/9.1/static/runtime-config-query.html#GUC-RANDOM-PAGE-COST'
)
print('random_page_cost = 2.0\n')
