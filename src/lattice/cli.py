"""CLI entry point for lattice commands."""

from __future__ import annotations

import argparse
import sys

from lattice import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lattice", description="Lattice CLI")
    parser.add_argument("--config-dir", default=None, help="Override config directory")
    parser.add_argument("--version", action="version", version=f"lattice {__version__}")

    sub = parser.add_subparsers(dest="command")

    # --- auth ---
    auth_parser = sub.add_parser("auth", help="API key authentication")
    auth_sub = auth_parser.add_subparsers(dest="auth_command")

    login_p = auth_sub.add_parser("login", help="Authenticate with API token")
    login_p.add_argument("--hostname", default=None)
    login_p.add_argument("--api-url", default=None)
    login_p.add_argument("--with-token", default=None, help="Pass token directly")
    login_p.add_argument("--no-browser", action="store_true")

    status_p = auth_sub.add_parser("status", help="Show auth status")
    status_p.add_argument("--show-token", action="store_true")
    status_p.add_argument("--offline", action="store_true")

    auth_sub.add_parser("logout", help="Remove credentials")
    auth_sub.add_parser("token", help="Print raw token")

    # --- ui ---
    ui_parser = sub.add_parser("ui", help="Browser-based UI operations")
    ui_sub = ui_parser.add_subparsers(dest="ui_command")

    ui_login_p = ui_sub.add_parser("login", help="SSO login via browser")
    ui_login_p.add_argument("--hostname", default=None)
    ui_login_p.add_argument("--timeout", type=int, default=300)
    ui_login_p.add_argument("--headless", action="store_true")
    ui_login_p.add_argument("--cdp-url", default=None)

    ui_sub.add_parser("status", help="Check browser session")
    ui_sub.add_parser("logout", help="Remove browser session")

    scrape_p = ui_sub.add_parser("scrape", help="Scrape a Lattice page")
    scrape_p.add_argument("path", nargs="?", default="/home")
    scrape_p.add_argument("--hostname", default=None)
    scrape_p.add_argument("--out", default="./lattice-scrape")
    scrape_p.add_argument("--html", action="store_true")
    scrape_p.add_argument("--no-graphql", action="store_true")
    scrape_p.add_argument("--screenshot", default=None)
    scrape_p.add_argument("--headed", action="store_true")
    scrape_p.add_argument("--print", dest="print_text", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "auth":
        from lattice import auth

        if args.auth_command == "login":
            return auth.login(
                token=args.with_token,
                hostname=args.hostname,
                api_url=args.api_url,
                no_browser=args.no_browser,
                config_dir=args.config_dir,
            )
        elif args.auth_command == "status":
            return auth.status(
                show_token=args.show_token,
                offline=args.offline,
                config_dir=args.config_dir,
            )
        elif args.auth_command == "logout":
            return auth.logout(args.config_dir)
        elif args.auth_command == "token":
            return auth.token(args.config_dir)
        else:
            auth_parser.print_help()
            return 1

    elif args.command == "ui":
        from lattice import ui

        if args.ui_command == "login":
            return ui.ui_login(
                hostname=args.hostname,
                timeout=args.timeout,
                headless=args.headless,
                cdp_url=args.cdp_url,
                config_dir_override=args.config_dir,
            )
        elif args.ui_command == "status":
            return ui.ui_status(args.config_dir)
        elif args.ui_command == "logout":
            return ui.ui_logout(args.config_dir)
        elif args.ui_command == "scrape":
            return ui.ui_scrape(
                path=args.path,
                hostname=args.hostname,
                out_dir=args.out,
                capture_html=args.html,
                no_graphql=args.no_graphql,
                screenshot=args.screenshot,
                headed=args.headed,
                print_text=args.print_text,
                config_dir_override=args.config_dir,
            )
        else:
            ui_parser.print_help()
            return 1

    else:
        parser.print_help()
        return 1
