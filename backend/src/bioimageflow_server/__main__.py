"""Entrypoint for `python -m bioimageflow_server`."""

import argparse
import uvicorn


_RELOAD_EXCLUDES = [
    ".git/*",
    ".mypy_cache/*",
    ".pytest_cache/*",
    ".ruff_cache/*",
    ".venv/*",
    ".pixi/*",
    "bif_data/*",
    "datasets/*",
    "tool_packages/*",
    "workflows/*",
    "**/.wetlands/*",
    "**/envs/*",
    "**/site-packages/*",
]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="BioImageFlow Server")
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Launch in desktop mode with a pywebview window",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable development mode",
    )
    args = parser.parse_args(argv)

    if args.desktop:
        from bioimageflow_server.desktop import start_desktop

        start_desktop(host=args.host, port=args.port, dev=args.dev)
    elif args.dev:
        from pathlib import Path

        package_dir = Path(__file__).resolve().parent
        uvicorn.run(
            "bioimageflow_server.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=True,
            reload_dirs=[str(package_dir)],
            reload_includes=["*.py"],
            reload_excludes=_RELOAD_EXCLUDES,
        )
    else:
        uvicorn.run(
            "bioimageflow_server.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=False,
        )


if __name__ == "__main__":
    main()
