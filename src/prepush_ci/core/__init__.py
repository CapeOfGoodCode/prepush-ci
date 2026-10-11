"""The pure core: decisions without I/O (trailers, config values, ref lines, verify).

Nothing here touches the file system, processes, the environment or the network; the CLI and
hook modules do that and pass plain values in. tests/unit covers this package to 100% on its own.
"""
