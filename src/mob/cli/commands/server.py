"""Server command to run the API."""

import click


@click.command("serve")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8080, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def serve(host: str, port: int, reload: bool):
    """Start the mob API server."""
    import uvicorn

    uvicorn.run(
        "mob.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )
