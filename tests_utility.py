import sys
import subprocess
import re
import os
import moment
import json
import argparse

__author__ = "Nathan Danzmann de Freitas"


def json_output(debug, simplified):
    """
    Beautify JSON output for screen or filewriting by indenting the response dictionaries
    :param debug: DEBUG part of results
    :param simplified: In case simplified mode is being used, only minimal DEBUG information is to be shown
    """
    first_pass = debug.split('DEBUG:{"body": "')[1]

    if not simplified:
        second_pass = first_pass.split('", "response')[0].replace("\\", "")

        third_pass = first_pass.split(', "failures": ')

        fourth_pass = third_pass[1][:third_pass[1].rfind(']}')]

        result = "{" + '"response" : ' + second_pass + ', "failures" : ' + fourth_pass + "]}"

    else:
        get_error = '"error" : ' + re.findall('"errorMessage": (.*), "registeredError": [0-1]}"',
                                              first_pass.replace("\\", ""))[0]

        get_url = '"url" : ' + re.findall('"_url":(.*?),', first_pass)[0]

        get_group = '"group" : ' + re.findall('"group":(.*?),', first_pass)[0]

        get_name = '"name" : ' + re.findall('"name":(.*?),', first_pass)[0]

        result = ",".join([get_group, get_name, get_url, get_error])

        result = '{ "debug": {' + result + '}}'.replace("\\", "")

    try:
        result = json.loads(result)
    except ValueError:
        pass

    return json.dumps(result, sort_keys=True, indent=4, separators=(',', ':'))


def results_screen(detail_results, just_errors=False, simplified=False):
    """
    Show result in screen
    :param detail_results: List of headers and DEBUG section for every test
    :param just_errors: Show just the errors instead of full DEBUG
    :param simplified: In case simplified mode is being used, only minimal DEBUG information is to be shown
    """
    for result in detail_results:
        print("\n\n")
        for ind, a in enumerate(result):
            if not just_errors:
                if "DEBUG:" in a:
                    print("------------ DEBUG -----------")
                    print(json_output(a, simplified))
                else:
                    print("------------ INFO ------------")
                    print(a)
                print("\n" * 1)
            else:
                try:
                    if "ERROR:" in result[ind+1]:
                        if not simplified:
                            print("------------ INFO -----------")
                            print(a)
                        print("------------ DEBUG -----------")
                        print(json_output(result[ind+1], simplified))
                except:
                    continue


def results_file(detail_results, just_errors=False, simplified=False):
    """
    Write result to file
    :param detail_results: List of headers and DEBUG section for every test
    :param just_errors: In case only errors must be written to file
    :param simplified: In case simplified mode is being used, only minimal DEBUG information is to be shown
    """
    today = moment.now().format("YYYYMMDD")
    now = moment.now().format("HH:mm:ss")
    if not os.path.exists("logs/logs_" + today):
        os.makedirs("logs/logs_" + today)
    logfile = open("logs/logs_" + today + "/log_" + now + ".txt", "w")
    for result in detail_results:
        for ind, type in enumerate(result):
            if not just_errors:
                if "DEBUG:" in type:
                    logfile.write("------------ DEBUG -----------")
                    logfile.write(json_output(type, simplified))
                else:
                    logfile.write("------------ INFO ------------")
                    logfile.write(type)
                logfile.write("\n" * 1)
            else:
                try:
                    if "ERROR:" in result[ind+1]:
                        if not simplified:
                            logfile.write("------------ INFO -----------")
                            logfile.write(type)
                        logfile.write("------------ DEBUG -----------")
                        logfile.write(json_output(result[ind+1], simplified))
                    logfile.write("\n"*1)
                except:
                    continue
    logfile.close()
    logtest = open("logs/logs_" + today + "/log_" + now + ".txt", "r")
    if logtest.readline() == "":
        os.remove("logs/logs_" + today + "/log_" + now + ".txt")
    else:
        print("\n\nResults written to: logs/logs_" + today + "/log_" + now + ".txt")
    logtest.close()


