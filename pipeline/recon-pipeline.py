#!/usr/bin/env python
import os
import sys
import time
import shlex
import shutil
import tempfile
import textwrap
import selectors
import threading
import subprocess
import webbrowser
from enum import IntEnum
from pathlib import Path
from typing import List, NewType

DEFAULT_PROMPT = "recon-pipeline> "

os.environ["PYTHONPATH"] = f"{os.environ.get('PYTHONPATH')}:{str(Path(__file__).expanduser().resolve().parents[1])}"
os.environ["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
sys.path.append(str(Path.home() / ".local" / "bin"))

import cmd2
from cmd2.ansi import style

def cluge_package_imports(name, package):
    if name == "__main__" and package is None:
        file = Path(__file__).expanduser().resolve()
        parent, top = file.parent, file.parents[1]

        sys.path.append(str(top))
        try:
            sys.path.remove(str(parent))
        except ValueError:
            pass

        import pipeline

        sys.modules[name].__package__ = "pipeline"

cluge_package_imports(name=__name__, package=__package__)

from .recon.config import defaults
from .models.nse_model import NSEResult
from .models.db_manager import DBManager
from .models.nmap_model import NmapResult
from .models.technology_model import Technology
from .models.searchsploit_model import SearchsploitResult

from .recon import (
    get_scans,
    scan_parser,
    view_parser,
    tools_parser,
    status_parser,
    database_parser,
    db_attach_parser,
    db_delete_parser,
    db_detach_parser,
    db_list_parser,
    tools_list_parser,
    tools_install_parser,
    tools_uninstall_parser,
    tools_reinstall_parser,
    target_results_parser,
    endpoint_results_parser,
    nmap_results_parser,
    technology_results_parser,
    searchsploit_results_parser,
    port_results_parser,
)

from .tools import tools

class ToolAction(IntEnum):
    INSTALL = 0
    UNINSTALL = 1

ToolActions = NewType("ToolActions", ToolAction)

selector = selectors.DefaultSelector()

class SelectorThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()
        for key in selector.get_map():
            selector.get_key(key).fileobj.close()

    def stopped(self):
        return self._stop_event.is_set()

    def run(self):
        while not self.stopped():
            for k, mask in selector.select():
                callback = k.data
                callback(k.fileobj)

class ReconShell(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_mgr = None
        self.sentry = False
        self.self_in_py = True
        self.selectorloop = None
        self.continue_install = True
        self.prompt = DEFAULT_PROMPT
        self.tools_dir = Path(defaults.get("tools-dir"))

        self._initialize_parsers()

        self.tools_dir.mkdir(parents=True, exist_ok=True)
        Path(defaults.get("database-dir")).mkdir(parents=True, exist_ok=True)
        Path(defaults.get("gopath")).mkdir(parents=True, exist_ok=True)
        Path(defaults.get("goroot")).mkdir(parents=True, exist_ok=True)

        self.register_preloop_hook(self._preloop_hook)
        self.register_postloop_hook(self._postloop_hook)

    def _initialize_parsers(self):
        db_list_parser.set_defaults(func=self.database_list)
        db_attach_parser.set_defaults(func=self.database_attach)
        db_detach_parser.set_defaults(func=self.database_detach)
        db_delete_parser.set_defaults(func=self.database_delete)
        endpoint_results_parser.set_defaults(func=self.print_endpoint_results)
        target_results_parser.set_defaults(func=self.print_target_results)
        nmap_results_parser.set_defaults(func=self.print_nmap_results)
        technology_results_parser.set_defaults(func=self.print_webanalyze_results)
        searchsploit_results_parser.set_defaults(func=self.print_searchsploit_results)
        port_results_parser.set_defaults(func=self.print_port_results)
        tools_install_parser.set_defaults(func=self.tools_install)
        tools_reinstall_parser.set_defaults(func=self.tools_reinstall)
        tools_uninstall_parser.set_defaults(func=self.tools_uninstall)
        tools_list_parser.set_defaults(func=self.tools_list)

    def _preloop_hook(self):
        self.selectorloop = SelectorThread(daemon=True)
        self.selectorloop.start()

    def _postloop_hook(self):
        if self.selectorloop.is_alive():
            self.selectorloop.stop()
        selector.close()

    def _install_error_reporter(self, stderr):
        output = stderr.readline()
        if not output:
            return
        output = output.decode().strip()
        self.async_alert(style(f"[!] {output}", fg="bright_red"))

    def _luigi_pretty_printer(self, stderr):
        output = stderr.readline()
        if not output:
            return
        output = output.decode()
        if "===== Luigi Execution Summary =====" in output:
            self.async_alert("")
            self.sentry = True
        if self.sentry:
            self.async_alert(style(output.strip(), fg="bright_blue"))
        elif output.startswith("INFO: Informed") and output.strip().endswith("PENDING"):
            words = output.split()
            self.async_alert(style(f"[-] {words[5].split('_')[0]} queued", fg="bright_white"))
        elif output.startswith("INFO: ") and "running" in output:
            words = output.split()
            scantypeidx = words.index("running") + 1
            scantype = words[scantypeidx].split("(", 1)[0]
            self.async_alert(style(f"[*] {scantype} running...", fg="bright_yellow"))
        elif output.startswith("INFO: Informed") and output.strip().endswith("DONE"):
            words = output.split()
            self.async_alert(style(f"[+] {words[5].split('_')[0]} complete!", fg="bright_green"))

    def check_scan_directory(self, directory):
        directory = Path(directory)
        if directory.exists():
            term_width = shutil.get_terminal_size((80, 20)).columns
            warning_msg = (
                f"[*] Your results-dir ({str(directory)}) already exists. Subfolders/files may tell "
                f"the pipeline that the associated Task is complete. This means that your scan may start "
                f"from a point you don't expect. Your options are as follows:"
            )
            for line in textwrap.wrap(warning_msg, width=term_width, subsequent_indent="    "):
                self.poutput(style(line, fg="bright_yellow"))
            option_one = (
                "Resume existing scan (use any existing scan data & only attempt to scan what isn't already done)"
            )
            option_two = "Remove existing directory (scan starts from the beginning & all existing results are removed)"
            option_three = "Save existing directory (your existing folder is renamed and your scan proceeds)"
            answer = self.select([("Resume", option_one), ("Remove", option_two), ("Save", option_three)])
            if answer == "Resume":
                self.poutput(style("[+] Resuming scan from last known good state.", fg="bright_green"))
            elif answer == "Remove":
                shutil.rmtree(Path(directory))
                self.poutput(style("[+] Old directory removed, starting fresh scan.", fg="bright_green"))
            elif answer == "Save":
                current = time.strftime("%Y%m%d-%H%M%S")
                directory.rename(f"{directory}-{current}")
                self.poutput(
                    style(f"[+] Starting fresh scan.  Old data saved as {directory}-{current}", fg="bright_green")
                )

    @cmd2.with_argparser(scan_parser)
    def do_scan(self, args):
        if self.db_mgr is None:
            return self.poutput(
                style("[!] You are not connected to a database; run database attach before scanning", fg="bright_red")
            )
        self.check_scan_directory(args.results_dir)
        self.poutput(
            style(
                "If anything goes wrong, rerun your command with --verbose to enable debug statements.",
                fg="cyan",
                dim=True,
            )
        )
        scans = get_scans()
        try:
            command = ["luigi", "--module", scans.get(args.scantype)[0]]
        except TypeError:
            return self.poutput(
                style(f"[!] {args.scantype} or one of its dependencies is not installed", fg="bright_red")
            )
        tgt_file_path = None
        if args.target:
            tgt_file_fd, tgt_file_path = tempfile.mkstemp()
            tgt_file_path = Path(tgt_file_path)
            tgt_idx = args.__statement__.arg_list.index("--target")
            tgt_file_path.write_text(args.target)
            args.__statement__.arg_list[tgt_idx + 1] = str(tgt_file_path)
            args.__statement__.arg_list[tgt_idx] = "--target-file"
        command.extend(args.__statement__.arg_list)
        command.extend(["--db-location", str(self.db_mgr.location)])
        if args.sausage:
            command.pop(command.index("--sausage"))
            webbrowser.open("http://127.0.0.1:8082")
        if args.verbose:
            command.pop(command.index("--verbose"))
            subprocess.run(command)
        else:
            proc = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            selector.register(proc.stderr, selectors.EVENT_READ, self._luigi_pretty_printer)
        self.add_dynamic_parser_arguments()

    def _get_dict(self):
        return tools

    def _finalize_tool_action(self, tool: str, tool_dict: dict, return_values: List[int], action: ToolActions):
        verb = ["install", "uninstall"][action.value]
        if all(x == 0 for x in return_values):
            self.poutput(style(f"[+] {tool} {verb}ed!", fg="bright_green"))
            tool_dict[tool]["installed"] = True if action == ToolAction.INSTALL else False
        else:
            tool_dict[tool]["installed"] = False if action == ToolAction.INSTALL else True
            self.poutput(
                style(
                    f"[!!] one (or more) of {tool}'s commands failed and may have not {verb}ed properly; check output from the offending command above...",
                    fg="bright_red",
                    bold=True,
                )
            )

    def tools_install(self, args):
        if args.tool == "all":
            [
                self.poutput(style(f"[-] {x} queued", fg="bright_white"))
                for x in tools.keys()
                if not tools.get(x).get("installed")
            ]
            for tool in tools.keys():
                self.do_tools(f"install {tool}")
            return
        if tools.get(args.tool).get("dependencies"):
            for dependency in tools.get(args.tool).get("dependencies"):
                if tools.get(dependency).get("installed"):
                    continue
                self.poutput(
                    style(f"[!] {args.tool} has an unmet dependency; installing {dependency}", fg="yellow", bold=True)
                )
                self.do_tools(f"install {dependency}")
        if tools.get(args.tool).get("installed"):
            return self.poutput(style(f"[!] {args.tool} is already installed.", fg="yellow"))
        else:
            retvals = list()
            self.poutput(style(f"[*] Installing {args.tool}...", fg="bright_yellow"))
            addl_env_vars = tools.get(args.tool).get("environ")
            if addl_env_vars is not None:
                addl_env_vars.update(dict(os.environ))
            for command in tools.get(args.tool, {}).get("install_commands", []):
                self.poutput(style(f"[=] {command}", fg="cyan"))
                if tools.get(args.tool).get("shell"):
                    proc = subprocess.Popen(
                        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=addl_env_vars
                    )
                else:
                    proc = subprocess.Popen(
                        shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=addl_env_vars
                    )
                out, err = proc.communicate()
                if err:
                    self.poutput(style(f"[!] {err.decode().strip()}", fg="bright_red"))
                retvals.append(proc.returncode)
        self._finalize_tool_action(args.tool, tools, retvals, ToolAction.INSTALL)

    def tools_uninstall(self, args):
        if args.tool == "all":
            [
                self.poutput(style(f"[-] {x} queued", fg="bright_white"))
                for x in tools.keys()
                if tools.get(x).get("installed")
            ]
            for tool in tools.keys():
                self.do_tools(f"uninstall {tool}")
            return
        if not tools.get(args.tool).get("installed"):
            return self.poutput(style(f"[!] {args.tool} is not installed.", fg="yellow"))
        else:
            retvals = list()
            self.poutput(style(f"[*] Removing {args.tool}...", fg="bright_yellow"))
            if not tools.get(args.tool).get("uninstall_commands"):
                self.poutput(style(f"[*] {args.tool} removal not needed", fg="bright_yellow"))
                return
            for command in tools.get(args.tool).get("uninstall_commands"):
                self.poutput(style(f"[=] {command}", fg="cyan"))
                proc = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = proc.communicate()
                if err:
                    self.poutput(style(f"[!] {err.decode().strip()}", fg="bright_red"))
                retvals.append(proc.returncode)
        self._finalize_tool_action(args.tool, tools, retvals, ToolAction.UNINSTALL)

    def tools_reinstall(self, args):
        self.do_tools(f"uninstall {args.tool}")
        self.do_tools(f"install {args.tool}")

    def tools_list(self, args):
        for key, value in tools.items():
            status = [style(":Missing:", fg="bright_magenta"), style("Installed", fg="bright_green")]
            self.poutput(style(f"[{status[value.get('installed')]}] - {value.get('path') or key}"))

    @cmd2.with_argparser(tools_parser)
    def do_tools(self, args):
        func = getattr(args, "func", None)
        if func is not None:
            func(args)
        else:
            self.do_help("tools")

    @cmd2.with_argparser(status_parser)
    def do_status(self, args):
        webbrowser.open(f"http://{args.host}:{args.port}")

    @staticmethod
    def get_databases():
        dbdir = defaults.get("database-dir")
        for db in sorted(Path(dbdir).iterdir()):
            yield db

    def database_list(self, args):
        try:
            next(self.get_databases())
        except StopIteration:
            return self.poutput(style("[-] There are no databases.", fg="bright_white"))
        for i, location in enumerate(self.get_databases(), start=1):
            self.poutput(style(f"   {i}. {location}"))

    def database_attach(self, args):
        locations = [str(x) for x in self.get_databases()] + ["create new database"]
        location = self.select(locations)
        if location == "create new database":
            location = self.read_input(
                style("new database name? (recommend something unique for this target)\n-> ", fg="bright_white")
            )
            new_location = str(Path(defaults.get("database-dir")) / location)
            index = sorted([new_location] + locations[:-1]).index(new_location) + 1
            self.db_mgr = DBManager(db_location=new_location)
            self.poutput(style(f"[*] created database @ {new_location}", fg="bright_yellow"))
            location = new_location
        else:
            index = locations.index(location) + 1
            self.db_mgr = DBManager(db_location=location)
        self.add_dynamic_parser_arguments()
        self.poutput(
            style(f"[+] attached to sqlite database @ {Path(location).expanduser().resolve()}", fg="bright_green")
        )
        self.prompt = f"[db-{index}] {DEFAULT_PROMPT}"

    def add_dynamic_parser_arguments(self):
        port_results_parser.add_argument("--host", choices=self.db_mgr.get_all_targets(), help="filter results by host")
        port_results_parser.add_argument(
            "--port-number", choices=self.db_mgr.get_all_port_numbers(), help="filter results by port number"
        )
        endpoint_results_parser.add_argument(
            "--status-code", choices=self.db_mgr.get_status_codes(), help="filter results by status code"
        )
        endpoint_results_parser.add_argument(
            "--host", choices=self.db_mgr.get_all_targets(), help="filter results by host"
        )
        nmap_results_parser.add_argument("--host", choices=self.db_mgr.get_all_targets(), help="filter results by host")
        nmap_results_parser.add_argument(
            "--nse-script", choices=self.db_mgr.get_all_nse_script_types(), help="filter results by nse script type ran"
        )
        nmap_results_parser.add_argument(
            "--port", choices=self.db_mgr.get_all_port_numbers(), help="filter results by port scanned"
        )
        nmap_results_parser.add_argument(
            "--product", help="filter results by reported product", choices=self.db_mgr.get_all_nmap_reported_products()
        )
        technology_results_parser.add_argument(
            "--host", choices=self.db_mgr.get_all_targets(), help="filter results by host"
        )
        technology_results_parser.add_argument(
            "--type", choices=self.db_mgr.get_all_web_technology_types(), help="filter results by type"
        )
        technology_results_parser.add_argument(
            "--product", choices=self.db_mgr.get_all_web_technology_products(), help="filter results by product"
        )
        searchsploit_results_parser.add_argument(
            "--host", choices=self.db_mgr.get_all_targets(), help="filter results by host"
        )
        searchsploit_results_parser.add_argument(
            "--type", choices=self.db_mgr.get_all_exploit_types(), help="filter results by exploit type"
        )

    def database_detach(self, args):
        if self.db_mgr is None:
            return self.poutput(style("[!] you are not connected to a database", fg="magenta"))
        self.db_mgr.close()
        self.poutput(style(f"[*] detached from sqlite database @ {self.db_mgr.location}", fg="bright_yellow"))
        self.db_mgr = None
        self.prompt = DEFAULT_PROMPT

    def database_delete(self, args):
        locations = [str(x) for x in self.get_databases()]
        to_delete = self.select(locations)
        index = locations.index(to_delete) + 1
        Path(to_delete).unlink()
        if f"[db-{index}]" in self.prompt:
            self.poutput(style(f"[*] detached from sqlite database at {self.db_mgr.location}", fg="bright_yellow"))
            self.prompt = DEFAULT_PROMPT
            self.db_mgr.close()
            self.db_mgr = None
        self.poutput(
            style(f"[+] deleted sqlite database @ {Path(to_delete).expanduser().resolve()}", fg="bright_green")
        )

    @cmd2.with_argparser(database_parser)
    def do_database(self, args):
        func = getattr(args, "func", None)
        if func is not None:
            func(args)
        else:
            self.do_help("database")

    def print_target_results(self, args):
        results = list()
        printer = self.ppaged if args.paged else self.poutput
        if args.type == "ipv4":
            targets = self.db_mgr.get_all_ipv4_addresses()
        elif args.type == "ipv6":
            targets = self.db_mgr.get_all_ipv6_addresses()
        elif args.type == "domain-name":
            targets = self.db_mgr.get_all_hostnames()
        else:
            targets = self.db_mgr.get_all_targets()
        for target in targets:
            if args.vuln_to_subdomain_takeover:
                tgt = self.db_mgr.get_or_create_target_by_ip_or_hostname(target)
                if not tgt.vuln_to_sub_takeover:
                    continue
                vulnstring = style("vulnerable", fg="green")
                vulnstring = f"[{vulnstring}] {target}"
                results.append(vulnstring)
            else:
                results.append(target)
        if results:
            printer("\n".join(results))

    def print_endpoint_results(self, args):
        host_endpoints = status_endpoints = None
        printer = self.ppaged if args.paged else self.poutput
        color_map = {"2": "green", "3": "blue", "4": "bright_red", "5": "bright_magenta"}
        if args.status_code is not None:
            status_endpoints = self.db_mgr.get_endpoint_by_status_code(args.status_code)
        if args.host is not None:
            host_endpoints = self.db_mgr.get_endpoints_by_ip_or_hostname(args.host)
        endpoints = self.db_mgr.get_all_endpoints()
        for subset in [status_endpoints, host_endpoints]:
            if subset is not None:
                endpoints = set(endpoints).intersection(set(subset))
        results = list()
        for endpoint in endpoints:
            color = color_map.get(str(endpoint.status_code)[0])
            if args.plain or endpoint.status_code is None:
                results.append(endpoint.url)
            else:
                results.append(f"[{style(endpoint.status_code, fg=color)}] {endpoint.url}")
            if not args.headers:
                continue
            for header in endpoint.headers:
                if args.plain:
                    results.append(f"  {header.name}: {header.value}")
                else:
                    results.append(style(f"  {header.name}:", fg="cyan") + f" {header.value}")
        if results:
            printer("\n".join(results))

    def print_nmap_results(self, args):
        results = list()
        printer = self.ppaged if args.paged else self.poutput
        if args.host is not None:
            scans = self.db_mgr.get_nmap_scans_by_ip_or_hostname(args.host)
        else:
            scans = self.db_mgr.get_and_filter(NmapResult)
        if args.port is not None or args.product is not None:
            tmpscans = scans[:]
            for scan in scans:
                if args.port is not None and scan.port.port_number != int(args.port) and scan in tmpscans:
                    del tmpscans[tmpscans.index(scan)]
                if args.product is not None and scan.product != args.product and scan in tmpscans:
                    del tmpscans[tmpscans.index(scan)]
            scans = tmpscans
        if args.nse_script:
            for nse_scan in self.db_mgr.get_and_filter(NSEResult, script_id=args.nse_script):
                for nmap_result in nse_scan.nmap_results:
                    if nmap_result not in scans:
                        continue
                    results.append(nmap_result.pretty(nse_results=[nse_scan], commandline=args.commandline))
        else:
            for scan in scans:
                results.append(scan.pretty(commandline=args.commandline))
        if results:
            printer("\n".join(results))

    def print_webanalyze_results(self, args):
        results = list()
        printer = self.ppaged if args.paged else self.poutput
        filters = dict()
        if args.type is not None:
            filters["type"] = args.type
        if args.product is not None:
            filters["text"] = args.product
        if args.host:
            tgt = self.db_mgr.get_or_create_target_by_ip_or_hostname(args.host)
            printer(args.host)
            printer("=" * len(args.host))
            for tech in tgt.technologies:
                if args.product is not None and args.product != tech.text:
                    continue
                if args.type is not None and args.type != tech.type:
                    continue
                printer(f"   - {tech.text} ({tech.type})")
        else:
            for scan in self.db_mgr.get_and_filter(Technology, **filters):
                results.append(scan.pretty(padlen=1))
        if results:
            printer("\n".join(results))

    def print_searchsploit_results(self, args):
        results = list()
        targets = self.db_mgr.get_all_targets()
        printer = self.ppaged if args.paged else self.poutput
        for ss_scan in self.db_mgr.get_and_filter(SearchsploitResult):
            tmp_targets = set()
            if (
                args.host is not None
                and self.db_mgr.get_or_create_target_by_ip_or_hostname(args.host) != ss_scan.target
            ):
                continue
            if ss_scan.target.hostname in targets:
                tmp_targets.add(ss_scan.target.hostname)
                targets.remove(ss_scan.target.hostname)
            for ipaddr in ss_scan.target.ip_addresses:
                address = ipaddr.ipv4_address or ipaddr.ipv6_address
                if address is not None and address in targets:
                    tmp_targets.add(address)
                    targets.remove(address)
            if tmp_targets:
                header = ", ".join(tmp_targets)
                results.append(header)
                results.append("=" * len(header))
                for scan in ss_scan.target.searchsploit_results:
                    if args.type is not None and scan.type != args.type:
                        continue
                    results.append(scan.pretty(fullpath=args.fullpath))
        if results:
            printer("\n".join(results))

    def print_port_results(self, args):
        results = list()
        targets = self.db_mgr.get_all_targets()
        printer = self.ppaged if args.paged else self.poutput
        for target in targets:
            if args.host is not None and target != args.host:
                continue
            ports = [
                str(port.port_number) for port in self.db_mgr.get_or_create_target_by_ip_or_hostname(target).open_ports
            ]
            if args.port_number and args.port_number not in ports:
                continue
            if ports:
                results.append(f"{target}: {','.join(ports)}")
        if results:
            printer("\n".join(results))

    @cmd2.with_argparser(view_parser)
    def do_view(self, args):
        if self.db_mgr is None:
            return self.poutput(style("[!] you are not connected to a database", fg="bright_magenta"))
        func = getattr(args, "func", None)
        if func is not None:
            func(args)
        else:
            self.do_help("view")

def main(
    name,
    old_tools_dir=Path().home() / ".recon-tools",
    old_tools_dict=Path().home() / ".cache" / ".tool-dict.pkl",
    old_searchsploit_rc=Path().home() / ".searchsploit_rc",
):
    if name == "__main__":
        if old_tools_dir.exists() and old_tools_dir.is_dir():
            print(style("[*] Found remnants of an older version of recon-pipeline.", fg="bright_yellow"))
            print(
                style(
                    f"[*] It's {style('strongly', fg='red')} advised that you allow us to remove them.",
                    fg="bright_white",
                )
            )
            print(
                style(
                    f"[*] Do you want to remove {old_tools_dir}/*, {old_searchsploit_rc}, and {old_tools_dict}?",
                    fg="bright_white",
                )
            )
            answer = cmd2.Cmd().select(["Yes", "No"])
            print(style(f"[+] You chose {answer}", fg="bright_green"))
            if answer == "Yes":
                shutil.rmtree(old_tools_dir)
                print(style(f"[+] {old_tools_dir} removed", fg="bright_green"))
                if old_tools_dict.exists():
                    old_tools_dict.unlink()
                    print(style(f"[+] {old_tools_dict} removed", fg="bright_green"))
                if old_searchsploit_rc.exists():
                    old_searchsploit_rc.unlink()
                    print(style(f"[+] {old_searchsploit_rc} removed", fg="bright_green"))
                print(style("[=] Please run the install all command to complete setup", fg="bright_blue"))
        rs = ReconShell(persistent_history_file="~/.reconshell_history", persistent_history_length=10000)
        sys.exit(rs.cmdloop())

main(name=__name__)
