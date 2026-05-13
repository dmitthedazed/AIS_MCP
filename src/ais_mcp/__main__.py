from ais_mcp.server import app


def main():
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