def show_results(detail_results, test_results, args):
    """
    Show results after being processed by process_results()

    :param detail_results: detailed results list from processed string
    :param test_results: simple test results from processed string
    :param args: In case application is being run in arguments mode
    """
    if args.test_api is None and args.all is False:

        print("Test results: \n")
        for result in test_results:
            print(result)

        while True:

            print("\nWhat do you want to do now?\n"
                  "1- Full debug\n"
                  "2- Just errors\n"
                  "3- Just errors simplified (minimal output)\n"
                  "4- Nothing")
            choice = str(input("-> "))

            if choice in ("1", "2", "3"):

                simplified = False
                if choice == "1":
                    just_errors = False
                else:
                    just_errors = True

                if choice == "3":
                    just_errors = True
                    simplified = True

                print("\n\n\n1- DEBUG on Screen\n2- Write DEBUG to file\n3- Both previous")
                choice = str(input("-> "))

                if choice == "1":
                    results_screen(detail_results, just_errors, simplified)

                elif choice == "2":
                    results_file(detail_results, just_errors, simplified)

                elif choice == "3":
                    results_screen(detail_results, just_errors, simplified)
                    results_file(detail_results, just_errors, simplified)

                else:
                    print("unknown option")
                    return
            elif choice == "4":
                return

            else:
                print("unknown option \n")

    else:

        if args.ignore_info is True:
            simplified = True
            args.only_errors = True
        else:
            simplified = False

        if args.silent is False:
            if args.only_errors is True:
                results_screen(detail_results, True, simplified)
            else:
                results_screen(detail_results, False)

        if args.write is True:
            if args.only_errors is True:
                results_file(detail_results, True, simplified)
            else:
                results_file(detail_results, False)

        print("Test results: \n")
        for result in test_results:
            print(result)


def process_results(result, args):
    """
    Process the result from the test subprocess after finished and parses the string accordingly

    :param result: string raw result from test subprocess completion
    :param args: In case application is being run in arguments mode, pass arguments over to show_results()
    """
    result = result.lstrip('\'b')

    # Splits every test by searching for the first line (from curl headers, "Trying <server ip>...")
    result_list = re.split(r"\*[ ]*Trying [0-9]+\.[0-9]+\.[0-9]+\.[0-9]...", result)

    # List contains the final test results
    test_results = []
    # List contains curl headers and DEBUG result for every test
    detail_results = []

    for n, item in enumerate(result_list):

        # Separates headers from debug part by searching last string in headers part ("Closing Connection <N>")
        separator = re.split(r"\* Closing connection [0-9]", item)
        try:
            debug = separator[1]
            curl = separator[0]

            detail_results.append([curl, debug])

            # In case is the last debug, it will contain the final results of the test at the end
            if "Test Group" in debug:
                # Separates every result by splitting through "Test Group" string
                temp_result = re.split(r"Test Group", debug)
                # Removes everything before the test results (rest of DEBUG)
                temp_result.pop(0)

                test_results = temp_result

                # During "Test Group" split, first result ASCII color code is removed, so here we put it back
                # Green color code for success and red for fail
                if "SUCCEEDED" in test_results[0]:
                    test_results[0] = "\x1b[92m" + test_results[0]
                else:
                    test_results[0] = "\x1b[91m" + test_results[0]

        except:
            continue

    show_results(detail_results, test_results, args)
    return


def subprocess_run(test, args):
    """
    Starts subprocess of pyresttest for the specified test
    :param test: test to be run
    :param args: In case of argument mode, pass arguments over to next function (process_results())
    """
    print("\nStarting test '" + test + "...'")
    process = subprocess.Popen(['pyresttest', 'url', test, '--import_extensions',
                                "tests_extension", "--verbose", "--log", "DEBUG"],
                               stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                               stderr=subprocess.STDOUT, shell=False)
    print("\nPlease wait while test is being run")
    result = str(process.stdout.read())
    print("\nTest finished\n")
    try:
        process_results(result, args)
    except Exception as e:
        print ("An error has occured: " + e.message)
    return


