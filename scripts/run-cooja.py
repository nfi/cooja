#!/usr/bin/env python3

import argparse
import sys
import os
import time
import traceback
import subprocess
from subprocess import PIPE, STDOUT, CalledProcessError

# Find path to this script
SELF_PATH = os.path.dirname(os.path.abspath(__file__))
# Find path to Contiki-NG relative to this script
COOJA_PATH = os.path.dirname(SELF_PATH)

CONTIKI_PATH = os.path.normpath(os.path.join(os.path.dirname(COOJA_PATH), "contiki-ng"))
cooja_log = 'COOJA.log'


#######################################################
# Run a child process and get its output

def _run_command(command):
    try:
        proc = subprocess.run(command, stdout=PIPE, stderr=STDOUT, shell=True, universal_newlines=True)
        return proc.returncode, proc.stdout if proc.stdout else ''
    except CalledProcessError as e:
        print(f"Command failed: {e}", file=sys.stderr)
        return e.returncode, e.stdout if e.stdout else ''
    except (OSError, Exception) as e:
        traceback.print_exc()
        return -1, str(e)


def _remove_file(filename):
    try:
        os.remove(filename)
    except FileNotFoundError:
        pass


#############################################################
# Run a single instance of Cooja on a given simulation script

def run_simulation(cooja_file, output_path=None, debug=False):
    # Remove any old simulation logs
    _remove_file(cooja_log)

    target_basename = cooja_file
    if target_basename.endswith('.csc.gz'):
        target_basename = target_basename[:-7]
    elif target_basename.endswith('.csc'):
        target_basename = target_basename[:-4]
    simulation_id = str(round(time.time() * 1000))
    if output_path is not None:
        target_basename = os.path.join(output_path, target_basename)
    target_basename += '-dt-' + simulation_id
    target_basename_fail = target_basename + '-fail'
    target_script_output = os.path.join(target_basename, 'script.log')
    target_log_output = os.path.join(target_basename, 'cooja.log')
    print(f'Saving data trace "{target_basename}"')

    command = (f'{COOJA_PATH}/gradlew -p {COOJA_PATH} --console=plain run '
               f'--args="-nogui={cooja_file} -contiki={CONTIKI_PATH} '
               f'-datatrace={target_basename} -logdir={os.getcwd()}"')
    if debug:
        sys.stdout.write(f"  Running Cooja:\n    {command}\n")

    start_time = time.perf_counter_ns()
    (return_code, output) = _run_command(command)
    end_time = time.perf_counter_ns()
    with open(cooja_log, 'a') as f:
        f.write(f'\nSimulation execution time: {end_time - start_time} ns.\n')

    if not os.path.isdir(target_basename):
        os.mkdir(target_basename)
    has_script_output = os.path.isfile(target_script_output)
    os.rename(cooja_log, target_log_output)

    if return_code != 0 or not has_script_output:
        print(f"Failed, ret code={return_code}, output:", file=sys.stderr)
        print("-----", file=sys.stderr)
        print(output, file=sys.stderr, end='')
        print("-----", file=sys.stderr)
        if not has_script_output:
            print("No Cooja simulation script output!", file=sys.stderr)
        os.rename(target_basename, target_basename_fail)
        return False

    if debug:
        print("  Checking for output...")

    is_done = False
    with open(target_script_output, "r") as f:
        for line in f.readlines():
            parts = line.strip().split('\t')
            if len(parts) == 2 and parts[1] == "TEST OK":
                is_done = True
                continue

    if not is_done:
        print("  test failed.")
        os.rename(target_basename, target_basename_fail)
        return False

    print(f"  test done in {round((end_time - start_time) / 1000000)} milliseconds.")
    return True


#######################################################
# Run the application

def main(parser=None):
    if not os.path.isfile(os.path.join(COOJA_PATH, 'build.gradle')):
        sys.exit(f'Cooja not found in "{COOJA_PATH}"')
    if not os.path.isfile(os.path.join(CONTIKI_PATH, 'Makefile.include')):
        sys.exit(f'Contiki-NG not found in "{CONTIKI_PATH}"')

    if not parser:
        parser = argparse.ArgumentParser()
    parser.add_argument('-o', dest='output_path')
    parser.add_argument('-d', dest='debug', type=bool, default=False)
    parser.add_argument('input', nargs='+')
    try:
        args = parser.parse_args(sys.argv[1:])
    except Exception as e:
        sys.exit(f"Illegal arguments: {e}")

    if args.output_path and not os.path.isdir(args.output_path):
        os.mkdir(args.output_path)

    for file in args.input:
        simulation_file = os.path.abspath(file)
        if not os.access(simulation_file, os.R_OK):
            print(f'Can not read simulation script "{simulation_file}"', file=sys.stderr)
            sys.exit(1)

        print(f'Running simulation "{simulation_file}"')
        if not run_simulation(simulation_file, args.output_path, debug=args.debug):
            sys.exit(f'Failed to run simulation "{simulation_file}"')

    print('Done. No more simulation files specified.')


#######################################################

if __name__ == '__main__':
    main()
