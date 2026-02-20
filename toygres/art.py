from .constants import NAVY, RESET, GRAY, YELLOW, DEEP_RED

LOGO = f"""
{NAVY}  ████████╗ ██████╗ ██╗   ██╗ ██████╗ ██████╗ ███████╗███████╗{RESET}
{NAVY}  ╚══██╔══╝██╔═══██╗╚██╗ ██╔╝██╔════╝ ██╔══██╗██╔════╝██╔════╝{RESET}
{NAVY}     ██║   ██║   ██║ ╚████╔╝ ██║  ███╗██████╔╝█████╗  ███████╗{RESET}
{NAVY}     ██║   ██║   ██║  ╚██╔╝  ██║   ██║██╔══██╗██╔══╝  ╚════██║{RESET}
{NAVY}     ██║   ╚██████╔╝   ██║   ╚██████╔╝██║  ██║███████╗███████║{RESET}
{NAVY}     ╚═╝    ╚═════╝    ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝{RESET}
"""


def print_logo():
    print(LOGO)


def print_shortcuts():
    print(f"\n  {GRAY}Available Commands:{RESET}")
    print(
        f"  {GRAY}• {RESET};{GRAY}                 - Execute standard SQL query{RESET}"
    )
    print(
        f"  {GRAY}• {RESET}\\{GRAY}                 - Execute psql meta-commands{RESET}"
    )
    print(
        f"  {GRAY}• {RESET}menu{GRAY}              - Return to Database selection{RESET}"
    )
    print(
        f"  {GRAY}• {YELLOW}reset db{GRAY}          - Delete all the entries from all the tables{RESET}"
    )
    print(
        f"  {GRAY}• {DEEP_RED}atom bomb{GRAY}         - Deletes all the tables, indexes, enums, functions, everything!{RESET}"
    )
    print(f"  {GRAY}• {RESET}Ctrl+C{GRAY}            - Quit application{RESET}\n")