def argument_run(arguments):
    """
    In case of argument mode, will check if arguments were correctly passed and call run_choice() with relevant test
    :param arguments: arguments from parser
    """

    api = arguments.test_api
    if arguments.all is True:
        for test in (1, 2, 3, 4, 5):
            run_choice(str(test), arguments)

        # Concatenate multiple log files
        if arguments.write is True:
            print("Multiple logs created, concatenating....")
            dir = "logs/logs_" + moment.now().format("YYYYMMDD")
            newfile = dir + "/log_" + moment.now().add(seconds=1).format("HH:mm:ss") + ".txt"

            files = os.listdir(dir)
            with open(newfile, 'w') as outfile:
                for f in files:
                    with open(dir + "/" + f, 'rb') as fd:
                        outfile.write(fd.read())
                    fd.close()
            outfile.close()
            for file in files:
                os.remove(dir + "/" + file)
            print("All log files concatenated under: " + newfile)

        if arguments.menu is False:
            return -1
        else:
            return 1

    else:
        if api not in (1, 2, 3, 4, 5):
            print("Error: api argument for [--test-api] must be between 1 - 5")
            return -1
        run_choice(str(api), arguments)
    if arguments.menu is True:
        return 1
    else:
        return -1


def run_choice(choice, args=None):
    """
    Runs specific test according to choice from menu or argument

    :param choice: test run choice
    :param args: in case of arguments, pass arguments over to next function
    """
    if choice == "1":

        subprocess_run("quickstart.yaml", args)

    else:
        print("Unknown option, please try again")
    return


def main():
    """
    Main

    """
    parser = argparse.ArgumentParser(description="Automatically tests REST APIs with pyresttest.\nArguments optional"
                                                 " and all configuration can be done real-time on terminal menu.\n"
                                                 "Menu is opened on execution of test_utility with no args,"
                                                 "otherwise all operations can be done on following arguments:")
    parser.add_argument('-t', '--test-api', type=int, required=False,
                        help="Which test to run, refer to menu for test numbering")

    parser.add_argument('-e', '--only-errors', action='store_true', required=False,
                        help="Silences debug of successful tests and debug only for errors on screen,"
                             " and file if used with [-w]")

    parser.add_argument('-w', '--write', action='store_true', required=False,
                        help="Write output to log file")

    parser.add_argument('-s', '--silent', action='store_true', required=False,
                        help="Do not show any debug, only simple test result (does not silences output to file)")

    parser.add_argument('-m', '--menu', action='store_true', required=False,
                        help="Redirect to interface menu after tests completion")

    parser.add_argument('-a', '--all', action='store_true', required=False,
                        help="Run all tests")

    parser.add_argument('-i', '--ignore-info', action='store_true', required=False,
                        help="Ignore info from tests and show only minimum debug information "
                             "(option 'only_errors' [-e] will be enforced)")

    arguments = parser.parse_args()

    if (True in vars(arguments).values() and arguments.all is False) and arguments.test_api is None:
        print("Error: if using arguments mode, test_api argument must not be empty!\n"
              "Use python test_utility.py -h for more information")
        exit(1)

    if arguments.all is True and arguments.test_api is not None:
        print("Error: if using [--all], calling single test with [--test-api] is not allowed")
        exit(1)

    if arguments.silent is True \
            and (arguments.ignore_info is True or arguments.only_errors is True) \
            and arguments.write is False:
        print("Error: if using [--silent], the usage of [--ignore-info] and/or [--only-errors] "
              "is not allowed, except if writing to file [-w]")
        exit(1)

    # Stores result code from argument run if started from argument command line
    result_code = None

    if sys.version_info[0] > 3:
        print("Please rerun with python2")
        return

    print("\n\nRESTful API test utility")

    # If started from argument command line, calls argument_run()
    if arguments.test_api is not None or arguments.all is True:
        result_code = argument_run(arguments)

    while True:
        print("\n\nMenu:")
        print("1- Quick API tests (all APIs)\n"
              "0- Quit")
        choice = str(input("-> "))

        if choice != "0":
            run_choice(choice)

        else:
            break


if __name__ == "__main__":
    main()
