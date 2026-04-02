"""Entrypoint for `python -m bioimageflow_server`."""

import uvicorn


def main() -> None:
    uvicorn.run(
        "bioimageflow_server.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
